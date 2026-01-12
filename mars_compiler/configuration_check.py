import os

from lexer import tokenize
from parser import Parser
from type_checker import TypeChecker
from component_registry import ComponentRegistry
from component_validator import ComponentValidator, ComponentValidationError
from component_visualizer import visualize_components
from ast_nodes import ComponentDef, FuncDecl, VarDecl, Call, Return, Block, Var, NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, UnaryOp, RequirementSpec, RequirementParam, RequirementFunction


def precompile_config(config_dir: str, debug: bool = False):
    """
    Parse and validate component config and prepare runtime metadata.
    Returns (registry, interfaces, comp_funcs, comp_params, component_tree, component_parents).
    """
    registry = ComponentRegistry()
    interfaces = load_marsc_files(config_dir, registry, debug=debug)
    component_tree, component_parents = build_component_tree(registry, interfaces)
    errors, flags = validate_requirements(component_tree, component_parents, os.path.dirname(__file__))
    if errors:
        msg = ["Requirements check failed:"]
        msg.extend(f"  - {err}" for err in errors)
        if flags:
            msg.append("Flags:")
            msg.extend(f"  - {flag}" for flag in flags)
        raise SystemExit("\n".join(msg))
    if flags:
        print("[requirements] Flags:")
        for flag in flags:
            print(f"  - {flag}")
    comp_funcs, comp_params = build_component_runtime(registry, interfaces, component_tree)
    return registry, interfaces, comp_funcs, comp_params, component_tree, component_parents


def load_marsc_files(directory, registry, debug: bool = False):
    # built-in base Robot component (empty)
    components = [ComponentDef("Robot", None, [], [], [])]
    for filename in os.listdir(directory):
        if filename.endswith(".marsc"):
            with open(os.path.join(directory, filename)) as f:
                code = f.read()
            file_path = os.path.join(directory, filename)
            tokens = tokenize(code, source_path=file_path)
            parser = Parser(tokens, source_text=code, source_path=file_path)
            ast = parser.parse()
            for comp in ast.components:
                if comp.name == "Robot":
                    raise ComponentValidationError("Defining 'Robot' is not allowed; it is a built-in base component.")
                components.append(comp)

    if components:
        validator = ComponentValidator(components)
        try:
            interfaces = validator.validate()
        except ComponentValidationError as e:
            raise Exception(f"Component validation failed: {e}")

        # Type-check component functions with component-aware scope
        tc = TypeChecker(component_interfaces=interfaces)
        tc.check_components(components)

        _render_graphviz(visualize_components(components), os.path.join(directory, "component_tree"))

        for component in components:
            registry.register(component)
        return interfaces

    return {}


def build_component_tree(registry, interfaces):
    component_parents = {name: comp.parent for name, comp in registry.components.items()}
    nodes = {}
    roots = []

    def _eval_literal(node):
        if node is None:
            return None
        if isinstance(node, NumberLiteral):
            return node.value
        if isinstance(node, StringLiteral):
            return node.value
        if isinstance(node, BooleanLiteral):
            return node.value
        if isinstance(node, UnaryOp) and node.op == "NEGATE":
            val = _eval_literal(node.operand)
            if isinstance(val, (int, float)):
                return -val
            return None
        if isinstance(node, BinaryOp) and node.op in ("PLUS", "MINUS", "MUL", "DIV"):
            left = _eval_literal(node.left)
            right = _eval_literal(node.right)
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                return None
            if node.op == "PLUS":
                return left + right
            if node.op == "MINUS":
                return left - right
            if node.op == "MUL":
                return left * right
            if node.op == "DIV":
                return left / right
        return None

    def _is_robot_family(comp_def):
        if comp_def.name == "Robot":
            return True
        parent = comp_def.parent
        while parent:
            if parent == "Robot":
                return True
            parent_def = registry.get(parent)
            if parent_def is None:
                break
            parent = parent_def.parent
        return False

    def _build_node(type_name, instance_name, parent_path, bindings, type_stack):
        comp_def = registry.get(type_name)
        if comp_def is None:
            return None

        path = instance_name if parent_path is None else f"{parent_path}.{instance_name}"
        param_ast = {}
        param_values = {}
        param_types = {}

        for param in comp_def.parameters:
            param_ast[param.name] = param.value
            param_values[param.name] = _eval_literal(param.value)
            param_types[param.name] = param.vartype

        for bname, bval in bindings or []:
            param_ast[bname] = bval
            param_values[bname] = _eval_literal(bval)

        node = {
            "name": instance_name,
            "type": type_name,
            "path": path,
            "params": param_values,
            "param_ast": param_ast,
            "param_types": param_types,
            "functions": set(interfaces.get(type_name, {}).get("funcs", {}).keys()),
            "subcomponents": {},
            "children": [],
        }
        nodes[path] = node

        if type_name in type_stack:
            return node

        for sub in comp_def.subcomponents:
            child = _build_node(sub.type_name, sub.name, path, sub.bindings, type_stack + [type_name])
            if child is None:
                continue
            node["subcomponents"][sub.name] = child["path"]
            node["children"].append(child["path"])

        return node

    for comp in registry.components.values():
        if not _is_robot_family(comp):
            continue
        if comp.name == "Robot":
            continue
        node = _build_node(comp.name, comp.name, None, None, [])
        if node:
            roots.append(node["path"])

    return {"nodes": nodes, "roots": roots}, component_parents


