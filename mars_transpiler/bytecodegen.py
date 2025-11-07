from typing import List, Tuple
import ast_nodes as ast

Instr = Tuple[str, ...] # instruction is a tuple of strings and then somtimes numbers. (Ex. ("PUSH_INT", 42) or ("ADD",) )

#This returns a List of instructions (bytecode) from the AST, and will give them to the Stack VM.
def compile_program(node: ast.Program, printBytecode = False) -> List[Instr]:
    code = []
    for stmt in node.statements:
        compile_node(stmt, code)
    code.append(("HALT",)) # this is for the ending of the program (so we know when to stop)
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
                case _:
                    raise NotImplementedError(op)

        case ast.Assign(name, value):
            compile_node(value, code)
            code.append(("STORE", name))

        case ast.Var(name):
            code.append(("LOAD", name))
        
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
            # compile each argument in order (so last argument ends up on top of stack)
            for arg in args:
                compile_node(arg, code)
            # currently only support 'print' as builtin
            if isinstance(func, ast.Var) and func.name == "print":
                code.append(("PRINT", len(args)))  # PUSH all args, then PRINT n args
            else:
                raise NotImplementedError(f"Function call not implemented: {func}")

        case _:
            raise TypeError(f"Unknown AST node {node}")

def print_bytecode(bytecode: List[Instr]):
    print("Generated Bytecode:")
    for i, instr in enumerate(bytecode):
        print(f"{i:04}: {instr}")
    print("\n")
