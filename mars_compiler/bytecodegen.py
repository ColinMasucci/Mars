import os
import importlib.util
from typing import List, Tuple
import ast_nodes as ast


Instr = Tuple[str, ...] # instruction is a tuple of strings and then somtimes numbers. (Ex. ("PUSH_INT", 42) or ("ADD",) )
function_table = {}  # name -> start index

#This returns a List of instructions (bytecode) from the AST, and will give them to the Stack VM.
def compile_program(node: ast.Program, printBytecode = False, component_functions=None, component_params=None) -> List[Instr]:
    code = []
    function_table.clear()

    # Reserve space for a JUMP over all function definitions
    code.append(("JUMP", None))  # placeholder

    # Compile component functions first (they are already namespaced)
    for func in component_functions or []:
        compile_node(func, code)

    # Compile function declarations first
    for stmt in node.statements:
        if isinstance(stmt, ast.FuncDecl):
            compile_node(stmt, code)

    # Mark the start of the main program
    main_start = len(code)

    # Patch the jump
    code[0] = ("JUMP", main_start)

    # Emit component parameter declarations as globals
    for decl in component_params or []:
        compile_node(decl, code)

    # Compile all NON-function statements
    for stmt in node.statements:
        if not isinstance(stmt, ast.FuncDecl):
            compile_node(stmt, code)

    code.append(("HALT",))
    if printBytecode:
        print_bytecode(code)
    return code


