import os

from lexer import tokenize
from parser import Parser
from type_checker import TypeChecker
from component_registry import ComponentRegistry
from component_validator import ComponentValidator, ComponentValidationError
from component_visualizer import visualize_components
from ast_nodes import ComponentDef, FuncDecl, VarDecl, Call, Return, Block, Var


def precompile_config(config_dir: str, debug: bool = False):
    """
    Parse and validate component config and prepare runtime metadata.
    Returns (registry, interfaces, comp_funcs, comp_params).
    """
    registry = ComponentRegistry()
    interfaces = load_marsc_files(config_dir, registry, debug=debug)
    comp_funcs, comp_params = build_component_runtime(registry, interfaces)
    return registry, interfaces, comp_funcs, comp_params


def load_marsc_files(directory, registry, debug: bool = False):
    # built-in base Robot component (empty)
    components = [ComponentDef("Robot", None, [], [], [])]
    for filename in os.listdir(directory):
        if filename.endswith(".marsc"):
            with open(os.path.join(directory, filename)) as f:
                code = f.read()
            tokens = tokenize(code)
            parser = Parser(tokens)
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


def build_component_runtime(registry, interfaces):
    """
    Build lists of FuncDecl and VarDecl for component runtime exposure.
    - Component params become readonly globals: Component.param
    - Component functions get namespaced as Component.func
    - Subcomponent bindings/params get aliases: Parent.sub.param
    - Subcomponent functions get aliases: Parent.sub.func
    """
    comp_funcs = []
    comp_params = []

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

    for comp in registry.components.values():
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

            # Alias variable for the subcomponent instance (namespaced only)
            comp_params.append(VarDecl(sub.type_name, f"{comp.name}.{sub.name}", None, True))

            # Param aliases for subcomponent instance
            for pname, ptype in sub_params_types.items():
                val = bindings.get(pname, default_map.get(pname))
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
