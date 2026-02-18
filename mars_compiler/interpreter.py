from contextlib import contextmanager
from io import StringIO
import os
import sys

from lexer import tokenize  # tokenizer from lexer.py
from parser import Parser  # parser from parser.py
from type_checker import TypeChecker  # type checker from type_checker.py
from bytecodegen import compile_program  # bytecode generator from bytecodegen.py
from vm import VM  # the stack-based virtual machine from vm.py
from configuration_check import precompile_config, validate_instantiated_component_functions, validate_instantiated_requirements
from class_validator import ClassValidator
from ast_nodes import FuncDecl, Return, Block, Var, Assign, MemberAccess, Import
from ast_visualizer import visualize  # for visualizing the AST


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
    # Precompile component configurations
    _registry, interfaces, comp_funcs, comp_params, component_tree, component_parents = precompile_config(config_dir, debug=debug)

    # Tokenize -> Parse
    tokens = tokenize(code, printTokens=debug, source_path=source_path)
    parser = Parser(tokens, source_text=code, source_path=source_path)
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
                mod_tokens = tokenize(mod_code, printTokens=debug, source_path=candidate)
                mod_parser = Parser(mod_tokens, source_text=mod_code, source_path=candidate)
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

    # Validate component implementations for instantiated Robot trees
    impl_errors = validate_instantiated_component_functions(component_tree, interfaces)
    if impl_errors:
        msg = ["Component implementation check failed:"]
        msg.extend(f"  - {err}" for err in impl_errors)
        raise SystemExit("\n".join(msg))

    # Validate requirements for instantiated classes against component args
    req_errors, req_flags = validate_instantiated_requirements(parsed_ast, component_tree, component_parents, class_interfaces)
    if req_errors:
        msg = ["Requirements check failed:"]
        msg.extend(f"  - {err}" for err in req_errors)
        if req_flags:
            msg.append("Flags:")
            msg.extend(f"  - {flag}" for flag in req_flags)
        raise SystemExit("\n".join(msg))
    if req_flags:
        print("[requirements] Flags:")
        for flag in req_flags:
            print(f"  - {flag}")

    # Visualize AST if requested
    if debug:
        _render_graphviz(visualize(parsed_ast), "ast_output")

    # Build class runtime functions and field info
    class_funcs, class_field_info = build_class_runtime(parsed_ast.classes, class_interfaces)

    # Compile to bytecode and run on VM
    bytecode = compile_program(parsed_ast, debug, component_functions=comp_funcs, component_params=comp_params, class_functions=class_funcs, class_interfaces=class_interfaces)
    vm = VM(bytecode, class_field_info=class_field_info, component_tree=component_tree, component_parents=component_parents)

    if capture_output:
        with _capture_stdout() as buf:
            vm.run()
        return buf.getvalue()

    vm.run()
    return None


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
