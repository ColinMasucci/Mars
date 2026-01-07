from lexer import tokenize #tokenizer from lexer.py
from parser import Parser #parser from parser.py
from type_checker import TypeChecker #type checker from type_checker.py
from bytecodegen import compile_program #bytecode generator from bytecodegen.py
from vm import VM #the stack-based virtual machine from vm.py
from component_registry import ComponentRegistry
from component_validator import ComponentValidator, ComponentValidationError
from ast_nodes import FuncDecl, VarDecl, Call, Return, Block, Var
import os


from ast_visualizer import visualize #for visualizing the AST
from component_visualizer import visualize_components


def interpret_code_from_file(file_path: str, print_debug: bool = False):
    
    # Access and read the test file
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()


    registry = ComponentRegistry()
    interfaces = load_marsc_files("config", registry)
    print("=== COMPONENT REGISTRY ===")
    for name, comp in registry.components.items():
        print(name, "->", comp)
    print("==========================")
    motor = registry.get("robot")
    print(motor.name)
    print(motor.parent)
    print(motor.subcomponents)
    print(motor.parameters)
    print(motor.functions)
    motor = registry.get("chassis")
    print(motor.name)
    print(motor.parent)
    print(motor.subcomponents)
    print(motor.parameters)
    print(motor.functions)
    

    #1. tokenize the input code
    tokens = tokenize(code, print_debug)

    #2. Parse the tokens into an AST
    parser = Parser(tokens)
    parsed_ast = parser.parse(print_debug)

    # now compile main program
    #3. Type check the AST
    type_checker = TypeChecker(component_interfaces=interfaces)    
    try:
        type_checker.check(parsed_ast)
        print("Static type checking passed\n")
    except TypeError as e:
        print(f"Type Error: {e}")
        exit(1)  # stop execution before codegen if types are invalid

    #(Optional) Visualize AST
    if print_debug:
        dot = visualize(parsed_ast)
        output_path = dot.render("ast_output", cleanup=True)
        print(f"AST visualization saved as {output_path} \n")

    # Build runtime component params and functions
    comp_funcs, comp_params = build_component_runtime(registry, interfaces)

    #4. Compile the AST into bytecode
    bytecode1 = compile_program(parsed_ast, print_debug, component_functions=comp_funcs, component_params=comp_params)

    #5. Run the bytecode on the VM
    vm1 = VM(bytecode1) #create VM instance with the bytecode
    vm1.run() #run the bytecode on the VM


#Useful for running code from strings (like in tests)
def interpret_code_from_string(code: str):
    tokens = tokenize(code)
    parser = Parser(tokens)
    ast = parser.parse()
    type_checker = TypeChecker()
    type_checker.check(ast)
    bytecode = compile_program(ast)
    vm = VM(bytecode)

    # Capture output
    from io import StringIO
    import sys

    old_stdout = sys.stdout
    sys.stdout = StringIO()

    vm.run()

    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    return output


def load_marsc_files(directory, registry):
    components = []
    for filename in os.listdir(directory):
        if filename.endswith(".marsc"):
            with open(os.path.join(directory, filename)) as f:
                code = f.read()
            tokens = tokenize(code)
            parser = Parser(tokens)
            ast = parser.parse()
            components.extend(ast.components)

    if components:
        validator = ComponentValidator(components)
        try:
            interfaces = validator.validate()
        except ComponentValidationError as e:
            raise Exception(f"Component validation failed: {e}")

        # Type-check component functions with component-aware scope
        tc = TypeChecker(component_interfaces=interfaces)
        tc.check_components(components)

        # Visualize component tree
        dot = visualize_components(components)
        output_path = dot.render("component_tree", cleanup=True)
        print(f"Component tree visualization saved as {output_path}")

        for component in components:
            registry.register(component)
        return interfaces

    return {}


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