def compile_node(node, code: List[Instr]):
    """Emit bytecode for a single AST node appending into code list."""
    match node:
        case ast.NumberLiteral(value):
            if isinstance(value, int):
                code.append(("PUSH_INT", value))
            else:
                code.append(("PUSH_FLOAT", float(value)))

        case ast.StringLiteral(value):
            code.append(("PUSH_STR", value))
        
        case ast.BooleanLiteral(value):
            code.append(("PUSH_BOOL", value))

        case ast.ArrayLiteral(elements):
            # compile elements in-order (left-to-right)
            for elem in elements:
                compile_node(elem, code)
            # BUILD_ARRAY will pop N items and push a single array object (preserving element order)
            code.append(("BUILD_ARRAY", len(elements)))
        
        case ast.DictLiteral(pairs):
            # compile key/value pairs in-order (left-to-right)
            # push key then value for each pair
            for key, value in pairs:
                compile_node(key, code)
                compile_node(value, code)
            # BUILD_DICT will pop 2*N items (value, key pairs) and push a dict object
            code.append(("BUILD_DICT", len(pairs)))
        
        case ast.VarDecl(vartype, name, value, readonly):
            if value is not None: # if there is an initializer expression
                compile_node(value, code)
            else:
                # -------- DEFAULT INITIALIZATION --------

                # Add support for array types like "array<int>"
                if isinstance(vartype, str) and vartype.startswith("array<") and vartype.endswith(">"):
                    code.append(("PUSH_EMPTY_ARRAY",))

                # Detect dictionary types: starts with dict<...>
                elif isinstance(vartype, str) and vartype.startswith("dict<"):
                    code.append(("PUSH_EMPTY_DICT",))
                    
                # Primitive defaults
                else:
                    match vartype:
                        case "int" | "float":
                            code.append(("PUSH_INT", 0))
                        case "bool":
                            code.append(("PUSH_BOOL", False))
                        case "string":
                            code.append(("PUSH_STR", ""))
                        case "void":
                            raise ValueError("Variables cannot be of type void")
                        case _:# For user-defined types or unsupported types
                            raise ValueError(f"Unknown vartype '{vartype}' in VarDecl")
            
            # Finally declare the variable
            code.append(("DECLARE", name, vartype, readonly))

        case ast.BinaryOp(op, left, right):
            # compile left then right (stack-based order)
            compile_node(left, code)
            compile_node(right, code)
            match op:
                case "PLUS":
                    code.append(("ADD",))
                case "MINUS":
                    code.append(("SUB",))
                case "MUL":
                    code.append(("MUL",))
                case "DIV":
                    code.append(("DIV",))
                case "POW":
                    code.append(("POW",))
                case "AND":
                    code.append(("AND",))
                case "OR":
                    code.append(("OR",))
                case "LT":
                    code.append(("LT",))
                case "GT":
                    code.append(("GT",))
                case "LEQ":
                    code.append(("LEQ",))
                case "GEQ":
                    code.append(("GEQ",))
                case "EQ":
                    code.append(("EQ",))
                case "NEQ":
                    code.append(("NEQ",))
                case _:
                    raise NotImplementedError(op)
                
        case ast.UnaryOp(op, operand):
            match op:
                case "NEGATE":    # unary minus
                    compile_node(operand, code)
                    code.append(("NEGATE",))
                case "BANG":      # logical not
                    compile_node(operand, code)
                    code.append(("NOT",))
                case "INC":
                    if isinstance(operand, ast.Var):
                        # directly tell VM which variable to increment
                        code.append(("INC", operand.name))
                    else:
                        raise NotImplementedError("INC can only be applied to variables")
                case "DEC":
                    if isinstance(operand, ast.Var):
                        code.append(("DEC", operand.name))
                    else:
                        raise NotImplementedError("DEC can only be applied to variables")
                case _:
                    raise NotImplementedError(f"Unary operator not implemented: {op}")


        case ast.Assign(name_node, value):
            # Assignment to a plain variable (Var)
            if isinstance(name_node, ast.Var):
                compile_node(value, code)
                # store expects: <value> on top, then STORE will pop it and store into name
                code.append(("STORE", name_node.name))
                return

            # Assignment to a dotted field like a.b.c (Split like "a.b.c" → base="a", fields=["b","c"])
            if isinstance(name_node, str) and "." in name_node:
                parts = name_node.split(".")
                base = parts[0]
                fields = parts[1:]
                # compile value then set through fields
                compile_node(value, code)
                code.append(("LOAD", base))
                for f in fields[:-1]:
                    code.append(("GET_FIELD", f))
                code.append(("SET_FIELD", fields[-1]))
                return

            # Assignment to array or dictionary element: arr[i] = value OR dict[key] = value
            if isinstance(name_node, ast.ArrayAccess):
                ''' We will compile: <array>, <index>, <value> then INDEX_SET will pop value,index,array and set.
                # But to avoid temporaries, compile array and index first, then compile value.
                # This order yields stack: [..., array, index, value]'''
                # compile container expression (array or dict)
                compile_node(name_node.array, code)
                # compile index/key expression
                compile_node(name_node.index, code)
                # compile value to assign
                compile_node(value, code)
                # VM: pops value, index, container — sets and pushes nothing
                code.append(("INDEX_SET",))
                return

            raise NotImplementedError("Unsupported LHS in assignment")

        case ast.Var(name):
            """Access a variable or module/component member."""
            code.append(("LOAD", name))
        
        case ast.ArrayAccess(array_expr, index_expr):
            # compile array/dict expression
            compile_node(array_expr, code)
            # compile index/key expression
            compile_node(index_expr, code)
            # VM will decide array vs dict indexing
            code.append(("INDEX_GET",))
            return

        case ast.FuncDecl(return_type, name, params, body):
            # Record the function start
            func_start = len(code)
            function_table[name] = func_start

            # Emit label for VM to know where function starts
            code.append(("FUNC_BEGIN", name, len(params)))

            # Push parameters into local variables
            for ptype, pname in params:
                code.append(("DECLARE", pname, ptype))

            # Compile function body
            compile_node(body, code)
            # Ensure function returns
            if not code or code[-1][0] != "RETURN":
                code.append(("PUSH_NONE",))
                code.append(("RETURN",))

            # Ensure function always returns; for void functions, push None
            code.append(("FUNC_END", name))
            return

        case ast.Return(value):
            # Compile the return value onto the stack
            if value is not None:
                compile_node(value, code)
            else:
                code.append(("PUSH_NONE",))  # placeholder for void return

            # Signal VM to return from function
            code.append(("RETURN",))
            return

        
        case ast.If(cond, then_branch, else_branch):
            compile_node(cond, code) # first compile the condition statement

            jmp_false_index = len(code) # this is the index of the below placeholder bytecode instruction so we know where to go back and fill it in later
            code.append(("JUMP_IF_FALSE", None))  # placeholder to skip then_branch to go to else_branch (The placeholder is used because we dont yet know where the else_branch to jump to is)

            compile_node(then_branch, code) # compile the then_branch

            if else_branch: # if there is an else_branch (sometimes there isnt)
                jmp_end_index = len(code) # this is the index of the below placeholder so we know where to go back and fill it in later
                code.append(("JUMP", None))  # placeholder to skip else_branch since the then_branch was executed
                code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # now we know where to jump to for the else_branch so we go back and fill it in
                compile_node(else_branch, code) # compile the else_branch
                code[jmp_end_index] = ("JUMP", len(code)) # now we know where to jump to after the else_branch so we go back and fill it in
            else:
                code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # (for if there is no else_branch) now we know where to jump to after the then_branch so we go back and fill it in

        case ast.While(cond, body):
            loop_start = len(code) # this is the index of the start of the loop (so we know where to jump back to)
            compile_node(cond, code) # compile the condition
            jmp_false_index = len(code) # this is the index of the below placeholder so we know where to go back and fill it in later
            code.append(("JUMP_IF_FALSE", None))  # placeholder to exit loop if condition is false
            compile_node(body, code) # compile the body of the loop
            code.append(("JUMP", loop_start)) # jump back to start of loop
            code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # now we know where to jump to if the condition is false so we go back and fill it in

        case ast.Block(statements):
            for stmt in statements:
                compile_node(stmt, code)

        case ast.Call(func, args):
            """Compile a function call (top-level, module, or component)."""
            # Compile arguments
            for arg in args:
                compile_node(arg, code)

            # Emit appropriate opcode
            if isinstance(func, ast.Var) and func.name == "print":
                code.append(("PRINT", len(args)))       # special PRINT opcode
            else:
                target_name = func.name if isinstance(func, ast.Var) else "<callable>"
                code.append(("CALL", target_name, len(args)))  # normal CALL


        case ast.Import(module_name):
            """Compile-time check that module exists in builtins."""
            module_path = os.path.join("builtins", f"{module_name}.py")
            if os.path.exists(module_path):
                # Dynamically load module just to validate functions/constants exist
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            # Emit IMPORT opcode for the VM (no-op for components)
            code.append(("IMPORT", module_name))


        case _:
            raise TypeError(f"Unknown AST node {node}")

def print_bytecode(bytecode: List[Instr]):
    print("Generated Bytecode:")
    for i, instr in enumerate(bytecode):
        print(f"{i:04}: {instr}")
    print("\n")
