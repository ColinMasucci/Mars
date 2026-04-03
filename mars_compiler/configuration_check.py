import os
import re

from lexer import tokenize
from parser import Parser
from type_checker import TypeChecker
from component_registry import ComponentRegistry
from component_validator import ComponentValidator, ComponentValidationError
from component_visualizer import visualize_components
from ast_nodes import ArrayAccess, ArrayLiteral, Assign, AugAssign, BinaryOp, Block, BooleanLiteral, Call, ComponentDef, DictLiteral, FuncDecl, If, Import, MemberAccess, NumberLiteral, Program, RequirementExpr, RequirementFunction, RequirementParam, RequirementSpec, Return, StringLiteral, UnaryOp, UnitTag, Var, VarDecl, While, For

_SUBSCRIBE_EXAMPLE = 'lidar = subscribe("/scan", "sensor_msgs/msg/LaserScan");'


def _load_ros_topics_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    if not os.path.exists(path):
        return {}
    topics = {}
    pat = re.compile(r"^(\S+)\s+\(([^)]+)\)")
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = pat.match(line)
            if not m:
                continue
            topics[m.group(1)] = m.group(2)
    return topics


def precompile_config(config_dir: str, debug: bool = False, ros_topics_file: str | None = None):
    """
    Parse and validate component config and prepare runtime metadata.
    Returns (registry, interfaces, comp_funcs, comp_params, component_tree, component_parents).
    """
    registry = ComponentRegistry()
    interfaces = load_marsc_files(config_dir, registry, debug=debug)
    topics_map = _load_ros_topics_map(ros_topics_file)
    component_tree, component_parents = build_component_tree(registry, interfaces, ros_topics_map=topics_map, ros_topics_file=ros_topics_file)
    comp_funcs, comp_params = build_component_runtime(registry, interfaces, component_tree)
    return registry, interfaces, comp_funcs, comp_params, component_tree, component_parents


def load_marsc_files(directory, registry, debug: bool = False):
    # built-in base Robot component (empty)
    components = [ComponentDef("Robot", None, [], [], [])]
    import_statements = []
    for filename in os.listdir(directory):
        if filename.endswith(".marsc"):
            with open(os.path.join(directory, filename)) as f:
                code = f.read()
            file_path = os.path.join(directory, filename)
            tokens = tokenize(code, source_path=file_path)
            parser = Parser(tokens, source_text=code, source_path=file_path)
            ast = parser.parse()
            import_statements.extend(
                stmt for stmt in ast.statements if isinstance(stmt, Import)
            )
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
        for stmt in import_statements:
            tc.check(stmt)
        tc.check_components(components)

        _render_graphviz(visualize_components(components), os.path.join(directory, "component_tree"))

        for component in components:
            registry.register(component)
        return interfaces

    return {}


