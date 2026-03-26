import os
import importlib.util
from typing import List, Tuple

import ast_nodes as ast


Instr = Tuple[str, ...] # instruction is a tuple of strings and then somtimes numbers. (Ex. ("PUSH_INT", 42) or ("ADD",) )
function_table = {}  # name -> start index
RETURN_TYPE_STACK = []
CLASS_NAMES = set()
COMPONENT_BASES = set()
COMPONENT_INSTANCE_PATHS = set()
LOOP_STACK = []  # stack of {"breaks": [idx], "continues": [idx]}

def _strip_unit_type(typ):
    if not isinstance(typ, str):
        return typ
    if typ.startswith(("array<", "dict<", "component:", "class:")):
        return typ
    if "::" in typ:
        return typ.split("::", 1)[0]
    return typ

def _flatten_member_access(node):
    """Return list of identifiers for MemberAccess chain, or None if not pure identifiers."""
    parts = []
    cur = node
    while isinstance(cur, ast.MemberAccess):
        parts.insert(0, cur.attr)
        cur = cur.obj
    if isinstance(cur, ast.Var):
        parts.insert(0, cur.name)
        return parts
    return None

#This returns a List of instructions (bytecode) from the AST, and will give them to the Stack VM.
def compile_program(node: ast.Program, printBytecode = False, component_functions=None, component_params=None, class_functions=None, class_interfaces=None) -> List[Instr]:
    code = []
    function_table.clear()
    global CLASS_NAMES, COMPONENT_BASES, COMPONENT_INSTANCE_PATHS, LOOP_STACK
    CLASS_NAMES = set(class_interfaces.keys()) if class_interfaces else set()
    COMPONENT_BASES = set()
    COMPONENT_INSTANCE_PATHS = set()
    LOOP_STACK = []
    for decl in component_params or []:
        if isinstance(decl, ast.VarDecl) and isinstance(decl.name, str):
            base = decl.name.split(".",1)[0]
            COMPONENT_BASES.add(base)
            if isinstance(decl.value, ast.StringLiteral) and decl.value.value == decl.name:
                COMPONENT_INSTANCE_PATHS.add(decl.name)
    if component_functions:
        for fn in component_functions:
            if isinstance(fn, ast.FuncDecl):
                base = fn.name.split(".",1)[0]
                COMPONENT_BASES.add(base)

    # Reserve space for a JUMP over all function definitions
    code.append(("JUMP", None))  # placeholder

    # Compile class functions (methods/ctors)
    for func in class_functions or []:
        compile_node(func, code)

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
            compile_statement(stmt, code)

    code.append(("HALT",))
    if printBytecode:
        print_bytecode(code)
    return code