def validate_requirements(component_tree, component_parents, base_dir):
    errors = []
    flags = []

    def _expr_to_str(expr):
        if isinstance(expr, Var):
            return expr.name
        if isinstance(expr, NumberLiteral):
            return str(expr.value)
        if isinstance(expr, StringLiteral):
            return repr(expr.value)
        if isinstance(expr, BooleanLiteral):
            return "true" if expr.value else "false"
        if isinstance(expr, UnaryOp):
            op = "!" if expr.op == "BANG" else "-"
            return f"{op}{_expr_to_str(expr.operand)}"
        if isinstance(expr, BinaryOp):
            op_map = {
                "AND": "&&",
                "OR": "||",
                "EQ": "==",
                "NEQ": "!=",
                "LT": "<",
                "GT": ">",
                "LEQ": "<=",
                "GEQ": ">=",
                "PLUS": "+",
                "MINUS": "-",
                "MUL": "*",
                "DIV": "/",
            }
            op = op_map.get(expr.op, expr.op)
            return f"{_expr_to_str(expr.left)} {op} {_expr_to_str(expr.right)}"
        return "<expr>"

    def _format_requirement(req):
        parts = [req.type_name]
        args = []
        if req.subcomponents:
            args.append("subcomponents=...")
        if req.parameters:
            args.append("parameters=...")
        if req.functions:
            args.append("functions=...")
        if args:
            return f"{req.type_name}({', '.join(args)})"
        return req.type_name

    def _is_type_or_child(type_name, target_type):
        if type_name == target_type:
            return True
        cur = component_parents.get(type_name)
        while cur:
            if cur == target_type:
                return True
            cur = component_parents.get(cur)
        return False

    def _collect_vars(expr, out):
        if isinstance(expr, Var):
            out.add(expr.name)
        elif isinstance(expr, UnaryOp):
            _collect_vars(expr.operand, out)
        elif isinstance(expr, BinaryOp):
            _collect_vars(expr.left, out)
            _collect_vars(expr.right, out)

    def _eval_condition(expr, param_values):
        if isinstance(expr, Var):
            return param_values.get(expr.name)
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, BooleanLiteral):
            return expr.value
        if isinstance(expr, UnaryOp):
            val = _eval_condition(expr.operand, param_values)
            if val is None:
                return None
            if expr.op == "NEGATE" and isinstance(val, (int, float)):
                return -val
            if expr.op == "BANG":
                return not bool(val)
            return None
        if isinstance(expr, BinaryOp):
            left = _eval_condition(expr.left, param_values)
            right = _eval_condition(expr.right, param_values)
            if left is None or right is None:
                return None
            if expr.op == "AND":
                return bool(left) and bool(right)
            if expr.op == "OR":
                return bool(left) or bool(right)
            if expr.op == "EQ":
                return left == right
            if expr.op == "NEQ":
                return left != right
            if expr.op == "LT":
                try:
                    return left < right
                except TypeError:
                    return None
            if expr.op == "GT":
                try:
                    return left > right
                except TypeError:
                    return None
            if expr.op == "LEQ":
                try:
                    return left <= right
                except TypeError:
                    return None
            if expr.op == "GEQ":
                try:
                    return left >= right
                except TypeError:
                    return None
        return None

    def _param_failure_reason(expr, node):
        names = set()
        _collect_vars(expr, names)
        missing = [name for name in sorted(names) if name not in node["params"] or node["params"][name] is None]
        if missing:
            return f"parameter(s) {', '.join(missing)} missing on {node['type']}"
        result = _eval_condition(expr, node["params"])
        if result:
            return None
        values = ", ".join(f"{name}={node['params'].get(name)!r}" for name in sorted(names))
        return f"parameter check '{_expr_to_str(expr)}' failed on {node['type']}{f' ({values})' if values else ''}"

    def _find_matches(root_path, target_type):
        matches = []
        stack = [root_path]
        nodes = component_tree["nodes"]
        while stack:
            path = stack.pop()
            node = nodes.get(path)
            if node is None:
                continue
            if _is_type_or_child(node["type"], target_type):
                matches.append(path)
            stack.extend(node["children"])
        return matches

    def _check_constraints(node, req):
        local_flags = []
        local_errors = []

        for param_req in req.parameters or []:
            reason = _param_failure_reason(param_req.expr, node)
            if reason:
                msg = f"optional {reason}" if param_req.optional else reason
                if param_req.optional:
                    local_flags.append(msg)
                else:
                    local_errors.append(msg)

        for func_req in req.functions or []:
            if func_req.name not in node["functions"]:
                msg = f"function '{func_req.name}()' missing on {node['type']}"
                if func_req.optional:
                    local_flags.append(f"optional {msg}")
                else:
                    local_errors.append(msg)

        for sub_req in req.subcomponents or []:
            ok, sub_flags, sub_errors = _check_requirement_on_subtree(node["path"], sub_req)
            if not ok:
                sub_detail = "; ".join(sub_errors) if sub_errors else f"missing component '{sub_req.type_name}'"
                msg = f"subcomponent '{sub_req.type_name}' requirement failed under {node['type']}: {sub_detail}"
                if sub_req.optional:
                    local_flags.append(f"optional {msg}")
                else:
                    local_errors.append(msg)
            else:
                local_flags.extend(sub_flags)

        return len(local_errors) == 0, local_flags, local_errors

    def _check_requirement_on_subtree(root_path, req):
        matches = _find_matches(root_path, req.type_name)
        if not matches:
            return False, [], [f"missing component '{req.type_name}'"]
        best_flags = None
        best_errors = None
        nodes = component_tree["nodes"]
        for path in matches:
            node = nodes.get(path)
            if node is None:
                continue
            ok, local_flags, local_errors = _check_constraints(node, req)
            if ok and not local_flags:
                return True, [], []
            if ok and best_flags is None:
                best_flags = local_flags
            if not ok and best_errors is None and local_errors:
                best_errors = local_errors
        if best_flags is not None:
            return True, best_flags, []
        if best_errors is None:
            best_errors = [f"no '{req.type_name}' instance satisfied constraints"]
        return False, [], best_errors

    for filename in os.listdir(base_dir):
        if not filename.endswith(".mars"):
            continue
        file_path = os.path.join(base_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        tokens = tokenize(code, source_path=file_path)
        parser = Parser(tokens, source_text=code, source_path=file_path)
        ast = parser.parse()
        for cls in ast.classes or []:
            for req in cls.requirements or []:
                ok = False
                req_flags = []
                req_errors = []
                for root in component_tree["roots"]:
                    ok, req_flags, req_errors = _check_requirement_on_subtree(root, req)
                    if ok:
                        break
                if not ok:
                    if req_errors:
                        if len(req_errors) == 1 and req_errors[0].startswith("missing component "):
                            detail = f": {req_errors[0]}"
                        else:
                            detail_lines = "\n".join(f"      - {detail}" for detail in req_errors)
                            detail = f":\n{detail_lines}"
                    else:
                        detail = ""
                    msg = f"{filename}:{cls.name} requirement {_format_requirement(req)} failed{detail}"
                    if req.optional:
                        flags.append(msg)
                    else:
                        errors.append(msg)
                else:
                    for flag in req_flags:
                        flags.append(f"{filename}:{cls.name} {flag}")

    return errors, flags


def build_component_runtime(registry, interfaces, component_tree=None):
    """
    Build lists of FuncDecl and VarDecl for component runtime exposure.
    - Component params become readonly globals: Component.param
    - Component functions get namespaced as Component.func
    - Subcomponent bindings/params get aliases: Parent.sub.param
    - Subcomponent functions get aliases: Parent.sub.func
    """
    comp_funcs = []
    comp_params = []

    def _literal_to_ast(val):
        if val is None:
            return None
        if isinstance(val, bool):
            return BooleanLiteral(val)
        if isinstance(val, (int, float)):
            return NumberLiteral(val)
        if isinstance(val, str):
            return StringLiteral(val)
        return None

    # Helper to find function definition by name
    def _find_func_def(comp_def, fname):
        for f in comp_def.functions:
            if f.name == fname:
                return f
        return None

    def _find_func_def_in_hierarchy(comp_def, fname):
        cur = comp_def
        while cur:
            found = _find_func_def(cur, fname)
            if found and found.body is not None:
                return found, cur.name
            if not cur.parent:
                break
            cur = registry.get(cur.parent)
        return None, None

    if component_tree:
        for path, node in component_tree["nodes"].items():
            comp_params.append(VarDecl(node["type"], path, StringLiteral(path), True))
            for pname, ptype in node["param_types"].items():
                pval = node["param_ast"].get(pname)
                if pval is None:
                    pval = _literal_to_ast(node["params"].get(pname))
                comp_params.append(VarDecl(ptype, f"{path}.{pname}", pval, True))

    for comp in registry.components.values():
        if not component_tree:
            # Own params
            for param in comp.parameters:
                comp_params.append(VarDecl(param.vartype, f"{comp.name}.{param.name}", param.value, True))

        # Functions (including inherited bodies) -> compile or wrap under this component's namespace
        iface_funcs = interfaces.get(comp.name, {}).get("funcs", {})
        for fname, finfo in iface_funcs.items():
            fdef, def_owner = _find_func_def_in_hierarchy(comp, fname)
            if fdef is None or fdef.body is None:
                continue
            params = fdef.params
            if def_owner == comp.name:
                comp_funcs.append(FuncDecl(fdef.return_type, f"{comp.name}.{fname}", params, fdef.body))
            else:
                call_target = f"{def_owner}.{fname}"
                args = [Var(p[1]) for p in params]
                call_node = Call(Var(call_target), args)
                body_stmts = []
                if fdef.return_type != "void":
                    body_stmts.append(Return(call_node))
                else:
                    body_stmts.append(call_node)
                    body_stmts.append(Return(None))
                comp_funcs.append(FuncDecl(fdef.return_type, f"{comp.name}.{fname}", params, Block(body_stmts)))

        # Subcomponents
        for sub in comp.subcomponents:
            sub_iface = interfaces.get(sub.type_name, {})
            sub_params_types = sub_iface.get("params", {})
            bindings = {b[0]: b[1] for b in (sub.bindings or [])}
            sub_def = registry.get(sub.type_name)
            default_map = {p.name: p.value for p in sub_def.parameters}

            if not component_tree:
                # Alias variable for the subcomponent instance (namespaced only)
                comp_params.append(VarDecl(sub.type_name, f"{comp.name}.{sub.name}", None, True))

            # Param aliases for subcomponent instance
            for pname, ptype in sub_params_types.items():
                val = bindings.get(pname, default_map.get(pname))
                if not component_tree:
                    comp_params.append(VarDecl(ptype, f"{comp.name}.{sub.name}.{pname}", val, True))

            # Function aliases for subcomponent instance
            sub_funcs = sub_iface.get("funcs", {})
            for fname, finfo in sub_funcs.items():
                fdef = _find_func_def(sub_def, fname)
                params = fdef.params if fdef else [(ptype, f"arg{i}") for i, ptype in enumerate(finfo.get("params", []))]
                call_target = f"{sub.type_name}.{fname}"
                args = [Var(p[1]) for p in params]
                call_node = Call(Var(call_target), args)
                body_stmts = []
                if finfo.get("return") != "void":
                    body_stmts.append(Return(call_node))
                else:
                    body_stmts.append(call_node)
                    body_stmts.append(Return(None))
                alias = FuncDecl(finfo.get("return"), f"{comp.name}.{sub.name}.{fname}", params, Block(body_stmts))
                comp_funcs.append(alias)

    return comp_funcs, comp_params


def robot_tree_has_component(registry, target_type: str) -> bool:
    """
    Return True if any Robot-rooted component tree includes target_type or a child of it.
    """
    if not target_type:
        return False

    def _is_type_or_child(type_name: str, ancestor: str) -> bool:
        cur = registry.get(type_name)
        while cur:
            if cur.name == ancestor:
                return True
            if not cur.parent:
                break
            cur = registry.get(cur.parent)
        return False

    def _is_robot_family(comp_def) -> bool:
        if comp_def.name == "Robot":
            return True
        parent = comp_def.parent
        while parent:
            if parent == "Robot":
                return True
            parent_def = registry.get(parent)
            if parent_def is None:
                break
            parent = parent_def.parent
        return False

    roots = [c.name for c in registry.components.values() if _is_robot_family(c) and c.name != "Robot"]
    stack = list(roots)
    visited = set()

    while stack:
        comp_name = stack.pop()
        if comp_name in visited:
            continue
        visited.add(comp_name)
        if _is_type_or_child(comp_name, target_type):
            return True
        comp_def = registry.get(comp_name)
        if comp_def is None:
            continue
        for sub in comp_def.subcomponents:
            stack.append(sub.type_name)

    return False


def _render_graphviz(dot_obj, filename):
    """Render a graphviz object but do not fail the run if Graphviz is missing."""
    try:
        return dot_obj.render(filename, cleanup=True)
    except Exception as e:
        print(f"[debug] Skipping graph render for {filename}: {e}")
        return None