def build_component_tree(registry, interfaces, ros_topics_map=None, ros_topics_file: str | None = None):
    component_parents = {name: comp.parent for name, comp in registry.components.items()}
    nodes = {}
    roots = []
    ros_topics_map = ros_topics_map or {}

    def _eval_literal(node):
        if node is None:
            return None
        if isinstance(node, NumberLiteral):
            return node.value
        if isinstance(node, UnitTag):
            return _eval_literal(node.expr)
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

    def _parse_subscribe(node, path, param_name):
        if not isinstance(node, Call):
            return None
        if not isinstance(node.func, Var) or node.func.name != "subscribe":
            return None
        if len(node.args) != 2:
            raise ComponentValidationError(
                f"Invalid subscribe() in '{path}.{param_name}'. Expected subscribe(topic, msg_type). Example: {_SUBSCRIBE_EXAMPLE}"
            )
        topic_node, type_node = node.args
        if not isinstance(topic_node, StringLiteral) or not isinstance(type_node, StringLiteral):
            raise ComponentValidationError(
                f"Invalid subscribe() in '{path}.{param_name}'. Topic and msg_type must be string literals. Example: {_SUBSCRIBE_EXAMPLE}"
            )
        topic = topic_node.value
        msg_type = type_node.value
        if not ros_topics_map:
            raise ComponentValidationError(
                f"Cannot validate subscribed topic '{topic}' for '{path}.{param_name}'. No ROS topics available at '{ros_topics_file or 'ros_topics.txt'}'. "
                f"Example: {_SUBSCRIBE_EXAMPLE}"
            )
        resolved_topic = topic
        field_path = []
        discovered_type = ros_topics_map.get(resolved_topic)
        if not discovered_type:
            parts = topic.split("/")
            for idx in range(len(parts) - 1, 1, -1):
                candidate = "/".join(parts[:idx])
                if not candidate:
                    continue
                discovered_type = ros_topics_map.get(candidate)
                if discovered_type:
                    resolved_topic = candidate
                    field_path = parts[idx:]
                    break
        if not discovered_type:
            raise ComponentValidationError(
                f"Invalid subscription topic '{topic}' for '{path}.{param_name}'. Topic not found in discovered ROS topics. "
                f"Example: {_SUBSCRIBE_EXAMPLE}"
            )
        if discovered_type != msg_type:
            raise ComponentValidationError(
                f"Invalid subscription type for '{topic}' in '{path}.{param_name}'. Expected '{discovered_type}', got '{msg_type}'. "
                f"Example: {_SUBSCRIBE_EXAMPLE}"
            )
        return {"topic": resolved_topic, "msg_type": msg_type, "field_path": field_path}

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

        subscriptions = {}
        for pname, pexpr in list(param_ast.items()):
            sub = _parse_subscribe(pexpr, path, pname)
            if sub:
                subscriptions[pname] = sub
                # Subscribed params are user-visible only after update(); default to None.
                param_values[pname] = None

        node = {
            "name": instance_name,
            "type": type_name,
            "path": path,
            "params": param_values,
            "param_ast": param_ast,
            "param_types": param_types,
            "subscriptions": subscriptions,
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
        if isinstance(expr, UnitTag):
            return f"{_expr_to_str(expr.expr)}::{expr.unit}"
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

    def _format_requirement_spec(req):
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

    def _format_requirement_expr(req):
        if isinstance(req, RequirementSpec):
            return _format_requirement_spec(req)
        if isinstance(req, RequirementExpr):
            if req.op == "NOT":
                inner = _format_requirement_expr(req.left)
                if isinstance(req.left, RequirementExpr):
                    inner = f"({inner})"
                return f"!{inner}"
            op = "&&" if req.op == "AND" else "||"
            prec = 2 if req.op == "AND" else 1
            left = _format_requirement_expr(req.left)
            right = _format_requirement_expr(req.right)
            if isinstance(req.left, RequirementExpr):
                left_prec = 2 if req.left.op == "AND" else 1
                if left_prec < prec:
                    left = f"({left})"
            if isinstance(req.right, RequirementExpr):
                right_prec = 2 if req.right.op == "AND" else 1
                if right_prec < prec:
                    right = f"({right})"
            return f"{left} {op} {right}"
        return "<requirement>"

    def _prefix_errors(label, errors):
        if not errors:
            return [f"{label} failed"]
        if len(errors) == 1:
            return [f"{label} failed: {errors[0]}"]
        return [f"{label} failed: {err}" for err in errors]

    def _apply_optional(req, status, local_flags, local_errors):
        if getattr(req, "optional", False) and status == "hard":
            return "soft", local_flags + local_errors, []
        return status, local_flags, local_errors

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
        elif isinstance(expr, UnitTag):
            _collect_vars(expr.expr, out)
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
        if isinstance(expr, UnitTag):
            return _eval_condition(expr.expr, param_values)
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
            status, sub_flags, sub_errors = _check_requirement_expr(node["path"], sub_req)
            if status == "hard":
                label = _format_requirement_expr(sub_req)
                sub_detail = "; ".join(sub_errors) if sub_errors else f"missing component '{label}'"
                msg = f"subcomponent '{label}' requirement failed under {node['type']}: {sub_detail}"
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

    def _check_requirement_expr(root_path, req):
        if isinstance(req, RequirementSpec):
            ok, local_flags, local_errors = _check_requirement_on_subtree(root_path, req)
            if ok:
                return _apply_optional(req, "ok", local_flags, [])
            return _apply_optional(req, "hard", local_flags, local_errors)
        if isinstance(req, RequirementExpr):
            if req.op == "NOT":
                status, _, _ = _check_requirement_expr(root_path, req.left)
                if status == "ok":
                    return _apply_optional(req, "hard", [], ["negated requirement matched"])
                return _apply_optional(req, "ok", [], [])
            left_status, left_flags, left_errors = _check_requirement_expr(root_path, req.left)
            right_status, right_flags, right_errors = _check_requirement_expr(root_path, req.right)
            if req.op == "OR":
                if left_status == "ok" and right_status == "ok":
                    return _apply_optional(req, "ok", left_flags if len(left_flags) <= len(right_flags) else right_flags, [])
                if left_status == "ok":
                    return _apply_optional(req, "ok", left_flags, [])
                if right_status == "ok":
                    return _apply_optional(req, "ok", right_flags, [])
                flags = []
                if left_status == "soft":
                    flags.extend(left_flags)
                if right_status == "soft":
                    flags.extend(right_flags)
                if left_status == "soft" and right_status == "soft":
                    return _apply_optional(req, "soft", flags, [])
                errors = []
                if left_status == "hard":
                    errors.extend(_prefix_errors(_format_requirement_expr(req.left), left_errors))
                if right_status == "hard":
                    errors.extend(_prefix_errors(_format_requirement_expr(req.right), right_errors))
                return _apply_optional(req, "hard", flags, errors)
            if req.op == "AND":
                flags = []
                flags.extend(left_flags)
                flags.extend(right_flags)
                errors = []
                status = "ok"
                if left_status == "hard":
                    status = "hard"
                    errors.extend(_prefix_errors(_format_requirement_expr(req.left), left_errors))
                if right_status == "hard":
                    status = "hard"
                    errors.extend(_prefix_errors(_format_requirement_expr(req.right), right_errors))
                if status != "hard" and (left_status == "soft" or right_status == "soft"):
                    status = "soft"
                return _apply_optional(req, status, flags, errors)
        return "hard", [], ["invalid requirement expression"]

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
                status = "hard"
                req_flags = []
                req_errors = []
                for root in component_tree["roots"]:
                    status, req_flags, req_errors = _check_requirement_expr(root, req)
                    if status != "hard":
                        break
                if status == "hard":
                    if req_errors:
                        if len(req_errors) == 1 and req_errors[0].startswith("missing component "):
                            detail = f": {req_errors[0]}"
                        else:
                            detail_lines = "\n".join(f"      - {detail}" for detail in req_errors)
                            detail = f":\n{detail_lines}"
                    else:
                        detail = ""
                    msg = f"{filename}:{cls.name} requirement {_format_requirement_expr(req)} failed{detail}"
                    errors.append(msg)
                elif status == "soft":
                    if req_flags:
                        if len(req_flags) == 1 and req_flags[0].startswith("missing component "):
                            detail = f": {req_flags[0]}"
                        else:
                            detail_lines = "\n".join(f"      - {detail}" for detail in req_flags)
                            detail = f":\n{detail_lines}"
                    else:
                        detail = ""
                    msg = f"{filename}:{cls.name} requirement {_format_requirement_expr(req)} failed{detail}"
                    flags.append(msg)
                else:
                    for flag in req_flags:
                        flags.append(f"{filename}:{cls.name} {flag}")

    return errors, flags


def validate_instantiated_requirements(program, component_tree, component_parents, class_interfaces):
    errors = []
    flags = []

    if not isinstance(program, Program):
        return errors, flags

    class_requirements = {}
    class_map = {}
    for cls in program.classes or []:
        class_requirements[cls.name] = cls.requirements or []
        class_map[cls.name] = cls

    if not any(class_requirements.values()):
        return errors, flags

    def _format_requirement_spec(req):
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

    def _format_requirement_expr(req):
        if isinstance(req, RequirementSpec):
            return _format_requirement_spec(req)
        if isinstance(req, RequirementExpr):
            if req.op == "NOT":
                inner = _format_requirement_expr(req.left)
                if isinstance(req.left, RequirementExpr):
                    inner = f"({inner})"
                return f"!{inner}"
            op = "&&" if req.op == "AND" else "||"
            prec = 2 if req.op == "AND" else 1
            left = _format_requirement_expr(req.left)
            right = _format_requirement_expr(req.right)
            if isinstance(req.left, RequirementExpr):
                left_prec = 2 if req.left.op == "AND" else 1
                if left_prec < prec:
                    left = f"({left})"
            if isinstance(req.right, RequirementExpr):
                right_prec = 2 if req.right.op == "AND" else 1
                if right_prec < prec:
                    right = f"({right})"
            return f"{left} {op} {right}"
        return "<requirement>"

    def _prefix_errors(label, items):
        if not items:
            return [f"{label} failed"]
        if len(items) == 1:
            return [f"{label} failed: {items[0]}"]
        return [f"{label} failed: {item}" for item in items]

    def _apply_optional(req, status, local_flags, local_errors):
        if getattr(req, "optional", False) and status == "hard":
            return "soft", local_flags + local_errors, []
        return status, local_flags, local_errors

    def _expr_to_str(expr):
        if isinstance(expr, Var):
            return expr.name
        if isinstance(expr, NumberLiteral):
            return str(expr.value)
        if isinstance(expr, UnitTag):
            return f"{_expr_to_str(expr.expr)}::{expr.unit}"
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
        elif isinstance(expr, UnitTag):
            _collect_vars(expr.expr, out)
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
        if isinstance(expr, UnitTag):
            return _eval_condition(expr.expr, param_values)
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
            status, sub_flags, sub_errors = _check_requirement_expr(node["path"], sub_req)
            if status == "hard":
                label = _format_requirement_expr(sub_req)
                sub_detail = "; ".join(sub_errors) if sub_errors else f"missing component '{label}'"
                msg = f"subcomponent '{label}' requirement failed under {node['type']}: {sub_detail}"
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

    def _check_requirement_expr(root_path, req):
        if isinstance(req, RequirementSpec):
            ok, local_flags, local_errors = _check_requirement_on_subtree(root_path, req)
            if ok:
                return _apply_optional(req, "ok", local_flags, [])
            return _apply_optional(req, "hard", local_flags, local_errors)
        if isinstance(req, RequirementExpr):
            if req.op == "NOT":
                status, _, _ = _check_requirement_expr(root_path, req.left)
                if status == "ok":
                    return _apply_optional(req, "hard", [], ["negated requirement matched"])
                return _apply_optional(req, "ok", [], [])
            left_status, left_flags, left_errors = _check_requirement_expr(root_path, req.left)
            right_status, right_flags, right_errors = _check_requirement_expr(root_path, req.right)
            if req.op == "OR":
                if left_status == "ok" and right_status == "ok":
                    return _apply_optional(req, "ok", left_flags if len(left_flags) <= len(right_flags) else right_flags, [])
                if left_status == "ok":
                    return _apply_optional(req, "ok", left_flags, [])
                if right_status == "ok":
                    return _apply_optional(req, "ok", right_flags, [])
                flags = []
                if left_status == "soft":
                    flags.extend(left_flags)
                if right_status == "soft":
                    flags.extend(right_flags)
                if left_status == "soft" and right_status == "soft":
                    return _apply_optional(req, "soft", flags, [])
                errors = []
                if left_status == "hard":
                    errors.extend(_prefix_errors(_format_requirement_expr(req.left), left_errors))
                if right_status == "hard":
                    errors.extend(_prefix_errors(_format_requirement_expr(req.right), right_errors))
                return _apply_optional(req, "hard", flags, errors)
            if req.op == "AND":
                flags = []
                flags.extend(left_flags)
                flags.extend(right_flags)
                errors = []
                status = "ok"
                if left_status == "hard":
                    status = "hard"
                    errors.extend(_prefix_errors(_format_requirement_expr(req.left), left_errors))
                if right_status == "hard":
                    status = "hard"
                    errors.extend(_prefix_errors(_format_requirement_expr(req.right), right_errors))
                if status != "hard" and (left_status == "soft" or right_status == "soft"):
                    status = "soft"
                return _apply_optional(req, status, flags, errors)
        return "hard", [], ["invalid requirement expression"]

    def _evaluate_requirements(requirements, root_path):
        req_errors = []
        req_flags = []
        for req in requirements or []:
            status, local_flags, local_errors = _check_requirement_expr(root_path, req)
            if status == "hard":
                if local_errors:
                    if len(local_errors) == 1 and local_errors[0].startswith("missing component "):
                        detail = f": {local_errors[0]}"
                    else:
                        detail_lines = "\n".join(f"      - {detail}" for detail in local_errors)
                        detail = f":\n{detail_lines}"
                else:
                    detail = ""
                req_errors.append(f"requirement {_format_requirement_expr(req)} failed{detail}")
            elif status == "soft":
                if local_flags:
                    if len(local_flags) == 1 and local_flags[0].startswith("missing component "):
                        detail = f": {local_flags[0]}"
                    else:
                        detail_lines = "\n".join(f"      - {detail}" for detail in local_flags)
                        detail = f":\n{detail_lines}"
                else:
                    detail = ""
                req_flags.append(f"requirement {_format_requirement_expr(req)} failed{detail}")
            else:
                for flag in local_flags:
                    req_flags.append(flag)
        return req_errors, req_flags

    def _match_component(start_path, target_type):
        nodes = component_tree["nodes"]
        if start_path not in nodes:
            return None, f"component '{start_path}' not found in config"
        queue = [(start_path, 0)]
        matches = []
        current_depth = 0
        while queue:
            path, depth = queue.pop(0)
            if depth > current_depth and matches:
                break
            node = nodes.get(path)
            if node is None:
                continue
            if _is_type_or_child(node["type"], target_type):
                matches.append(path)
                current_depth = depth
            for child in node["children"]:
                queue.append((child, depth + 1))
        if not matches:
            return None, f"match could not find '{target_type}' under '{start_path}'"
        if len(matches) > 1:
            return None, f"match found multiple '{target_type}' under '{start_path}' at depth {current_depth}"
        return matches[0], None

    def _component_expr_str(expr):
        if isinstance(expr, Var):
            return expr.name
        if isinstance(expr, MemberAccess):
            return f"{_component_expr_str(expr.obj)}.{expr.attr}"
        if isinstance(expr, Call) and isinstance(expr.func, MemberAccess) and expr.func.attr == "match":
            if len(expr.args) == 1 and isinstance(expr.args[0], Var):
                return f"{_component_expr_str(expr.func.obj)}.match({expr.args[0].name})"
            return f"{_component_expr_str(expr.func.obj)}.match(...)"
        return "<component>"

    def _resolve_component_path(expr, path_scopes):
        if isinstance(expr, Var):
            for scope in reversed(path_scopes):
                if expr.name in scope:
                    return scope[expr.name], None
            if expr.name in component_tree["nodes"]:
                return expr.name, None
            return None, f"component '{expr.name}' not found in config"
        if isinstance(expr, MemberAccess):
            base_path, err = _resolve_component_path(expr.obj, path_scopes)
            if err or base_path is None:
                return None, err
            node = component_tree["nodes"].get(base_path)
            if node is None:
                return None, f"component '{base_path}' not found in config"
            if expr.attr in node.get("subcomponents", {}):
                return node["subcomponents"][expr.attr], None
            return None, f"component '{base_path}' has no subcomponent '{expr.attr}'"
        if isinstance(expr, Call) and isinstance(expr.func, MemberAccess) and expr.func.attr == "match":
            base_path, err = _resolve_component_path(expr.func.obj, path_scopes)
            if err or base_path is None:
                return None, err
            if len(expr.args) != 1 or not isinstance(expr.args[0], Var):
                return None, "match requires a component type identifier"
            return _match_component(base_path, expr.args[0].name)
        return None, None

    def _is_component_type(type_str):
        return isinstance(type_str, str) and type_str.startswith("component:")

    def _prefix_message(prefix, msg):
        lines = msg.splitlines()
        lines[0] = f"{prefix} {lines[0]}"
        return "\n".join(lines)

    type_scopes = [{}]
    path_scopes = [{}]

    def _lookup_type(name):
        for scope in reversed(type_scopes):
            if name in scope:
                return scope[name]
        return None

    def _declare(name, typ, path=None):
        type_scopes[-1][name] = typ
        if _is_component_type(typ):
            path_scopes[-1][name] = path

    def _set_path(name, path):
        for scope in reversed(path_scopes):
            if name in scope:
                scope[name] = path
                return
        if name in type_scopes[-1]:
            path_scopes[-1][name] = path

    def _normalize_decl_type(vartype):
        if isinstance(vartype, str) and vartype in component_parents:
            return f"component:{vartype}"
        if isinstance(vartype, str) and vartype in class_interfaces:
            return f"class:{vartype}"
        return vartype

    def _handle_constructor_call(call_node, instance_name=None):
        if not isinstance(call_node.func, Var):
            return
        class_name = call_node.func.name
        requirements = class_requirements.get(class_name) or []
        if not requirements:
            return

        component_args = []
        for idx, arg in enumerate(call_node.args or []):
            arg_type = getattr(arg, "inferred_type", None)
            if _is_component_type(arg_type):
                component_args.append((idx, arg))

        if not component_args:
            label = f"{class_name}"
            if instance_name:
                label = f"{label} (instance={instance_name})"
            errors.append(f"{label} requires a component argument for requirements validation")
            return

        for idx, arg in component_args:
            path, err = _resolve_component_path(arg, path_scopes)
            label_parts = [class_name]
            detail_parts = []
            if instance_name:
                detail_parts.append(f"instance={instance_name}")
            detail_parts.append(f"component={_component_expr_str(arg) if path is None else path}")
            detail_parts.append(f"arg={idx + 1}")
            label = f"{label_parts[0]} ({', '.join(detail_parts)})"

            if err or path is None:
                reason = err or "component path could not be resolved"
                errors.append(f"{label} component argument could not be resolved: {reason}")
                continue

            req_errors, req_flags = _evaluate_requirements(requirements, path)
            for item in req_errors:
                errors.append(_prefix_message(label, item))
            for item in req_flags:
                flags.append(_prefix_message(label, item))

    def _walk_expr(expr):
        if isinstance(expr, Call):
            _handle_constructor_call(expr, None)
            if isinstance(expr.func, MemberAccess):
                _walk_expr(expr.func.obj)
            for arg in expr.args or []:
                _walk_expr(arg)
            return
        if isinstance(expr, MemberAccess):
            _walk_expr(expr.obj)
            return
        if isinstance(expr, BinaryOp):
            _walk_expr(expr.left)
            _walk_expr(expr.right)
            return
        if isinstance(expr, UnaryOp):
            _walk_expr(expr.operand)
            return
        if isinstance(expr, UnitTag):
            _walk_expr(expr.expr)
            return
        if isinstance(expr, ArrayAccess):
            _walk_expr(expr.array)
            _walk_expr(expr.index)
            return
        if isinstance(expr, ArrayLiteral):
            for item in expr.elements or []:
                _walk_expr(item)
            return
        if isinstance(expr, DictLiteral):
            for k, v in expr.pairs or []:
                _walk_expr(k)
                _walk_expr(v)
            return

    def _walk_statement(stmt):
        if isinstance(stmt, Block):
            type_scopes.append({})
            path_scopes.append({})
            for inner in stmt.statements:
                _walk_statement(inner)
            type_scopes.pop()
            path_scopes.pop()
            return
        if isinstance(stmt, If):
            _walk_expr(stmt.condition)
            type_scopes.append({})
            path_scopes.append({})
            _walk_statement(stmt.then_branch)
            type_scopes.pop()
            path_scopes.pop()
            if stmt.else_branch:
                type_scopes.append({})
                path_scopes.append({})
                _walk_statement(stmt.else_branch)
                type_scopes.pop()
                path_scopes.pop()
            return
        if isinstance(stmt, While):
            _walk_expr(stmt.condition)
            type_scopes.append({})
            path_scopes.append({})
            _walk_statement(stmt.body)
            type_scopes.pop()
            path_scopes.pop()
            return
        if isinstance(stmt, For):
            type_scopes.append({})
            path_scopes.append({})
            if stmt.init is not None:
                _walk_statement(stmt.init)
            if stmt.condition is not None:
                _walk_expr(stmt.condition)
            _walk_statement(stmt.body)
            if stmt.increment is not None:
                _walk_statement(stmt.increment)
            type_scopes.pop()
            path_scopes.pop()
            return
        if isinstance(stmt, FuncDecl):
            type_scopes.append({})
            path_scopes.append({})
            for ptype, pname in stmt.params or []:
                decl_type = _normalize_decl_type(ptype)
                _declare(pname, decl_type, None if _is_component_type(decl_type) else None)
            if stmt.body is not None:
                _walk_statement(stmt.body)
            type_scopes.pop()
            path_scopes.pop()
            return
        if isinstance(stmt, Return):
            if stmt.value is not None:
                _walk_expr(stmt.value)
            return
        if isinstance(stmt, VarDecl):
            if stmt.value is not None:
                if isinstance(stmt.value, Call):
                    _handle_constructor_call(stmt.value, stmt.name)
                    if isinstance(stmt.value.func, MemberAccess):
                        _walk_expr(stmt.value.func.obj)
                    for arg in stmt.value.args or []:
                        _walk_expr(arg)
                else:
                    _walk_expr(stmt.value)
            decl_type = getattr(stmt, "inferred_type", None) or _normalize_decl_type(stmt.vartype)
            path = None
            if _is_component_type(decl_type) and stmt.value is not None:
                path, _ = _resolve_component_path(stmt.value, path_scopes)
            _declare(stmt.name, decl_type, path)
            return
        if isinstance(stmt, Assign):
            if stmt.value is not None:
                if isinstance(stmt.value, Call):
                    _handle_constructor_call(stmt.value, stmt.name if isinstance(stmt.name, Var) else None)
                    if isinstance(stmt.value.func, MemberAccess):
                        _walk_expr(stmt.value.func.obj)
                    for arg in stmt.value.args or []:
                        _walk_expr(arg)
                else:
                    _walk_expr(stmt.value)
            if isinstance(stmt.name, Var):
                var_type = _lookup_type(stmt.name.name)
                if _is_component_type(var_type):
                    path, _ = _resolve_component_path(stmt.value, path_scopes)
                    _set_path(stmt.name.name, path)
            return
        if isinstance(stmt, AugAssign):
            if stmt.value is not None:
                _walk_expr(stmt.value)
            return

        _walk_expr(stmt)

    for stmt in program.statements or []:
        _walk_statement(stmt)

    return errors, flags


def validate_instantiated_component_functions(component_tree, interfaces):
    """
    Ensure that every component instance in the Robot tree has concrete function bodies.
    """
    errors = []

    if not component_tree:
        return errors

    for path, node in component_tree["nodes"].items():
        comp_type = node.get("type")
        iface = interfaces.get(comp_type)
        if not iface:
            continue
        missing = [fname for fname, finfo in iface.get("funcs", {}).items() if not finfo.get("has_body")]
        if missing:
            missing.sort()
            missing_list = ", ".join(missing)
            errors.append(
                f"component instance '{path}' of type '{comp_type}' is missing implementations for: {missing_list}"
            )

    return errors


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
                is_subscription = pname in node.get("subscriptions", {})
                if is_subscription:
                    decl = VarDecl(ptype, f"{path}.{pname}", None, True)
                    setattr(decl, "force_none_init", True)
                    comp_params.append(decl)
                    continue
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
