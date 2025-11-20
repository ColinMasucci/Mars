from ast_nodes import ArrayAccess, ArrayLiteral, NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, If, While, VarDecl, UnaryOp, Import, Return, FuncDecl
import os
import importlib.util


class TypeChecker:
    def __init__(self):
        # Scopes: list of dicts, each dict: name -> { 'type': str or 'function', 'mutable': bool, 'info': dict }
        self.scopes = [{}]
        self._loaded_modules = {}  # cache loaded builtin modules
        self.function_return_stack = [] # stack of return types

        # pre-load built-in functions and constants (not from library)
        self._declare_symbol(
            "print",
            "function",
            mutable=False,
            info={"return": "void", "params": None}  # no type info for simplicity
        )


    def _type_from_python_obj(self, obj):
        """Map Python object -> MARS type or 'function'."""
        if callable(obj):
            if hasattr(obj, "_mars_sig"):
                
                sig = getattr(obj, "_mars_sig")
                return {"type":"function","return":sig[0],"params":sig[1]}
            return {"type":"function","return":None,"params":None}
        if isinstance(obj, bool):
            return "bool"
        if isinstance(obj, int):
            return "int"
        if isinstance(obj, float):
            return "float"
        if isinstance(obj, str):
            return "string"
        return type(obj).__name__
    
    # scope helpers
    def _current_scope(self):
        return self.scopes[-1]

    def _push_scope(self):
        self.scopes.append({})

    def _pop_scope(self):
        self.scopes.pop()

    # symbol helpers // help with: avoiding assigning vars to constants, scope, and param/return types
    def _declare_symbol(self, name, typ, mutable=True, info=None):
        scope = self._current_scope()
        if name in scope:
            raise TypeError(f"Symbol '{name}' already declared in current scope")
        scope[name] = {"type": typ, "mutable": mutable, "info": info or {}}

    def _set_symbol(self, name, typ, mutable=True, info=None):
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name] = {"type": typ, "mutable": mutable, "info": info or {}}
                return
        self._declare_symbol(name, typ, mutable, info)

    def _lookup_symbol(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _normalize_type(self, typ: str):
        # Convert parser array syntax -> type checker array syntax (e.g., int[] -> array<int>)
        # This is because parser uses int[] syntax for easier parsing, but type checker uses array<int> internally
        # We make this change because its better for the type checker to handle nested arrays (e.g., array<array<int>> vs int[][])
        if typ.endswith("[]"):
            elem_type = typ[:-2]
            return f"array<{elem_type}>"
        return typ



    def _register_module_members(self, module_name, mod):
        """Load vars & functions from library module."""
        keyname = f"{module_name.upper()}_FUNCS"
        funcs_dict = getattr(mod, keyname, {})

        for name, obj in funcs_dict.items():
            if callable(obj) and hasattr(obj, "_mars_sig"):
                ret, params = getattr(obj, "_mars_sig")
                info = {"return": ret, "params": params}
                self._declare_symbol(f"{module_name}.{name}", "function", mutable=False, info=info)
            else:
                # Not a function — treat as constant
                typ = self._type_from_python_obj(obj)
                self._declare_symbol(f"{module_name}.{name}", typ, mutable=False, info={})


        # # Optionally support a separate CONSTS mapping if library author used it
        # const_key = f"{module_name.upper()}_CONSTS"
        # consts_dict = getattr(mod, const_key, {})
        # for name, obj in consts_dict.items():
        #     full = f"{module_name}.{name}"
        #     self.symbols[full] = self._type_from_python_obj(obj)


    def check(self, node):
        match node:
            case Program(statements):
                for stmt in statements:
                    self.check(stmt)

            case Block(statements):
                self._push_scope()
                try:
                    for stmt in statements:
                        self.check(stmt)
                finally:
                    self._pop_scope()


            case VarDecl(vartype, name, value):
                vartype = self._normalize_type(vartype)   # normalize type (e.g., int[] -> array<int>)
                if name in self._current_scope():
                    raise TypeError(f"Variable '{name}' already declared")
                value_type = None
                if value is not None:
                    value_type = self.check(value)
                if value_type is not None and vartype != value_type:
                    raise TypeError(f"Type mismatch in declaration of '{name}': expected {vartype}, got {value_type}")
                self._declare_symbol(name, vartype, mutable=True, info={})
                return vartype


            case Assign(name_node, value):
                # LHS can be Var or ArrayAccess (e.g., arr[i])
                if isinstance(name_node, Var):
                    name = name_node.name
                    sym = self._lookup_symbol(name)
                    if sym is None:
                        raise TypeError(f"Assignment to undeclared variable '{name}'")
                    if sym.get("mutable") is False:
                        raise TypeError("Cannot assign to immutable symbol")
                    value_type = self.check(value)
                    expected = sym["type"]
                    if expected != value_type:
                        raise TypeError(f"Type mismatch in assignment to '{name}': expected {expected}, got {value_type}")
                    return expected

                # Assignment to an array element: ArrayAccess(array, index)
                if isinstance(name_node, ArrayAccess):
                    # base must be a variable (we require assignable lvalue)
                    base = name_node.array
                    if not isinstance(base, Var):
                        raise TypeError("Left-hand side of assignment must be a variable or array element of a variable")
                    base_sym = self._lookup_symbol(base.name)
                    if base_sym is None:
                        raise TypeError(f"Assignment to undeclared variable '{base.name}'")
                    if base_sym.get("mutable") is False:
                        raise TypeError("Cannot assign to immutable symbol")

                    base_type = base_sym["type"]
                    if not (isinstance(base_type, str) and base_type.startswith("array<") and base_type.endswith(">")):
                        raise TypeError(f"Trying to index non-array type '{base_type}'")

                    elem_type = base_type[len("array<"):-1]  # extract element type
                    # check index type
                    idx_type = self.check(name_node.index)
                    if idx_type != "int":
                        raise TypeError(f"Array index must be an int, got {idx_type}")

                    value_type = self.check(value)
                    if value_type != elem_type:
                        raise TypeError(f"Type mismatch assigning to array element: expected {elem_type}, got {value_type}")
                    return elem_type

                raise TypeError("LHS of assignment must be a variable or an array access")


            case Var(name):
                sym = self._lookup_symbol(name)
                if sym is None:
                    raise TypeError(f"Undefined variable or symbol '{name}'")
                return sym["type"]



            case NumberLiteral(value):
                return "float" if isinstance(value, float) else "int"

            case StringLiteral(value):
                return "string"

            case BooleanLiteral(value):
                return "bool"

            case BinaryOp(op, left, right):
                left_type = self.check(left)
                right_type = self.check(right)

                # --- Arithmetic Operators ---
                if op in ("PLUS", "MINUS", "MUL", "DIV", "POW"):
                    # --- Handle addition separately (since it can be string concat) ---
                    if op == "PLUS":
                        # If either operand is a string, result is string
                        if left_type == "string" or right_type == "string":
                            return "string"
                        # Numeric addition
                        if left_type in ("int", "float") and right_type in ("int", "float"):
                            return "float" if "float" in (left_type, right_type) else "int"
                        raise TypeError(f"Invalid operand types for '+': {left_type} and {right_type}")

                    # --- For -, *, / only numeric types are allowed ---
                    if left_type in ("int", "float") and right_type in ("int", "float"):
                        return "float" if "float" in (left_type, right_type) else "int"
                    raise TypeError(f"Invalid operand types for {op}: {left_type} and {right_type}")
                
                # --- Comparison Operators (result is always bool) ---
                elif op in ("EQ", "NEQ", "LT", "LEQ", "GT", "GEQ"):
                    # Equality (==, !=) allows any matching types
                    if op in ("EQ", "NEQ"):
                        if left_type != right_type:
                            raise TypeError(f"Cannot compare values of different types: {left_type} and {right_type}")
                        return "bool"

                    # Relational (<, <=, >, >=) — only numeric types allowed
                    if left_type in ("int", "float") and right_type in ("int", "float"):
                        return "bool"
                    raise TypeError(f"Invalid operand types for {op}: {left_type} and {right_type}")

                # --- Logical Operators (&&, ||) ---
                elif op in ("AND", "OR"):
                    if left_type != "bool" or right_type != "bool":
                        raise TypeError(f"Logical operator '{op}' requires boolean operands, got {left_type} and {right_type}")
                    return "bool"

                else:
                    raise TypeError(f"Unknown binary operator {op}")

            case UnaryOp(op, operand):
                operand_type = self.check(operand)
                if op == "NEGATE":  # prefix numeric negation
                    if operand_type not in ("int", "float"):
                        raise TypeError(f"Unary '-' requires numeric type, got {operand_type}")
                    return operand_type
                if op == "BANG":   # logical NOT
                    if operand_type != "bool":
                        raise TypeError(f"Unary '!' requires boolean type, got {operand_type}")
                    return "bool"
                if op in ("INC", "DEC"):
                    if not isinstance(operand, Var):
                        raise TypeError(f"Unary '{op}' can only be applied to variables")

                    # must be numeric
                    if operand_type not in ("int", "float"):
                        raise TypeError(f"Unary '{op}' requires numeric type, got {operand_type}")

                    return operand_type
                raise TypeError(f"Unknown unary operator {op}")

            case If(condition, then_branch, else_branch):
                cond_type = self.check(condition)
                if cond_type not in ("bool", "int", "float"):
                    raise TypeError(f"Condition must be boolean or numeric, got {cond_type}") # allow numeric conditions as truthy/falsy
                self.check(then_branch)
                if else_branch:
                    self.check(else_branch)

            case While(condition, body):
                cond_type = self.check(condition)
                if cond_type not in ("bool", "int", "float"):
                    raise TypeError(f"Condition must be boolean or numeric, got {cond_type}") # allow numeric conditions as truthy/falsy
                self.check(body)
            
            case ArrayLiteral(elements):
                # empty array -> array<any>
                if not elements:
                    return "array<any>"
                # check types of all elements (must match)
                elem_types = [self.check(e) for e in elements]
                first = elem_types[0]
                for t in elem_types[1:]:
                    if t != first:
                        raise TypeError(f"Array literal contains mixed element types: {first} and {t}")
                return f"array<{first}>"

            case ArrayAccess(array_expr, index_expr):
                # check index type
                idx_t = self.check(index_expr)
                if idx_t != "int":
                    raise TypeError(f"Array index must be an int, got {idx_t}")

                arr_t = self.check(array_expr)
                if not (isinstance(arr_t, str) and arr_t.startswith("array<") and arr_t.endswith(">")):
                    raise TypeError(f"Trying to index non-array type '{arr_t}'")
                elem_type = arr_t[len("array<"):-1]
                return elem_type

            case Call(func, args):
                for arg in args: 
                    self.check(arg)
                if isinstance(func, Var):
                    sym = self._lookup_symbol(func.name)
                    if not sym: 
                        raise TypeError(f"Undefined function '{func.name}'")
                    if sym["type"] != "function": 
                        raise TypeError(f"'{func.name}' is not callable")
                    ret_type = sym["info"].get("return")
                    param_types = sym["info"].get("params")
                    if param_types is not None:
                        if len(param_types) != len(args): 
                            raise TypeError(f"You have provided the wrong number of arguments. Provided: {len(args)}, expected: {len(param_types)}")
                        for expected, arg_node in zip(param_types, args):
                            arg_type = self.check(arg_node)
                            if expected != arg_type:
                                raise TypeError(f"Argument type mismatch in call to '{func.name}': expected {expected}, got {arg_type}")
                return ret_type or "void"


            case FuncDecl(return_type, name, params, body):
                if name in self._current_scope(): raise TypeError(f"Function '{name}' already declared")
                param_types = [ptype for ptype,pname in params]
                sig_info = {"return": return_type, "params": param_types}
                self._declare_symbol(name, "function", mutable=False, info=sig_info)
                self._push_scope()
                self.function_return_stack.append(return_type)
                try:
                    for ptype, pname in params:
                        if pname in self._current_scope():
                            raise TypeError(f"Parameter '{pname}' already declared in function '{name}'")
                        self._declare_symbol(pname, ptype, mutable=True)
                    self.function_return_stack.append(return_type)
                    try:
                        self.check(body)
                    finally:
                        self.function_return_stack.pop()
                finally:
                    self._pop_scope()
                return None
            
            case Return(value):
                if not self.function_return_stack:
                    raise TypeError("Return outside function")
                expected = self.function_return_stack[-1]
                if value is None:
                    if expected is not None: raise TypeError("Return without value in function expecting ...")
                if expected == "void":
                    raise TypeError("Cannot return a value from a void function")
                else:
                    value_type = self.check(value)
                    if expected != value_type:
                        raise TypeError("Return type mismatch")
                return value_type or None




            case Import(module_name):
                # Load module once and register its exported members into the symbol table
                if module_name in self._loaded_modules:
                    mod = self._loaded_modules[module_name]
                else:
                    module_path = os.path.join("builtins", f"{module_name}.py")
                    if not os.path.exists(module_path):
                        raise TypeError(f"Module '{module_name}' not found")
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    self._loaded_modules[module_name] = mod

                # Register exported members into self.symbols (e.g., math.PI, math.round)
                self._register_module_members(module_name, mod)
                return None



            case _:
                raise TypeError(f"Unknown AST node type: {type(node).__name__}")
