from contextlib import contextmanager
from io import StringIO
import os
import sys

from lexer import tokenize  # tokenizer from lexer.py
from parser import Parser  # parser from parser.py
from type_checker import TypeChecker  # type checker from type_checker.py
from bytecodegen import compile_program  # bytecode generator from bytecodegen.py
from vm import VM  # the stack-based virtual machine from vm.py
from component_registry import ComponentRegistry
from component_validator import ComponentValidator, ComponentValidationError
from class_validator import ClassValidator
from ast_nodes import FuncDecl, VarDecl, Call, Return, Block, Var, ComponentDef, Assign, MemberAccess, Import
from ast_visualizer import visualize  # for visualizing the AST
from component_visualizer import visualize_components


def interpret_code_from_file(file_path: str, config_dir: str = "config", debug: bool = False):
    """Run a .mars program from disk through the full pipeline."""
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    return _interpret(code, config_dir=config_dir, debug=debug, capture_output=False, source_path=file_path)


def interpret_code_from_string(code: str, config_dir: str = "config", debug: bool = False):
    """
    Run code provided as a string. Used by tests.
    Returns captured stdout from the VM execution.
    """
    return _interpret(code, config_dir=config_dir, debug=debug, capture_output=True, source_path=None)


def _interpret(code: str, config_dir: str, debug: bool, capture_output: bool, source_path: str | None):
    registry = ComponentRegistry()
    interfaces = load_marsc_files(config_dir, registry, debug=debug)

    # Tokenize -> Parse
    tokens = tokenize(code, debug)
    parser = Parser(tokens)
    parsed_ast = parser.parse(debug)

    # Load classes from imported .mars files (single-class modules)
    base_dir = os.path.dirname(source_path) if source_path else "."
    imported_classes = []
    module_class_alias = {}
    for stmt in parsed_ast.statements:
        if isinstance(stmt, Import):
            module = stmt.module
            candidate = os.path.join(base_dir, f"{module}.mars")
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    mod_code = f.read()
                mod_tokens = tokenize(mod_code, debug)
                mod_parser = Parser(mod_tokens)
                mod_ast = mod_parser.parse(debug)
                if not mod_ast.classes:
                    raise Exception(f"Imported module '{module}' contains no class definition")
                if len(mod_ast.classes) > 1:
                    raise Exception(f"Imported module '{module}' must contain exactly one class")
                imported_classes.extend(mod_ast.classes)
                module_class_alias[module] = mod_ast.classes[0].name

    if imported_classes:
        parsed_ast.classes = (parsed_ast.classes or []) + imported_classes

    # Validate classes
    class_interfaces = {}
    if parsed_ast.classes:
        validator = ClassValidator(parsed_ast.classes)
        class_interfaces = validator.validate()
        for mod, cls_name in module_class_alias.items():
            if cls_name in class_interfaces:
                class_interfaces[mod] = class_interfaces[cls_name]

    # Type check
    type_checker = TypeChecker(component_interfaces=interfaces, class_interfaces=class_interfaces)
    type_checker.check(parsed_ast)

    # Visualize AST if requested
    if debug:
        _render_graphviz(visualize(parsed_ast), "ast_output")

    # Build runtime component params and functions
    comp_funcs, comp_params = build_component_runtime(registry, interfaces)
    class_funcs, class_field_info = build_class_runtime(parsed_ast.classes, class_interfaces)

    # Compile to bytecode and run on VM
    bytecode = compile_program(parsed_ast, debug, component_functions=comp_funcs, component_params=comp_params, class_functions=class_funcs, class_interfaces=class_interfaces)
    vm = VM(bytecode, class_field_info=class_field_info)

    if capture_output:
        with _capture_stdout() as buf:
            vm.run()
        return buf.getvalue()

    vm.run()
    return None


