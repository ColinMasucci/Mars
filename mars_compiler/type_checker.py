from ast_nodes import DictLiteral, ArrayAccess, ArrayLiteral, NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, AugAssign, If, While, VarDecl, UnaryOp, Import, Return, FuncDecl, MemberAccess, ClassDecl
import os
import importlib.util


class TypeChecker:
    def __init__(self, component_interfaces=None, class_interfaces=None):
        # Scopes: list of dicts, each dict: name -> { 'type': str or 'function', 'mutable': bool, 'info': dict }
        self.scopes = [{}]
        self._loaded_modules = {}  # cache loaded builtin modules
        self.function_return_stack = [] # stack of return types
        self.user_types = set()  # placeholder for user-defined types (classes, structs, enums, etc) - not implemented yet
        self.component_interfaces = component_interfaces or {}
        self.class_interfaces = class_interfaces or {}
        self.component_parents = {name: info.get("parent") for name, info in (self.component_interfaces or {}).items()}

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
            elem_type = self._normalize_type(typ[:-2])  # recursive call
            return f"array<{elem_type}>"
        return typ

    def _split_kind(self, typ: str):
        """Return (kind,name) where kind in {component,class,other}."""
        if typ.startswith("component:"):
            return ("component", typ.split(":",1)[1])
        if typ.startswith("class:"):
            return ("class", typ.split(":",1)[1])
        if typ in self.component_interfaces:
            return ("component", typ)
        if typ in self.class_interfaces:
            return ("class", typ)
        return ("other", typ)

    def _component_is_a(self, child: str, parent: str):
        """True if child is parent or inherits from parent (using component_parents)."""
        if child == parent:
            return True
        cur = self.component_parents.get(child)
        while cur:
            if cur == parent:
                return True
            cur = self.component_parents.get(cur)
        return False

    # Compare two types for compatibility (including structured types) Ex. dict<int,string> and dict<int,string> are compatible, but dict<int,string> and dict<string,string> are not.
    def _types_compatible(self, a, b, allow_numeric_coercion=True):
        """Compare structured types like dict<K,V> and array<T>."""
        if a == b:
            return True
        if allow_numeric_coercion and a == "float" and b == "int":
            return True
        if allow_numeric_coercion and a == "int" and b == "float":
            return True
        if self._normalize_type(a) == self._normalize_type(b):
            return True
        # component subtyping (child -> parent)
        if isinstance(a, str) and isinstance(b, str):
            a_kind, a_name = self._split_kind(a)
            b_kind, b_name = self._split_kind(b)
            if a_kind == b_kind == "component":
                # allow child->parent substitution; prefer treating 'a' as expected, 'b' as actual
                return self._component_is_a(b_name, a_name) or self._component_is_a(a_name, b_name)
            if a_kind == b_kind == "class" and a_name == b_name:
                return True
        # class instance type strings can be "ClassName" or "class:ClassName"
        if isinstance(a, str) and isinstance(b, str):
            if a.startswith("class:") and a.split(":",1)[1] == b:
                return True
            if b.startswith("class:") and b.split(":",1)[1] == a:
                return True
            if a.startswith("class:") and b.startswith("class:") and a.split(":",1)[1] == b.split(":",1)[1]:
                return True
            if a.startswith("component:") and b.startswith("component:") and a.split(":",1)[1] == b.split(":",1)[1]:
                return True

        # array<T>
        if a.startswith("array<") and a.endswith(">") and \
        b.startswith("array<") and b.endswith(">"):
            a_inner = a[len("array<"):-1]
            b_inner = b[len("array<"):-1]
            return self._types_compatible(a_inner, b_inner, allow_numeric_coercion=False)

        # dict<K,V>
        if a.startswith("dict<") and a.endswith(">") and \
        b.startswith("dict<") and b.endswith(">"):
            a_inside = a[len("dict<"):-1]
            b_inside = b[len("dict<"):-1]
            a_key, a_val = [x.strip() for x in a_inside.split(",")]
            b_key, b_val = [x.strip() for x in b_inside.split(",")]
            return self._types_compatible(a_key, b_key, allow_numeric_coercion=False) and \
                self._types_compatible(a_val, b_val, allow_numeric_coercion=False)
        
        return False

    def _display_type(self, typ: str):
        if typ.startswith("class:"):
            return typ.split(":", 1)[1]
        if typ.startswith("component:"):
            return typ
        return typ

    def _binary_result_type(self, op, left_type, right_type):
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
        if op in ("EQ", "NEQ", "LT", "LEQ", "GT", "GEQ"):
            # Equality (==, !=) allows any matching types
            if op in ("EQ", "NEQ"):
                if left_type != right_type:
                    raise TypeError(f"Cannot compare values of different types: {left_type} and {right_type}")
                return "bool"

            # Relational (<, <=, >, >=) only numeric types allowed
            if left_type in ("int", "float") and right_type in ("int", "float"):
                return "bool"
            raise TypeError(f"Invalid operand types for {op}: {left_type} and {right_type}")

        # --- Logical Operators (&&, ||) ---
        if op in ("AND", "OR"):
            if left_type != "bool" or right_type != "bool":
                raise TypeError(f"Logical operator '{op}' requires boolean operands, got {left_type} and {right_type}")
            return "bool"

        raise TypeError(f"Unknown binary operator {op}")

    # Validate declared types, making sure dict<K,V> and array<T> are well-formed Ex. dict<int,string> is valid, but dict<int> or dict<int,string,float> is not.
    def _validate_declared_type(self, t):
        """Ensure declared types like dict<int,string> or array<string> are legal."""
        # primitive
        if t in ("int", "float", "bool", "string", "void", "any"):
            return True

        # Components (treated as user-defined types)
        if t in self.component_interfaces:
            return True
        if t in self.class_interfaces:
            return True
        
        # User-defined types (classes, structs, enums, etc) - placeholder for future implementation
        if t in self.user_types:
            return True

        # array<T>
        if t.startswith("array<") and t.endswith(">"):
            inner = t[len("array<"):-1]
            return self._validate_declared_type(inner)

        # dict<K,V>
        if t.startswith("dict<") and t.endswith(">"):
            inside = t[len("dict<"):-1]
            if "," not in inside:
                raise TypeError(f"Invalid dict type '{t}'")
            key, val = [x.strip() for x in inside.split(",")]
            return self._validate_declared_type(key) and \
                self._validate_declared_type(val)

        raise TypeError(f"Unknown type '{t}'")



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

    # Component-aware helpers
    def check_components(self, components):
        """Type-check the functions of each component using precomputed component interfaces."""
        for comp in components:
            self._check_component(comp)

    def _check_component(self, comp):
        iface = self.component_interfaces.get(comp.name, {"params": {}, "funcs": {}, "subcomponents": {}})

        self._push_scope()
        try:
            # Component parameters are visible as variables
            for pname, ptype in iface.get("params", {}).items():
                normalized = self._normalize_type(ptype)
                self._declare_symbol(pname, normalized, mutable=True)

            # Subcomponents are visible as component-typed symbols
            for sname, stype in iface.get("subcomponents", {}).items():
                self._declare_symbol(sname, f"component:{stype}", mutable=True)

            # Component functions are callable within the component
            for fname, finfo in iface.get("funcs", {}).items():
                info = {"return": finfo.get("return"), "params": finfo.get("params")}
                self._declare_symbol(fname, "function", mutable=False, info=info)

            # Check bodies for functions that have one
            for func in getattr(comp, "functions", []):
                if func.body is None:
                    continue
                self._check_component_function_body(func)
        finally:
            self._pop_scope()

    def _check_component_function_body(self, func_decl):
        self._push_scope()
        self.function_return_stack.append(func_decl.return_type)
        try:
            for ptype, pname in func_decl.params:
                if pname in self._current_scope():
                    raise TypeError(f"Parameter '{pname}' already declared in function '{func_decl.name}'")
                normalized = self._normalize_type(ptype)
                self._declare_symbol(pname, normalized, mutable=True)
            self.check(func_decl.body)
        finally:
            self.function_return_stack.pop()
            self._pop_scope()

    def _resolve_dotted_var(self, name):
        parts = name.split(".")
        base = parts[0]
        sym = self._lookup_symbol(base)
        if sym is None:
            raise TypeError(f"Undefined variable or symbol '{base}'")
        sym_type = sym["type"]
        if not isinstance(sym_type, str) or not sym_type.startswith("component:"):
            raise TypeError(f"'{base}' is not a component and has no members")
        comp_type = sym_type.split(":", 1)[1]
        return self._resolve_component_member(comp_type, parts[1:])

    def _resolve_component_member(self, comp_type, member_parts):
        iface = self.component_interfaces.get(comp_type)
        if not iface:
            raise TypeError(f"Unknown component type '{comp_type}'")
        name = member_parts[0]

        # Direct param or function
        if len(member_parts) == 1:
            if name in iface.get("params", {}):
                return iface["params"][name]
            if name in iface.get("funcs", {}):
                # Accessing a function as a value is not supported; must be called
                raise TypeError(f"'{name}' is a function on component '{comp_type}' and must be called")
            raise TypeError(f"Component '{comp_type}' has no member '{name}'")

        # Nested access through subcomponents
        sub_map = iface.get("subcomponents", {})
        if name not in sub_map:
            raise TypeError(f"Component '{comp_type}' has no subcomponent '{name}'")
        return self._resolve_component_member(sub_map[name], member_parts[1:])

    def _check_component_call(self, dotted_name, arg_types):
        parts = dotted_name.split(".")
        base = parts[0]
        sym = self._lookup_symbol(base)
        if sym is None:
            raise TypeError(f"Undefined variable or symbol '{base}'")
        sym_type = sym["type"]
        if not isinstance(sym_type, str) or not sym_type.startswith("component:"):
            raise TypeError(f"'{base}' is not a component and has no callable members")
        comp_type = sym_type.split(":", 1)[1]
        return self._resolve_component_function(comp_type, parts[1:], arg_types)

    def _resolve_component_function(self, comp_type, member_parts, arg_types):
        iface = self.component_interfaces.get(comp_type)
        if not iface:
            raise TypeError(f"Unknown component type '{comp_type}'")

        name = member_parts[0]
        if len(member_parts) == 1:
            finfo = iface.get("funcs", {}).get(name)
            if not finfo:
                raise TypeError(f"Component '{comp_type}' has no function '{name}'")
            param_types = finfo.get("params", [])
            if len(param_types) != len(arg_types):
                raise TypeError(f"You have provided the wrong number of arguments. Provided: {len(arg_types)}, expected: {len(param_types)}")
            for expected, got in zip(param_types, arg_types):
                if not self._types_compatible(expected, got):
                    raise TypeError(f"Argument type mismatch in call to '{name}': expected {expected}, got {got}")
            return finfo.get("return") or "void"

        # Nested: traverse subcomponents
        sub_map = iface.get("subcomponents", {})
        if name not in sub_map:
            raise TypeError(f"Component '{comp_type}' has no subcomponent '{name}'")
        return self._resolve_component_function(sub_map[name], member_parts[1:], arg_types)


    def check(self, node):
        match node:
            case Program(statements, components, classes):
                self._push_scope()
                try:
                    # Expose classes and components as symbols for dotted access in programs
                    for cname in self.class_interfaces:
                        self._declare_symbol(cname, f"class:{cname}", mutable=False)
                    for cname in self.component_interfaces:
                        self._declare_symbol(cname, f"component:{cname}", mutable=False)
                    # also expose class names as types
                    for stmt in statements:
                        self.check(stmt)
                finally:
                    self._pop_scope()
                # Components are validated separately; this matcher keeps parsing aligned with Program structure.

            case Block(statements):
                self._push_scope()
                try:
                    for stmt in statements:
                        self.check(stmt)
                finally:
                    self._pop_scope()


            case VarDecl(vartype, name, value):
                # Normalize (e.g., int[] → array<int>)
                vartype = self._normalize_type(vartype)

                # Check the type exists or is valid (dict/array)
                self._validate_declared_type(vartype)

                stored_type = vartype
                if vartype in self.component_interfaces:
                    stored_type = f"component:{vartype}"
                if vartype in self.class_interfaces:
                    stored_type = f"class:{vartype}"

                # Check redeclaration
                if name in self._current_scope():
                    raise TypeError(f"Variable '{name}' already declared")

                # If initializer exists, ensure type compatibility
                if value is not None:
                    value_type = self.check(value)
                    if not self._types_compatible(stored_type, value_type):
                        raise TypeError(
                            f"Type mismatch in declaration of '{name}': "
                            f"expected {vartype}, got {value_type}"
                        )
                # Add to symbol table
                self._declare_symbol(name, stored_type, mutable=not getattr(node, "readonly", False))
                return stored_type



            case Assign(name_node, value):
                # ---------------- SIMPLE VAR ASSIGN ----------------
                if isinstance(name_node, Var):
                    name = name_node.name
                    sym = self._lookup_symbol(name)
                    if sym is None:
                        raise TypeError(f"Assignment to undeclared variable '{name}'")
                    if sym.get("mutable") is False:
                        raise TypeError(f"Cannot assign to immutable symbol '{name}'")
                    value_type = self.check(value)
                    expected = sym["type"]
                    if not self._types_compatible(expected, value_type):
                        raise TypeError(f"Type mismatch in assignment to '{name}': expected {expected}, got {value_type}")
                    return expected

                # ---------------- ARRAY / DICT ELEMENT ASSIGN ----------------
                if isinstance(name_node, ArrayAccess):
                    container = name_node.array
                    container_type = self.check(container)

                    # Enforce mutability on container if it is a variable or class field
                    if isinstance(container, Var):
                        base_sym = self._lookup_symbol(container.name)
                        if base_sym is None:
                            raise TypeError(f"Assignment to undeclared variable '{container.name}'")
                        if base_sym.get("mutable") is False:
                            raise TypeError(f"Cannot assign to immutable symbol '{container.name}'")
                    elif isinstance(container, MemberAccess):
                        obj_type = self.check(container.obj)
                        if isinstance(obj_type, str) and obj_type.startswith("class:"):
                            cname = obj_type.split(":",1)[1]
                            iface = self.class_interfaces.get(cname, {})
                            readonly = iface.get("readonly", {}).get(container.attr, False)
                            if readonly:
                                raise TypeError(f"Cannot assign to const field '{container.attr}'")
                        else:
                            raise TypeError("Left-hand side of assignment must be a variable, array element, or class field")

                    # array<int> or dict<K,V>
                    if isinstance(container_type, str) and container_type.startswith("array<") and container_type.endswith(">"):
                        elem_type = container_type[len("array<"):-1]
                        idx_type = self.check(name_node.index)
                        if idx_type != "int":
                            raise TypeError(f"Array index must be int, got {idx_type}")
                        value_type = self.check(value)
                        if not self._types_compatible(elem_type, value_type):
                            raise TypeError(f"Type mismatch assigning to array element: expected {elem_type}, got {value_type}")
                        name_node.inferred_type = elem_type
                        return elem_type

                    if isinstance(container_type, str) and container_type.startswith("dict<") and container_type.endswith(">"):
                        inside = container_type[len("dict<"):-1]
                        key_type, val_type = [x.strip() for x in inside.split(",")]
                        idx_type = self.check(name_node.index)
                        if idx_type != key_type:
                            raise TypeError(f"Dictionary key must be {key_type}, got {idx_type}")
                        value_type = self.check(value)
                        if not self._types_compatible(val_type, value_type):
                            raise TypeError(f"Type mismatch assigning to dictionary element: expected {val_type}, got {value_type}")
                        name_node.inferred_type = val_type
                        return val_type

                    raise TypeError(f"Trying to index non-indexable type '{container_type}'")

                # ---------------- CLASS FIELD ASSIGN ----------------
                if isinstance(name_node, MemberAccess):
                    obj_type = self.check(name_node.obj)
                    if not isinstance(obj_type, str) or not obj_type.startswith("class:"):
                        raise TypeError("Left-hand side of assignment must be a variable, array element, or class field")
                    cname = obj_type.split(":",1)[1]
                    iface = self.class_interfaces.get(cname, {})
                    readonly = iface.get("readonly", {}).get(name_node.attr, False)
                    if readonly:
                        raise TypeError(f"Cannot assign to const field '{name_node.attr}'")
                    ftype = self._resolve_member_access(obj_type, name_node.attr)
                    val_type = self.check(value)
                    if not self._types_compatible(ftype, val_type):
                        raise TypeError(f"Type mismatch assigning to field '{name_node.attr}': expected {ftype}, got {val_type}")
                    return ftype

                raise TypeError("LHS of assignment must be a variable or an array access")

            case AugAssign(name_node, op, value):
                # ---------------- SIMPLE VAR ASSIGN ----------------
                if isinstance(name_node, Var):
                    name = name_node.name
                    sym = self._lookup_symbol(name)
                    if sym is None:
                        raise TypeError(f"Assignment to undeclared variable '{name}'")
                    if sym.get("mutable") is False:
                        raise TypeError(f"Cannot assign to immutable symbol '{name}'")
                    left_type = sym["type"]

                # ---------------- ARRAY / DICT ELEMENT ASSIGN ----------------
                elif isinstance(name_node, ArrayAccess):
                    container = name_node.array
                    container_type = self.check(container)

                    # Enforce mutability on container if it is a variable or class field
                    if isinstance(container, Var):
                        base_sym = self._lookup_symbol(container.name)
                        if base_sym is None:
                            raise TypeError(f"Assignment to undeclared variable '{container.name}'")
                        if base_sym.get("mutable") is False:
                            raise TypeError(f"Cannot assign to immutable symbol '{container.name}'")
                    elif isinstance(container, MemberAccess):
                        obj_type = self.check(container.obj)
                        if isinstance(obj_type, str) and obj_type.startswith("class:"):
                            cname = obj_type.split(":",1)[1]
                            iface = self.class_interfaces.get(cname, {})
                            readonly = iface.get("readonly", {}).get(container.attr, False)
                            if readonly:
                                raise TypeError(f"Cannot assign to const field '{container.attr}'")
                        else:
                            raise TypeError("Left-hand side of assignment must be a variable, array element, or class field")

                    # array<int> or dict<K,V>
                    if isinstance(container_type, str) and container_type.startswith("array<") and container_type.endswith(">"):
                        elem_type = container_type[len("array<"):-1]
                        idx_type = self.check(name_node.index)
                        if idx_type != "int":
                            raise TypeError(f"Array index must be int, got {idx_type}")
                        left_type = elem_type
                        name_node.inferred_type = elem_type
                    elif isinstance(container_type, str) and container_type.startswith("dict<") and container_type.endswith(">"):
                        inside = container_type[len("dict<"):-1]
                        key_type, val_type = [x.strip() for x in inside.split(",")]
                        idx_type = self.check(name_node.index)
                        if idx_type != key_type:
                            raise TypeError(f"Dictionary key must be {key_type}, got {idx_type}")
                        left_type = val_type
                        name_node.inferred_type = val_type
                    else:
                        raise TypeError(f"Trying to index non-indexable type '{container_type}'")

                # ---------------- CLASS FIELD ASSIGN ----------------
                elif isinstance(name_node, MemberAccess):
                    obj_type = self.check(name_node.obj)
                    if not isinstance(obj_type, str) or not obj_type.startswith("class:"):
                        raise TypeError("Left-hand side of assignment must be a variable, array element, or class field")
                    cname = obj_type.split(":",1)[1]
                    iface = self.class_interfaces.get(cname, {})
                    readonly = iface.get("readonly", {}).get(name_node.attr, False)
                    if readonly:
                        raise TypeError(f"Cannot assign to const field '{name_node.attr}'")
                    left_type = self._resolve_member_access(obj_type, name_node.attr)

                else:
                    raise TypeError("LHS of assignment must be a variable or an array access")

                right_type = self.check(value)
                result_type = self._binary_result_type(op, left_type, right_type)
                if not self._types_compatible(left_type, result_type):
                    raise TypeError(f"Type mismatch in compound assignment: expected {left_type}, got {result_type}")
                return left_type


            case Var(name):
                sym = self._lookup_symbol(name)
                if sym is None:
                    raise TypeError(f"Undefined variable or symbol '{name}'")
                return sym["type"]
            case MemberAccess(obj, attr):
                obj_type = self.check(obj)
                res = self._resolve_member_access(obj_type, attr)
                if res is None:
                    raise TypeError(f"Cannot access member '{attr}' on {obj_type}")
                return res



            case NumberLiteral(value):
                return "float" if isinstance(value, float) else "int"

            case StringLiteral(value):
                return "string"

            case BooleanLiteral(value):
                return "bool"

            case BinaryOp(op, left, right):
                left_type = self.check(left)
                right_type = self.check(right)
                return self._binary_result_type(op, left_type, right_type)

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

                    # must be int
                    if operand_type != "int":
                        raise TypeError(f"Unary '{op}' requires int type, got {operand_type}")

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
            
            case DictLiteral(pairs):
                if not pairs:
                    return "dict<any, any>"

                key_types = []
                value_types = []

                for key, value in pairs:
                    k_type = self.check(key)
                    v_type = self.check(value)
                    key_types.append(k_type)
                    value_types.append(v_type)

                # All keys must match
                first_key = key_types[0]
                for k in key_types[1:]:
                    if k != first_key:
                        raise TypeError(f"Dictionary contains mixed key types: {first_key} and {k}")

                # All values must match
                first_val = value_types[0]
                for v in value_types[1:]:
                    if v != first_val:
                        raise TypeError(f"Dictionary contains mixed value types: {first_val} and {v}")

                return f"dict<{first_key}, {first_val}>"

            #Used for both Arrays and Dictionaries
            case ArrayAccess(container_expr, index_expr):
                # check index and container types
                idx_t = self.check(index_expr)
                cont_t = self.check(container_expr)

                # ARRAY ACCESS
                if isinstance(cont_t, str) and cont_t.startswith("array<") and cont_t.endswith(">"):
                    if idx_t != "int":
                        raise TypeError(f"Array index must be an int, got {idx_t}")
                    return cont_t[len("array<"):-1]
                

                # DICT ACCESS
                if isinstance(cont_t, str) and cont_t.startswith("dict<") and cont_t.endswith(">"):
                    inside = cont_t[len("dict<"):-1]  # "keyType, valueType"
                    key_t, val_t = [x.strip() for x in inside.split(",")]

                    if idx_t != key_t:
                        raise TypeError(f"Dictionary key must be {key_t}, got {idx_t}")

                    return val_t

                raise TypeError(f"Trying to index non-indexable type '{cont_t}'")

            case Call(func, args):
                arg_types = [self.check(arg) for arg in args]
                if isinstance(func, Var):
                    if func.name == "type":
                        if len(args) != 1:
                            raise TypeError(f"Function 'type' expects 1 argument, got {len(args)}")
                        node.type_str = self._display_type(arg_types[0])
                        return "string"
                    # constructor call
                    if func.name in self.class_interfaces:
                        iface = self.class_interfaces[func.name]
                        ctor = iface.get("ctor")
                        if ctor:
                            params = ctor.get("params", [])
                            if len(params) != len(arg_types):
                                raise TypeError(f"Wrong arg count for constructor {func.name}: expected {len(params)}, got {len(arg_types)}")
                            for expected, got in zip(params, arg_types):
                                if not self._types_compatible(expected, got):
                                    raise TypeError(f"Constructor arg mismatch for {func.name}: expected {expected}, got {got}")
                        else:
                            if len(arg_types) != 0:
                                raise TypeError(f"Constructor for {func.name} takes no arguments")
                        return f"class:{func.name}"
                    if "." in func.name:
                        sym = self._lookup_symbol(func.name)
                        if sym:
                            # Dotted symbol resolved directly (e.g., module.func)
                            if sym["type"] != "function":
                                raise TypeError(f"'{func.name}' is not callable")
                            ret_type = sym["info"].get("return")
                            param_types = sym["info"].get("params")
                            if param_types is not None:
                                if len(param_types) != len(arg_types): 
                                    raise TypeError(f"You have provided the wrong number of arguments. Provided: {len(arg_types)}, expected: {len(param_types)}")
                                for expected, arg_type in zip(param_types, arg_types):
                                    if not self._types_compatible(expected, arg_type):
                                        raise TypeError(f"Argument type mismatch in call to '{func.name}': expected {expected}, got {arg_type}")
                            return ret_type or "void"
                        return self._check_component_call(func.name, arg_types)

                    sym = self._lookup_symbol(func.name)
                    if not sym: 
                        raise TypeError(f"Undefined function '{func.name}'")
                    if sym["type"] != "function": 
                        raise TypeError(f"'{func.name}' is not callable")
                    ret_type = sym["info"].get("return")
                    param_types = sym["info"].get("params")
                    if param_types is not None:
                        if len(param_types) != len(arg_types): 
                            raise TypeError(f"You have provided the wrong number of arguments. Provided: {len(arg_types)}, expected: {len(param_types)}")
                        for expected, arg_type in zip(param_types, arg_types):
                            if not self._types_compatible(expected, arg_type):
                                raise TypeError(f"Argument type mismatch in call to '{func.name}': expected {expected}, got {arg_type}")
                    return ret_type or "void"
                if isinstance(func, MemberAccess):
                    return self._check_method_call(func, arg_types)
                raise TypeError("Unsupported function call target")


            case FuncDecl(return_type, name, params, body):
                if name in self._current_scope(): raise TypeError(f"Function '{name}' already declared")
                param_types = [ptype for ptype,pname in params]
                sig_info = {"return": return_type, "params": param_types}
                self._declare_symbol(name, "function", mutable=False, info=sig_info)
                if body is not None:
                    self._push_scope()
                    self.function_return_stack.append(return_type)
                    try:
                        for ptype, pname in params:
                            if pname in self._current_scope():
                                raise TypeError(f"Parameter '{pname}' already declared in function '{name}'")
                            self._declare_symbol(pname, ptype, mutable=True)
                        self.check(body)
                    finally:
                        self.function_return_stack.pop()
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
                    if not self._types_compatible(expected, value_type):
                        raise TypeError("Return type mismatch")
                return value_type or None




            case Import(module_name):
                # If importing a component, just declare it
                if module_name in self.component_interfaces:
                    if not self._lookup_symbol(module_name):
                        self._declare_symbol(module_name, f"component:{module_name}", mutable=False)
                    return None
                if module_name in self.class_interfaces:
                    if not self._lookup_symbol(module_name):
                        self._declare_symbol(module_name, f"class:{module_name}", mutable=False)
                    return None

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

    # --- Class helpers ---
    def _check_method_call(self, member_access, arg_types):
        # resolve object type
        obj_type = self.check(member_access.obj)
        if isinstance(obj_type, str) and obj_type in self.class_interfaces:
            obj_type = f"class:{obj_type}"
        if isinstance(obj_type, str) and obj_type.startswith("component:"):
            comp_type = obj_type.split(":",1)[1]
            return self._resolve_component_function(comp_type, [member_access.attr], arg_types)
        if not isinstance(obj_type, str) or not obj_type.startswith("class:"):
            raise TypeError(f"'{member_access.obj}' is not a class instance")
        class_name = obj_type.split(":",1)[1]
        iface = self.class_interfaces.get(class_name)
        if not iface:
            raise TypeError(f"Unknown class '{class_name}'")
        meth = iface.get("methods", {}).get(member_access.attr)
        if not meth:
            raise TypeError(f"Class '{class_name}' has no method '{member_access.attr}'")
        params = meth.get("params", [])
        if len(params) != len(arg_types):
            raise TypeError(f"Wrong arg count for {class_name}.{member_access.attr}: expected {len(params)}, got {len(arg_types)}")
        for expected, got in zip(params, arg_types):
            if not self._types_compatible(expected, got):
                raise TypeError(f"Argument type mismatch for {class_name}.{member_access.attr}: expected {expected}, got {got}")
        return meth.get("return") or "void"

    def _resolve_member_access(self, obj_type, attr):
        if obj_type.startswith("component:"):
            cname = obj_type.split(":",1)[1]
            iface = self.component_interfaces.get(cname)
            if not iface:
                raise TypeError(f"Unknown component '{cname}'")
            if attr in iface.get("params", {}):
                return iface["params"][attr]
            if attr in iface.get("funcs", {}):
                raise TypeError(f"'{attr}' is a function on component '{cname}' and must be called")
            if attr in iface.get("subcomponents", {}):
                return f"component:{iface['subcomponents'][attr]}"
            raise TypeError(f"Component '{cname}' has no member '{attr}'")

        if obj_type.startswith("class:"):
            cname = obj_type.split(":",1)[1]
            iface = self.class_interfaces.get(cname)
            if not iface:
                raise TypeError(f"Unknown class '{cname}'")
            if attr in iface.get("fields", {}):
                return iface["fields"][attr]
            if attr in iface.get("methods", {}):
                raise TypeError(f"'{attr}' is a method on class '{cname}' and must be called")
            raise TypeError(f"Class '{cname}' has no member '{attr}'")
        return None