def compile_statement(node, code: List[Instr]):
    """Compile a statement, discarding expression results."""
    expr_nodes = (
        ast.NumberLiteral,
        ast.StringLiteral,
        ast.BooleanLiteral,
        ast.UnitTag,
        ast.ArrayLiteral,
        ast.DictLiteral,
        ast.ArrayAccess,
        ast.BinaryOp,
        ast.UnaryOp,
        ast.Var,
        ast.MemberAccess,
        ast.Call,
    )
    compile_node(node, code)
    if isinstance(node, expr_nodes):
        code.append(("POP",))


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

        case ast.UnitTag(expr, unit):
            compile_node(expr, code)

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
                if getattr(node, "force_none_init", False):
                    code.append(("PUSH_NONE",))
                    code.append(("DECLARE", name, vartype, readonly, True))
                    return
                # -------- DEFAULT INITIALIZATION --------

                # Add support for array types like "array<int>"
                if isinstance(vartype, str) and vartype.startswith("array<") and vartype.endswith(">"):
                    code.append(("PUSH_EMPTY_ARRAY",))

                # Detect dictionary types: starts with dict<...>
                elif isinstance(vartype, str) and vartype.startswith("dict<"):
                    code.append(("PUSH_EMPTY_DICT",))
                    
                # Primitive defaults
                else:
                    base_type = _strip_unit_type(vartype)
                    match base_type:
                        case "int" | "float":
                            code.append(("PUSH_INT", 0))
                        case "bool":
                            code.append(("PUSH_BOOL", False))
                        case "string":
                            code.append(("PUSH_STR", ""))
                        case "void":
                            raise ValueError("Variables cannot be of type void")
                        case _:# For user-defined types or unsupported types
                            code.append(("PUSH_NONE",))
            
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
                case "MOD":
                    code.append(("MOD",))
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
            if isinstance(name_node, ast.MemberAccess):
                # obj.field = value
                compile_node(value, code)
                compile_node(name_node.obj, code)
                code.append(("SET_FIELD", name_node.attr))
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
                target_type = getattr(name_node, "inferred_type", None)
                base_type = _strip_unit_type(target_type)
                if base_type == "int":
                    code.append(("CAST_INT",))
                elif base_type == "float":
                    code.append(("CAST_FLOAT",))
                # VM: pops value, index, container — sets and pushes nothing
                code.append(("INDEX_SET",))
                return

            raise NotImplementedError("Unsupported LHS in assignment")

        case ast.AugAssign(name_node, op, value):
            op_map = {
                "PLUS": "ADD",
                "MINUS": "SUB",
                "MUL": "MUL",
                "DIV": "DIV",
                "MOD": "MOD",
            }
            if op not in op_map:
                raise NotImplementedError(f"Compound operator not implemented: {op}")
            op_instr = op_map[op]

            if isinstance(name_node, ast.Var):
                code.append(("LOAD", name_node.name))
                compile_node(value, code)
                code.append((op_instr,))
                code.append(("STORE", name_node.name))
                return

            if isinstance(name_node, ast.MemberAccess):
                # obj.field += value
                compile_node(name_node.obj, code)
                code.append(("DUP",))
                code.append(("GET_FIELD", name_node.attr))
                compile_node(value, code)
                code.append((op_instr,))
                code.append(("SWAP",))
                code.append(("SET_FIELD", name_node.attr))
                return

            if isinstance(name_node, ast.ArrayAccess):
                # arr[idx] += value (array or dict)
                compile_node(name_node.array, code)
                compile_node(name_node.index, code)
                code.append(("DUP2",))
                code.append(("INDEX_GET",))
                compile_node(value, code)
                code.append((op_instr,))
                target_type = getattr(name_node, "inferred_type", None)
                base_type = _strip_unit_type(target_type)
                if base_type == "int":
                    code.append(("CAST_INT",))
                elif base_type == "float":
                    code.append(("CAST_FLOAT",))
                code.append(("INDEX_SET",))
                return

            raise NotImplementedError("Unsupported LHS in compound assignment")

        case ast.Var(name):
            """Access a variable or module/component member."""
            code.append(("LOAD", name))
        
        case ast.MemberAccess(obj, attr):
            parts = _flatten_member_access(ast.MemberAccess(obj, attr))
            if parts and parts[0] in COMPONENT_BASES:
                code.append(("LOAD", ".".join(parts)))
            else:
                compile_node(obj, code)
                code.append(("GET_FIELD", attr))
        
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
            RETURN_TYPE_STACK.append(return_type)

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
            RETURN_TYPE_STACK.pop()
            return

        case ast.Return(value):
            # Compile the return value onto the stack
            if value is not None:
                compile_node(value, code)
                if RETURN_TYPE_STACK:
                    ret_type = RETURN_TYPE_STACK[-1]
                    base_ret = _strip_unit_type(ret_type)
                    if base_ret == "int":
                        code.append(("CAST_INT",))
                    elif base_ret == "float":
                        code.append(("CAST_FLOAT",))
            else:
                code.append(("PUSH_NONE",))  # placeholder for void return

            # Signal VM to return from function
            code.append(("RETURN",))
            return

        
        case ast.If(cond, then_branch, else_branch):
            compile_node(cond, code) # first compile the condition statement

            jmp_false_index = len(code) # this is the index of the below placeholder bytecode instruction so we know where to go back and fill it in later
            code.append(("JUMP_IF_FALSE", None))  # placeholder to skip then_branch to go to else_branch (The placeholder is used because we dont yet know where the else_branch to jump to is)

            compile_statement(then_branch, code) # compile the then_branch

            if else_branch: # if there is an else_branch (sometimes there isnt)
                jmp_end_index = len(code) # this is the index of the below placeholder so we know where to go back and fill it in later
                code.append(("JUMP", None))  # placeholder to skip else_branch since the then_branch was executed
                code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # now we know where to jump to for the else_branch so we go back and fill it in
                compile_statement(else_branch, code) # compile the else_branch
                code[jmp_end_index] = ("JUMP", len(code)) # now we know where to jump to after the else_branch so we go back and fill it in
            else:
                code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # (for if there is no else_branch) now we know where to jump to after the then_branch so we go back and fill it in

        case ast.While(cond, body):
            loop_start = len(code) # this is the index of the start of the loop (so we know where to jump back to)
            compile_node(cond, code) # compile the condition
            jmp_false_index = len(code) # this is the index of the below placeholder so we know where to go back and fill it in later
            code.append(("JUMP_IF_FALSE", None))  # placeholder to exit loop if condition is false
            loop_ctx = {"breaks": [], "continues": []}
            LOOP_STACK.append(loop_ctx)
            compile_statement(body, code) # compile the body of the loop
            LOOP_STACK.pop()
            code.append(("JUMP", loop_start)) # jump back to start of loop
            code[jmp_false_index] = ("JUMP_IF_FALSE", len(code)) # now we know where to jump to if the condition is false so we go back and fill it in
            loop_end = len(code)
            for idx in loop_ctx["breaks"]:
                code[idx] = ("JUMP", loop_end)
            for idx in loop_ctx["continues"]:
                code[idx] = ("JUMP", loop_start)
            return
        
        case ast.Step(body):
            loop_start = len(code)

            # Enforce update at top of every iteration
            code.append(("UPDATE",))

            loop_ctx = {"breaks": [], "continues": []}
            LOOP_STACK.append(loop_ctx)

            compile_statement(body, code)

            LOOP_STACK.pop()

            # jump back to update
            code.append(("JUMP", loop_start))

            loop_end = len(code)

            # patch breaks/continues
            for idx in loop_ctx["breaks"]:
                code[idx] = ("JUMP", loop_end)
            for idx in loop_ctx["continues"]:
                code[idx] = ("JUMP", loop_start)

            return

        case ast.For(init, cond, increment, body):
            if init is not None:
                compile_statement(init, code)

            loop_start = len(code)
            jmp_false_index = None
            if cond is not None:
                compile_node(cond, code)
                jmp_false_index = len(code)
                code.append(("JUMP_IF_FALSE", None))

            loop_ctx = {"breaks": [], "continues": []}
            LOOP_STACK.append(loop_ctx)
            compile_statement(body, code)
            LOOP_STACK.pop()

            increment_start = len(code)
            if increment is not None:
                compile_statement(increment, code)

            code.append(("JUMP", loop_start))
            loop_end = len(code)

            if jmp_false_index is not None:
                code[jmp_false_index] = ("JUMP_IF_FALSE", loop_end)

            for idx in loop_ctx["breaks"]:
                code[idx] = ("JUMP", loop_end)
            for idx in loop_ctx["continues"]:
                code[idx] = ("JUMP", increment_start)
            return

        case ast.Block(statements):
            code.append(("ENTER_SCOPE",))
            for stmt in statements:
                compile_statement(stmt, code)
            code.append(("EXIT_SCOPE",))

        case ast.Break():
            if not LOOP_STACK:
                raise TypeError("break used outside of a loop")
            code.append(("JUMP", None))
            LOOP_STACK[-1]["breaks"].append(len(code) - 1)
            return

        case ast.Continue():
            if not LOOP_STACK:
                raise TypeError("continue used outside of a loop")
            code.append(("JUMP", None))
            LOOP_STACK[-1]["continues"].append(len(code) - 1)
            return

        case ast.Call(func, args):
            """Compile a function call (top-level, module, component, class ctor, or method)."""
            if isinstance(func, ast.MemberAccess):
                if func.attr == "match":
                    if len(args) != 1 or not isinstance(args[0], ast.Var):
                        raise TypeError("match expects a single component type identifier")
                    compile_node(func.obj, code)
                    code.append(("PUSH_STR", args[0].name))
                    code.append(("MATCH_COMPONENT",))
                    return
                parts = _flatten_member_access(func)
                if parts and parts[0] in COMPONENT_BASES:
                    target_name = ".".join(parts)
                    component_path = ".".join(parts[:-1])
                    if component_path in COMPONENT_INSTANCE_PATHS:
                        compile_node(func.obj, code)
                        for arg in args:
                            compile_node(arg, code)
                        code.append(("CALL_METHOD", func.attr, len(args)))
                    else:
                        for arg in args:
                            compile_node(arg, code)
                        code.append(("CALL", target_name, len(args)))
                    return
                # class/object method
                compile_node(func.obj, code)
                for arg in args:
                    compile_node(arg, code)
                code.append(("CALL_METHOD", func.attr, len(args)))
                return

            # constructor call if func is class name (handled at runtime)
            if isinstance(func, ast.Var):
                if func.name == "type":
                    if len(args) != 1:
                        raise TypeError(f"Function 'type' expects 1 argument, got {len(args)}")
                    compile_node(args[0], code)
                    code.append(("POP",))
                    type_str = getattr(node, "type_str", "any")
                    code.append(("PUSH_STR", type_str))
                    return
                if func.name == "unit":
                    if len(args) != 1:
                        raise TypeError(f"Function 'unit' expects 1 argument, got {len(args)}")
                    compile_node(args[0], code)
                    code.append(("POP",))
                    unit_str = getattr(node, "unit_str", "unitless")
                    code.append(("PUSH_STR", unit_str))
                    return
                if func.name in CLASS_NAMES:
                    code.append(("PUSH_STR", func.name))
                    for arg in args:
                        compile_node(arg, code)
                    code.append(("NEW_CALL", len(args)))
                    return
                # regular function
                for arg in args:
                    compile_node(arg, code)
                if func.name == "print":
                    code.append(("PRINT", len(args)))
                    code.append(("PUSH_NONE",))
                elif func.name == "publish":
                    if len(args) != 3:
                        raise TypeError("publish() takes exactly 3 arguments: topic, msg_type, payload")
                    code.append(("PUBLISH",))
                    code.append(("PUSH_NONE",))
                elif func.name == "wait":
                    if len(args) != 1:
                        raise TypeError("wait() takes exactly 1 argument: seconds")
                    code.append(("WAIT",))
                    code.append(("PUSH_NONE",))
                elif func.name == "update":
                    if len(args) != 0:
                        raise TypeError("update() takes no arguments")
                    code.append(("UPDATE",))
                    code.append(("PUSH_NONE",))
                else:
                    code.append(("CALL", func.name, len(args)))
                return

            # fallback
            for arg in args:
                compile_node(arg, code)
            target_name = func.name if isinstance(func, ast.Var) else "<callable>"
            code.append(("CALL", target_name, len(args)))


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
