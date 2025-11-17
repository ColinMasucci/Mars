import os
import importlib.util
from typing import List, Tuple
import ast_nodes as ast


Instr = Tuple[str, ...] # instruction is a tuple of strings and then somtimes numbers. (Ex. ("PUSH_INT", 42) or ("ADD",) )
function_table = {}  # name -> start index

#This returns a List of instructions (bytecode) from the AST, and will give them to the Stack VM.
def compile_program(node: ast.Program, printBytecode = False) -> List[Instr]:
    code = []

    # Reserve space for a JUMP over all function definitions
    code.append(("JUMP", None))  # placeholder

    # Compile function declarations first
    for stmt in node.statements:
        if isinstance(stmt, ast.FuncDecl):
            compile_node(stmt, code)

    # Mark the start of the main program
    main_start = len(code)

    # Patch the jump
    code[0] = ("JUMP", main_start)

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
        
        case ast.VarDecl(vartype, name, value):
            if value is not None:
                compile_node(value, code)
            else:
                match vartype:
                    case "int" | "float":
                        code.append(("PUSH_INT", 0))
                    case "bool":
                        code.append(("PUSH_BOOL", False))
                    case "string":
                        code.append(("PUSH_STR", ""))
                    case _:
                        raise ValueError(f"Unknown vartype '{vartype}' in VarDecl")
            code.append(("DECLARE", name, vartype))

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


        case ast.Assign(name, value):
            compile_node(value, code)
            if "." in name:
                # Split like "a.b.c" → base="a", fields=["b","c"]
                parts = name.split(".")
                base = parts[0]
                fields = parts[1:]
                code.append(("LOAD", base))
                for f in fields[:-1]:
                    code.append(("GET_FIELD", f))
                code.append(("SET_FIELD", fields[-1]))
            else:
                code.append(("STORE", name))

        case ast.Var(name):
            """Access a variable or module member."""
            parts = name.split(".")
            if len(parts) == 2:
                module_name, member_name = parts
                # Check module exists
                module_path = os.path.join("builtins", f"{module_name}.py")
                if not os.path.exists(module_path):
                    raise TypeError(f"Module '{module_name}' not found")
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                funcs_dict = getattr(mod, f"{module_name.upper()}_FUNCS", {})
                if member_name not in funcs_dict:
                    raise TypeError(f"Module '{module_name}' has no member '{member_name}'")
            # Finally, emit the LOAD instruction for the VM
            code.append(("LOAD", name))

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
            """Compile a function call (top-level or module function)."""
            if isinstance(func, ast.Var):
                parts = func.name.split(".")
                if len(parts) == 2:
                    # Module function: compile-time check
                    module_name, func_name = parts
                    module_path = os.path.join("builtins", f"{module_name}.py")
                    if not os.path.exists(module_path):
                        raise TypeError(f"Module '{module_name}' not found")
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    funcs_dict = getattr(mod, f"{module_name.upper()}_FUNCS", {})
                    if func_name not in funcs_dict:
                        raise TypeError(f"Module '{module_name}' has no function '{func_name}'")
                else:
                    # Top-level function
                    if func.name not in {"print"} and func.name not in function_table:
                        raise TypeError(f"Unknown function '{func.name}'")

            # Compile arguments
            for arg in args:
                compile_node(arg, code)

            # Emit appropriate opcode
            if func.name == "print":
                code.append(("PRINT", len(args)))       # special PRINT opcode
            else:
                code.append(("CALL", func.name, len(args)))  # normal CALL for module functions


        case ast.Import(module_name):
            """Compile-time check that module exists in builtins."""
            module_path = os.path.join("builtins", f"{module_name}.py")
            if not os.path.exists(module_path):
                raise TypeError(f"Module '{module_name}' not found")

            # Dynamically load module just to validate functions/constants exist
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Emit IMPORT opcode for the VM
            code.append(("IMPORT", module_name))


        case _:
            raise TypeError(f"Unknown AST node {node}")

def print_bytecode(bytecode: List[Instr]):
    print("Generated Bytecode:")
    for i, instr in enumerate(bytecode):
        print(f"{i:04}: {instr}")
    print("\n")