def load_marsc_files(directory, registry, debug: bool = False):
    # built-in base robot component (empty)
    components = [ComponentDef("robot", None, [], [], [])]
    for filename in os.listdir(directory):
        if filename.endswith(".marsc"):
            with open(os.path.join(directory, filename)) as f:
                code = f.read()
            tokens = tokenize(code)
            parser = Parser(tokens)
            ast = parser.parse()
            for comp in ast.components:
                if comp.name == "robot":
                    raise ComponentValidationError("Defining 'robot' is not allowed; it is a built-in base component.")
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

        if debug:
            _render_graphviz(visualize_components(components), "component_tree")

        for component in components:
            registry.register(component)
        return interfaces

    return {}


def build_class_runtime(classes, class_interfaces):
    """
    Convert ClassDecls into runtime functions and field metadata for the VM.
    - Methods/ctors are namespaced as Class.method and Class.__ctor
    - Implicit 'this' parameter is prepended so CALL_METHOD/NEW_CALL can bind it
    - Field defaults are applied inside the constructor via assignments to this.field
    """
    class_funcs = []
    class_field_info = {}

    for cls in classes or []:
        defaults = []
        field_map = {}
        for f in cls.fields:
            field_map[f.name] = {"readonly": f.readonly, "default": f.value, "type": f.vartype}
            if f.value is not None:
                defaults.append(Assign(MemberAccess(Var("this"), f.name), f.value))
        class_field_info[cls.name] = field_map

        # Constructor (always emit one, even if user omitted the body)
        ctor_params = [(cls.name, "this")]
        if cls.constructor:
            ctor_params += cls.constructor.params
            ctor_body_stmts = list(defaults)
            if cls.constructor.body:
                if isinstance(cls.constructor.body, Block):
                    ctor_body_stmts.extend(cls.constructor.body.statements)
                else:
                    ctor_body_stmts.append(cls.constructor.body)
        else:
            ctor_body_stmts = list(defaults)
        ctor_body_stmts.append(Return(Var("this")))
        class_funcs.append(FuncDecl(cls.name, f"{cls.name}.__ctor", ctor_params, Block(ctor_body_stmts)))

        # Methods
        for m in cls.methods:
            if m.body is None:
                continue
            params = [(cls.name, "this")] + m.params
            class_funcs.append(FuncDecl(m.return_type, f"{cls.name}.{m.name}", params, m.body))

    return class_funcs, class_field_info


def build_component_runtime(registry, interfaces):
    """
    Build lists of FuncDecl and VarDecl for component runtime exposure.
    - Component params become readonly globals: Component.param
    - Subcomponent bindings/params get aliases: sub.param and Parent.sub.param
    - Component functions get namespaced as Component.func
    - Subcomponent functions get aliases: sub.func and Parent.sub.func
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

            # Alias variables for the subcomponent instance itself
            comp_params.append(VarDecl(sub.type_name, sub.name, None, True))
            comp_params.append(VarDecl(sub.type_name, f"{comp.name}.{sub.name}", None, True))

            # Param aliases for subcomponent instance
            for pname, ptype in sub_params_types.items():
                val = bindings.get(pname, default_map.get(pname))
                comp_params.append(VarDecl(ptype, f"{sub.name}.{pname}", val, True))
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
                alias1 = FuncDecl(finfo.get("return"), f"{sub.name}.{fname}", params, Block(body_stmts))
                alias2 = FuncDecl(finfo.get("return"), f"{comp.name}.{sub.name}.{fname}", params, Block(body_stmts))
                comp_funcs.extend([alias1, alias2])

    return comp_funcs, comp_params


def _render_graphviz(dot_obj, filename):
    """Render a graphviz object but do not fail the run if Graphviz is missing."""
    try:
        return dot_obj.render(filename, cleanup=True)
    except Exception as e:
        print(f"[debug] Skipping graph render for {filename}: {e}")
        return None


@contextmanager
def _capture_stdout():
    """Context manager to capture stdout, used for tests."""
    old_stdout = sys.stdout
    buf = StringIO()
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old_stdout
