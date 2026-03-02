import os
import importlib.util

from mars_compiler.ast_nodes import DictLiteral, ArrayAccess, ArrayLiteral, NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, AugAssign, If, While, For, VarDecl, UnaryOp, UnitTag, Import, Return, Break, Continue, FuncDecl, MemberAccess, ClassDecl
from mars_compiler.units import parse_unit_expr, canonical_name, UnitSpec



class TypeChecker:
    def __init__(self, component_interfaces=None, class_interfaces=None):
        # Scopes: list of dicts, each dict: name -> { 'type': str or 'function', 'mutable': bool, 'info': dict }
        self.scopes = [{}]
        self._loaded_modules = {}  # cache loaded builtin modules
        self.function_return_stack = [] # stack of return types
        self.loop_depth = 0
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
        self._declare_symbol(
            "publish",
            "function",
            mutable=False,
            info={"return": "void", "params": ["string", "string", None]}
        )
        self._declare_symbol(
            "wait",
            "function",
            mutable=False,
            info={"return": "void", "params": ["float"]}
        )
        self._declare_symbol(
            "update",
            "function",
            mutable=False,
            info={"return": "void", "params": []}
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

    def _set_type(self, node, typ):
        setattr(node, "inferred_type", typ)
        return typ

    def _normalize_type(self, typ: str):
        # Convert parser array syntax -> type checker array syntax (e.g., int[] -> array<int>)
        # This is because parser uses int[] syntax for easier parsing, but type checker uses array<int> internally
        # We make this change because its better for the type checker to handle nested arrays (e.g., array<array<int>> vs int[][])
        if typ.endswith("[]"):
            elem_type = self._normalize_type(typ[:-2])  # recursive call
            return f"array<{elem_type}>"
        return typ

    def _split_unit_type(self, typ: str):
        if not isinstance(typ, str):
            return typ, None
        if typ.startswith(("array<", "dict<", "component:", "class:")):
            return typ, None
        if "::" in typ:
            base, unit_expr = typ.split("::", 1)
            return base, unit_expr
        return typ, None

    def _parse_unit_expr(self, expr: str) -> UnitSpec:
        try:
            return parse_unit_expr(expr)
        except ValueError as exc:
            raise TypeError(str(exc))

    def _numeric_type_info(self, typ: str):
        if not isinstance(typ, str):
            return None
        if typ.startswith(("array<", "dict<", "component:", "class:")):
            return None
        base, unit_expr = self._split_unit_type(typ)
        if base not in ("int", "float"):
            return None
        unit_spec = self._parse_unit_expr(unit_expr) if unit_expr else None
        return {"base": base, "unit_expr": unit_expr, "unit_spec": unit_spec}

    def _unit_type_string(self, unit_spec: UnitSpec):
        return f"float::{unit_spec.expr}"

    def _dims_tuple(self, dims):
        return tuple(sorted((k, v) for k, v in dims.items() if v != 0))

    def _is_temp_unit(self, spec: UnitSpec) -> bool:
        return any(dim == "Temp" for dim, _ in spec.dims)

    def _is_energy_unit(self, spec: UnitSpec) -> bool:
        # energy/torque dimensions: kg*m^2/s^2
        return spec.dims == (("L", 2), ("M", 1), ("T", -2)) and not spec.affine

    def _is_pure_angle(self, spec: UnitSpec) -> bool:
        return spec.dims == (("A", 1),) and not spec.affine

    def _should_drop_angle(self, left_spec: UnitSpec, right_spec: UnitSpec, op: str) -> bool:
        if op == "MUL":
            return (self._is_energy_unit(left_spec) and self._is_pure_angle(right_spec)) or \
                (self._is_energy_unit(right_spec) and self._is_pure_angle(left_spec))
        if op == "DIV":
            return self._is_energy_unit(left_spec) and self._is_pure_angle(right_spec)
        return False

    def _combine_units(self, left_spec: UnitSpec, right_spec: UnitSpec, op: str):
        if left_spec.affine or right_spec.affine:
            raise TypeError("Affine temperature units cannot be multiplied or divided")
        dims = {k: v for k, v in left_spec.dims}
        scale = left_spec.scale
        sign = 1 if op == "MUL" else -1
        for dim, exp in right_spec.dims:
            dims[dim] = dims.get(dim, 0) + exp * sign
        scale *= right_spec.scale ** sign
        expr = f"{left_spec.expr}{'*' if op == 'MUL' else '/'}{right_spec.expr}"
        if self._should_drop_angle(left_spec, right_spec, op):
            dims.pop("A", None)
        dims_tuple = self._dims_tuple(dims)
        cname = canonical_name(dims_tuple, scale, 0.0, False)
        display = cname if cname is not None else expr
        return UnitSpec(dims=dims_tuple, scale=scale, offset=0.0, expr=display, affine=False)

    def _pow_unit(self, base_spec: UnitSpec, exponent: int):
        if base_spec.affine:
            raise TypeError("Affine temperature units cannot be exponentiated")
        dims = {k: v * exponent for k, v in base_spec.dims}
        scale = base_spec.scale ** exponent
        expr = f"{base_spec.expr}^{exponent}"
        dims_tuple = self._dims_tuple(dims)
        cname = canonical_name(dims_tuple, scale, 0.0, False)
        display = cname if cname is not None else expr
        return UnitSpec(dims=dims_tuple, scale=scale, offset=0.0, expr=display, affine=False)

    def _convert_unit_node(self, expr_node, from_spec: UnitSpec, to_spec: UnitSpec):
        if from_spec.expr == to_spec.expr and from_spec.dims == to_spec.dims:
            return expr_node
        if from_spec.dims != to_spec.dims:
            raise TypeError(f"Unit mismatch: cannot convert '{from_spec.expr}' to '{to_spec.expr}'")
        if from_spec.affine != to_spec.affine:
            raise TypeError(f"Unit mismatch: cannot convert '{from_spec.expr}' to '{to_spec.expr}'")
        factor = from_spec.scale / to_spec.scale
        offset = (from_spec.offset - to_spec.offset) / to_spec.scale
        if abs(factor - 1.0) <= 1e-12 and abs(offset) <= 1e-12:
            return expr_node
        mul = expr_node if abs(factor - 1.0) <= 1e-12 else BinaryOp("MUL", expr_node, NumberLiteral(float(factor)))
        if abs(offset) <= 1e-12:
            return mul
        return BinaryOp("PLUS", mul, NumberLiteral(float(offset)))

    def _delta_unit(self, base_spec: UnitSpec):
        expr = f"d{base_spec.expr}"
        return UnitSpec(dims=base_spec.dims, scale=base_spec.scale, offset=0.0, expr=expr, affine=False)

    def _coerce_value_to_expected(self, expected_type, value_node, value_type, context):
        if expected_type is None:
            return value_node

        expected_info = self._numeric_type_info(expected_type)
        value_info = self._numeric_type_info(value_type)

        if expected_info and value_info:
            expected_unit = expected_info["unit_spec"]
            value_unit = value_info["unit_spec"]

            if expected_unit or value_unit:
                if expected_info["base"] != "float":
                    raise TypeError("Units are only allowed on float types")
                if expected_unit and value_unit:
                    if expected_unit.dims != value_unit.dims or expected_unit.affine != value_unit.affine:
                        raise TypeError(f"{context}: unit mismatch '{expected_unit.expr}' vs '{value_unit.expr}'")
                    value_node = self._convert_unit_node(value_node, value_unit, expected_unit)
                # unitless -> unitful or unitful -> unitless is allowed
                return value_node

            # numeric without units: allow coercion int<->float
            if expected_info["base"] == value_info["base"]:
                return value_node
            # allow numeric coercion by default
            return value_node

        if expected_info or value_info:
            raise TypeError(f"{context}: incompatible types {expected_type} and {value_type}")

        if not self._types_compatible(expected_type, value_type):
            raise TypeError(f"{context}: expected {expected_type}, got {value_type}")
        return value_node

    def _coerce_call_args(self, param_types, args, arg_types, context):
        if param_types is None:
            return
        if isinstance(param_types, (list, tuple)) and param_types and isinstance(param_types[0], (list, tuple)):
            last_error = None
            for sig in param_types:
                try:
                    tmp_args = list(args)
                    tmp_types = list(arg_types)
                    self._coerce_call_args_single(sig, tmp_args, tmp_types, context)
                    args[:] = tmp_args
                    arg_types[:] = tmp_types
                    return
                except TypeError as exc:
                    last_error = exc
            raise TypeError(f"{context}: no matching overload") from last_error
        self._coerce_call_args_single(param_types, args, arg_types, context)

    def _coerce_call_args_single(self, param_types, args, arg_types, context):
        if isinstance(param_types, tuple):
            param_types = list(param_types)
        if param_types and param_types[-1] == "...":
            if len(param_types) < 2:
                raise TypeError(f"{context}: invalid variadic signature")
            fixed = param_types[:-1]
            if len(arg_types) < len(fixed):
                raise TypeError(f"{context}: expected at least {len(fixed)} args, got {len(arg_types)}")
            # Coerce fixed params
            for i, expected in enumerate(fixed):
                new_arg = self._coerce_value_to_expected(
                    expected,
                    args[i],
                    arg_types[i],
                    f"{context} (arg {i + 1})"
                )
                args[i] = new_arg
                arg_types[i] = expected
            # Coerce remaining params to the last fixed type
            repeat_type = fixed[-1]
            for i in range(len(fixed), len(arg_types)):
                new_arg = self._coerce_value_to_expected(
                    repeat_type,
                    args[i],
                    arg_types[i],
                    f"{context} (arg {i + 1})"
                )
                args[i] = new_arg
                arg_types[i] = repeat_type
            return
        if len(param_types) != len(arg_types):
            raise TypeError(f"{context}: expected {len(param_types)} args, got {len(arg_types)}")
        for i, (expected, arg, arg_type) in enumerate(zip(param_types, args, arg_types)):
            new_arg = self._coerce_value_to_expected(
                expected,
                arg,
                arg_type,
                f"{context} (arg {i + 1})"
            )
            args[i] = new_arg
            arg_types[i] = expected

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
        a_info = self._numeric_type_info(a)
        b_info = self._numeric_type_info(b)
        if a_info or b_info:
            if not a_info or not b_info:
                # unitful or numeric vs non-numeric
                return False
            if not allow_numeric_coercion and a_info["base"] != b_info["base"]:
                return False
            if a_info["unit_spec"] and b_info["unit_spec"]:
                return a_info["unit_spec"].dims == b_info["unit_spec"].dims and \
                    a_info["unit_spec"].affine == b_info["unit_spec"].affine
            # unitless numeric is compatible with unitful numeric
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
        base, unit_expr = self._split_unit_type(t)
        if unit_expr is not None:
            if base != "float":
                raise TypeError("Units are only allowed on float types")
            self._parse_unit_expr(unit_expr)
            return True
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

    def _check_component_call(self, dotted_name, args, arg_types):
        parts = dotted_name.split(".")
        base = parts[0]
        sym = self._lookup_symbol(base)
        if sym is None:
            raise TypeError(f"Undefined variable or symbol '{base}'")
        sym_type = sym["type"]
        if not isinstance(sym_type, str) or not sym_type.startswith("component:"):
            raise TypeError(f"'{base}' is not a component and has no callable members")
        comp_type = sym_type.split(":", 1)[1]
        return self._resolve_component_function(comp_type, parts[1:], args, arg_types)

    def _resolve_component_function(self, comp_type, member_parts, args, arg_types):
        iface = self.component_interfaces.get(comp_type)
        if not iface:
            raise TypeError(f"Unknown component type '{comp_type}'")

        name = member_parts[0]
        if len(member_parts) == 1:
            finfo = iface.get("funcs", {}).get(name)
            if not finfo:
                raise TypeError(f"Component '{comp_type}' has no function '{name}'")
            param_types = finfo.get("params", [])
            self._coerce_call_args(
                param_types,
                args,
                arg_types,
                f"Argument type mismatch in call to '{name}'"
            )
            return finfo.get("return") or "void"

        # Nested: traverse subcomponents
        sub_map = iface.get("subcomponents", {})
        if name not in sub_map:
            raise TypeError(f"Component '{comp_type}' has no subcomponent '{name}'")
        return self._resolve_component_function(sub_map[name], member_parts[1:], args, arg_types)


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
                    decl_info = self._numeric_type_info(stored_type)
                    value_info = self._numeric_type_info(value_type)
                    if decl_info and value_info:
                        if decl_info["base"] == "float" and decl_info["unit_spec"] is None and value_info["unit_spec"] is not None:
                            stored_type = self._unit_type_string(value_info["unit_spec"])
                            node.vartype = stored_type
                    value = self._coerce_value_to_expected(
                        stored_type,
                        value,
                        value_type,
                        f"Type mismatch in declaration of '{name}'"
                    )
                    node.value = value
                # Add to symbol table
                self._declare_symbol(name, stored_type, mutable=not getattr(node, "readonly", False))
                return self._set_type(node, stored_type)



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
                    value = self._coerce_value_to_expected(
                        expected,
                        value,
                        value_type,
                        f"Type mismatch in assignment to '{name}'"
                    )
                    node.value = value
                    return self._set_type(node, expected)

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
                        value = self._coerce_value_to_expected(
                            elem_type,
                            value,
                            value_type,
                            "Type mismatch assigning to array element"
                        )
                        node.value = value
                        name_node.inferred_type = elem_type
                        return self._set_type(node, elem_type)

                    if isinstance(container_type, str) and container_type.startswith("dict<") and container_type.endswith(">"):
                        inside = container_type[len("dict<"):-1]
                        key_type, val_type = [x.strip() for x in inside.split(",")]
                        idx_type = self.check(name_node.index)
                        if idx_type != key_type:
                            raise TypeError(f"Dictionary key must be {key_type}, got {idx_type}")
                        value_type = self.check(value)
                        value = self._coerce_value_to_expected(
                            val_type,
                            value,
                            value_type,
                            "Type mismatch assigning to dictionary element"
                        )
                        node.value = value
                        name_node.inferred_type = val_type
                        return self._set_type(node, val_type)

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
                    value = self._coerce_value_to_expected(
                        ftype,
                        value,
                        val_type,
                        f"Type mismatch assigning to field '{name_node.attr}'"
                    )
                    node.value = value
                    return self._set_type(node, ftype)

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
                left_info = self._numeric_type_info(left_type)
                right_info = self._numeric_type_info(right_type)
                if left_info or right_info:
                    if not left_info or not right_info:
                        raise TypeError(f"Invalid operand types for {op}: {left_type} and {right_type}")
                    left_unit = left_info["unit_spec"]
                    right_unit = right_info["unit_spec"]
                    left_base = left_info["base"]
                    right_base = right_info["base"]

                    if op in ("PLUS", "MINUS"):
                        if left_unit and right_unit:
                            if left_unit.dims != right_unit.dims:
                                raise TypeError(f"Unit mismatch for {op}: '{left_unit.expr}' vs '{right_unit.expr}'")
                            value = self._convert_unit_node(value, right_unit, left_unit)
                            node.value = value
                            result_unit = left_unit
                        else:
                            result_unit = left_unit or right_unit
                    elif op in ("MUL", "DIV"):
                        if left_unit and right_unit:
                            result_unit = self._combine_units(left_unit, right_unit, op)
                        else:
                            result_unit = left_unit or right_unit
                    else:
                        result_unit = None

                    if result_unit:
                        result_type = self._unit_type_string(result_unit)
                    else:
                        result_type = "float" if "float" in (left_base, right_base) else "int"
                else:
                    result_type = self._binary_result_type(op, left_type, right_type)
                if not self._types_compatible(left_type, result_type):
                    raise TypeError(f"Type mismatch in compound assignment: expected {left_type}, got {result_type}")
                return self._set_type(node, left_type)


            case Var(name):
                sym = self._lookup_symbol(name)
                if sym is None:
                    raise TypeError(f"Undefined variable or symbol '{name}'")
                return self._set_type(node, sym["type"])
            case MemberAccess(obj, attr):
                obj_type = self.check(obj)
                res = self._resolve_member_access(obj_type, attr)
                if res is None:
                    raise TypeError(f"Cannot access member '{attr}' on {obj_type}")
                return self._set_type(node, res)



            case UnitTag(expr, unit):
                expr_type = self.check(expr)
                expr_info = self._numeric_type_info(expr_type)
                if not expr_info:
                    raise TypeError("Unit tags can only be applied to numeric expressions")
                target_unit = self._parse_unit_expr(unit)
                if expr_info["unit_spec"]:
                    if expr_info["unit_spec"].dims != target_unit.dims:
                        raise TypeError(f"Unit mismatch: '{expr_info['unit_spec'].expr}' vs '{target_unit.expr}'")
                    node.expr = self._convert_unit_node(expr, expr_info["unit_spec"], target_unit)
                return self._set_type(node, self._unit_type_string(target_unit))

            case NumberLiteral(value):
                return self._set_type(node, "float" if isinstance(value, float) else "int")

            case StringLiteral(value):
                return self._set_type(node, "string")

            case BooleanLiteral(value):
                return self._set_type(node, "bool")

            case BinaryOp(op, left, right):
                left_type = self.check(left)
                right_type = self.check(right)

                # string concat falls back to base behavior
                if op == "PLUS" and (left_type == "string" or right_type == "string"):
                    return self._set_type(node, self._binary_result_type(op, left_type, right_type))

                left_info = self._numeric_type_info(left_type)
                right_info = self._numeric_type_info(right_type)

                if left_info or right_info:
                    if not left_info or not right_info:
                        raise TypeError(f"Invalid operand types for {op}: {left_type} and {right_type}")

                    left_unit = left_info["unit_spec"]
                    right_unit = right_info["unit_spec"]
                    left_base = left_info["base"]
                    right_base = right_info["base"]

                    # Comparisons
                    if op in ("EQ", "NEQ", "LT", "LEQ", "GT", "GEQ"):
                        if left_unit and right_unit:
                            if left_unit.dims != right_unit.dims or left_unit.affine != right_unit.affine:
                                raise TypeError(f"Unit mismatch in comparison: '{left_unit.expr}' vs '{right_unit.expr}'")
                            node.right = self._convert_unit_node(right, right_unit, left_unit)
                        return self._set_type(node, "bool")

                    # Addition / subtraction
                    if op in ("PLUS", "MINUS"):
                        if left_unit and right_unit:
                            if left_unit.dims != right_unit.dims:
                                raise TypeError(f"Unit mismatch for {op}: '{left_unit.expr}' vs '{right_unit.expr}'")
                            if self._is_temp_unit(left_unit) and self._is_temp_unit(right_unit):
                                # Temperature-specific arithmetic:
                                # absolute + delta -> absolute
                                # absolute - delta -> absolute
                                # absolute - absolute -> delta
                                # delta + absolute -> absolute
                                # delta - absolute -> error
                                if op == "PLUS":
                                    if left_unit.affine and right_unit.affine:
                                        raise TypeError("Cannot add absolute temperatures")
                                    if left_unit.affine and not right_unit.affine:
                                        delta_target = self._delta_unit(left_unit)
                                        node.right = self._convert_unit_node(right, right_unit, delta_target)
                                        result_unit = left_unit
                                    elif not left_unit.affine and right_unit.affine:
                                        delta_target = self._delta_unit(right_unit)
                                        node.left = self._convert_unit_node(left, left_unit, delta_target)
                                        result_unit = right_unit
                                    else:
                                        node.right = self._convert_unit_node(right, right_unit, left_unit)
                                        result_unit = left_unit
                                else:  # MINUS
                                    if left_unit.affine and right_unit.affine:
                                        node.right = self._convert_unit_node(right, right_unit, left_unit)
                                        result_unit = self._delta_unit(left_unit)
                                    elif left_unit.affine and not right_unit.affine:
                                        delta_target = self._delta_unit(left_unit)
                                        node.right = self._convert_unit_node(right, right_unit, delta_target)
                                        result_unit = left_unit
                                    elif not left_unit.affine and right_unit.affine:
                                        raise TypeError("Cannot subtract an absolute temperature from a delta temperature")
                                    else:
                                        node.right = self._convert_unit_node(right, right_unit, left_unit)
                                        result_unit = left_unit
                            else:
                                if left_unit.affine or right_unit.affine:
                                    if left_unit.affine != right_unit.affine:
                                        raise TypeError(f"Cannot mix absolute temperature with delta in {op.lower()}")
                                    if op == "PLUS":
                                        raise TypeError("Cannot add absolute temperatures")
                                    node.right = self._convert_unit_node(right, right_unit, left_unit)
                                    result_unit = self._delta_unit(left_unit)
                                else:
                                    node.right = self._convert_unit_node(right, right_unit, left_unit)
                                    result_unit = left_unit
                        else:
                            result_unit = left_unit or right_unit
                        if result_unit:
                            return self._set_type(node, self._unit_type_string(result_unit))
                        base_result = "float" if "float" in (left_base, right_base) else "int"
                        return self._set_type(node, base_result)

                    # Multiplication / division
                    if op in ("MUL", "DIV"):
                        if (left_unit and left_unit.affine) or (right_unit and right_unit.affine):
                            raise TypeError("Cannot multiply or divide absolute temperatures")
                        if left_unit and right_unit:
                            result_unit = self._combine_units(left_unit, right_unit, op)
                        else:
                            result_unit = left_unit or right_unit
                        if result_unit:
                            return self._set_type(node, self._unit_type_string(result_unit))
                        base_result = "float" if "float" in (left_base, right_base) else "int"
                        return self._set_type(node, base_result)

                    # Exponentiation
                    if op == "POW":
                        if right_unit:
                            raise TypeError("Exponent cannot have units")
                        if left_unit:
                            if left_unit.affine:
                                raise TypeError("Cannot exponentiate absolute temperatures")
                            if not isinstance(right, NumberLiteral) or not isinstance(right.value, int):
                                raise TypeError("Unit exponent must be an integer literal")
                            result_unit = self._pow_unit(left_unit, int(right.value))
                            return self._set_type(node, self._unit_type_string(result_unit))
                        return self._set_type(node, self._binary_result_type(op, left_type, right_type))

                return self._set_type(node, self._binary_result_type(op, left_type, right_type))

            case UnaryOp(op, operand):
                operand_type = self.check(operand)
                if op == "NEGATE":  # prefix numeric negation
                    if not self._numeric_type_info(operand_type):
                        raise TypeError(f"Unary '-' requires numeric type, got {operand_type}")
                    return self._set_type(node, operand_type)
                if op == "BANG":   # logical NOT
                    if operand_type != "bool":
                        raise TypeError(f"Unary '!' requires boolean type, got {operand_type}")
                    return self._set_type(node, "bool")
                if op in ("INC", "DEC"):
                    if not isinstance(operand, Var):
                        raise TypeError(f"Unary '{op}' can only be applied to variables")

                    # must be int
                    if operand_type != "int":
                        raise TypeError(f"Unary '{op}' requires int type, got {operand_type}")

                    return self._set_type(node, operand_type)
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
                self.loop_depth += 1
                try:
                    self.check(body)
                finally:
                    self.loop_depth -= 1

            case For(init, condition, increment, body):
                self._push_scope()
                try:
                    if init is not None:
                        self.check(init)
                    if condition is not None:
                        cond_type = self.check(condition)
                        if cond_type not in ("bool", "int", "float"):
                            raise TypeError(f"Condition must be boolean or numeric, got {cond_type}")
                    self.loop_depth += 1
                    try:
                        self.check(body)
                        if increment is not None:
                            self.check(increment)
                    finally:
                        self.loop_depth -= 1
                finally:
                    self._pop_scope()
            
            case ArrayLiteral(elements):
                # empty array -> array<any>
                if not elements:
                    return self._set_type(node, "array<any>")
                # check types of all elements (must match)
                elem_types = [self.check(e) for e in elements]
                first = elem_types[0]
                for t in elem_types[1:]:
                    if t != first:
                        raise TypeError(f"Array literal contains mixed element types: {first} and {t}")
                return self._set_type(node, f"array<{first}>")
            
            case DictLiteral(pairs):
                if not pairs:
                    return self._set_type(node, "dict<any, any>")

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

                return self._set_type(node, f"dict<{first_key}, {first_val}>")

            #Used for both Arrays and Dictionaries
            case ArrayAccess(container_expr, index_expr):
                # check index and container types
                idx_t = self.check(index_expr)
                cont_t = self.check(container_expr)

                # ARRAY ACCESS
                if isinstance(cont_t, str) and cont_t.startswith("array<") and cont_t.endswith(">"):
                    if idx_t != "int":
                        raise TypeError(f"Array index must be an int, got {idx_t}")
                    return self._set_type(node, cont_t[len("array<"):-1])
                

                # DICT ACCESS
                if isinstance(cont_t, str) and cont_t.startswith("dict<") and cont_t.endswith(">"):
                    inside = cont_t[len("dict<"):-1]  # "keyType, valueType"
                    key_t, val_t = [x.strip() for x in inside.split(",")]

                    if idx_t != key_t:
                        raise TypeError(f"Dictionary key must be {key_t}, got {idx_t}")

                    return self._set_type(node, val_t)

                raise TypeError(f"Trying to index non-indexable type '{cont_t}'")

            case Call(func, args):
                arg_types = [self.check(arg) for arg in args]
                if isinstance(func, Var):
                    if func.name == "type":
                        if len(args) != 1:
                            raise TypeError(f"Function 'type' expects 1 argument, got {len(args)}")
                        node.type_str = self._display_type(arg_types[0])
                        return self._set_type(node, "string")
                    if func.name == "unit":
                        if len(args) != 1:
                            raise TypeError(f"Function 'unit' expects 1 argument, got {len(args)}")
                        unit_info = self._numeric_type_info(arg_types[0])
                        if unit_info and unit_info["unit_expr"]:
                            spec = self._parse_unit_expr(unit_info["unit_expr"])
                            node.unit_str = spec.expr
                        else:
                            node.unit_str = "unitless"
                        return self._set_type(node, "string")
                    # constructor call
                    if func.name in self.class_interfaces:
                        iface = self.class_interfaces[func.name]
                        ctor = iface.get("ctor")
                        if ctor:
                            params = ctor.get("params", [])
                            self._coerce_call_args(
                                params,
                                args,
                                arg_types,
                                f"Constructor arg mismatch for {func.name}"
                            )
                        else:
                            if len(arg_types) != 0:
                                raise TypeError(f"Constructor for {func.name} takes no arguments")
                        return self._set_type(node, f"class:{func.name}")
                    if "." in func.name:
                        sym = self._lookup_symbol(func.name)
                        if sym:
                            # Dotted symbol resolved directly (e.g., module.func)
                            if sym["type"] != "function":
                                raise TypeError(f"'{func.name}' is not callable")
                            ret_type = sym["info"].get("return")
                            param_types = sym["info"].get("params")
                            if param_types is not None:
                                self._coerce_call_args(
                                    param_types,
                                    args,
                                    arg_types,
                                    f"Argument type mismatch in call to '{func.name}'"
                                )
                            return self._set_type(node, ret_type or "void")
                        return self._set_type(node, self._check_component_call(func.name, args, arg_types))

                    sym = self._lookup_symbol(func.name)
                    if not sym: 
                        raise TypeError(f"Undefined function '{func.name}'")
                    if sym["type"] != "function": 
                        raise TypeError(f"'{func.name}' is not callable")
                    ret_type = sym["info"].get("return")
                    param_types = sym["info"].get("params")
                    if param_types is not None:
                        self._coerce_call_args(
                            param_types,
                            args,
                            arg_types,
                            f"Argument type mismatch in call to '{func.name}'"
                        )
                    return self._set_type(node, ret_type or "void")
                if isinstance(func, MemberAccess):
                    return self._set_type(node, self._check_method_call(func, args, arg_types))
                raise TypeError("Unsupported function call target")

            case Break():
                if self.loop_depth <= 0:
                    raise TypeError("Break used outside of a loop")
                return None

            case Continue():
                if self.loop_depth <= 0:
                    raise TypeError("Continue used outside of a loop")
                return None

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
                    if expected == "void":
                        return None
                    raise TypeError("Return without value in function expecting ...")
                if expected == "void":
                    raise TypeError("Cannot return a value from a void function")
                value_type = self.check(value)
                value = self._coerce_value_to_expected(
                    expected,
                    value,
                    value_type,
                    "Return type mismatch"
                )
                node.value = value
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
                # Declare the module itself so member access (math.PI / math.sqrt) can type-check
                if not self._lookup_symbol(module_name):
                    self._declare_symbol(module_name, f"module:{module_name}", mutable=False)
                return None



            case _:
                raise TypeError(f"Unknown AST node type: {type(node).__name__}")

    # --- Class helpers ---
    def _check_method_call(self, member_access, args, arg_types):
        # resolve object type
        obj_type = self.check(member_access.obj)
        if isinstance(obj_type, str) and obj_type in self.class_interfaces:
            obj_type = f"class:{obj_type}"
        if isinstance(obj_type, str) and obj_type.startswith("module:"):
            module_name = obj_type.split(":", 1)[1]
            sym = self._lookup_symbol(f"{module_name}.{member_access.attr}")
            if not sym:
                raise TypeError(f"Module '{module_name}' has no member '{member_access.attr}'")
            if sym["type"] != "function":
                raise TypeError(f"'{module_name}.{member_access.attr}' is not callable")
            param_types = sym["info"].get("params")
            if param_types is not None:
                self._coerce_call_args(
                    param_types,
                    args,
                    arg_types,
                    f"Argument type mismatch in call to '{module_name}.{member_access.attr}'"
                )
            return sym["info"].get("return") or "void"
        if isinstance(obj_type, str) and obj_type.startswith("component:"):
            comp_type = obj_type.split(":",1)[1]
            if member_access.attr == "match":
                if len(arg_types) != 1:
                    raise TypeError(f"match expects 1 argument, got {len(arg_types)}")
                target = arg_types[0]
                if not isinstance(target, str) or not target.startswith("component:"):
                    raise TypeError("match expects a component type argument")
                target_type = target.split(":", 1)[1]
                return f"component:{target_type}"
            return self._resolve_component_function(comp_type, [member_access.attr], args, arg_types)
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
        self._coerce_call_args(
            params,
            args,
            arg_types,
            f"Argument type mismatch for {class_name}.{member_access.attr}"
        )
        return meth.get("return") or "void"

    def _resolve_member_access(self, obj_type, attr):
        if obj_type.startswith("module:"):
            module_name = obj_type.split(":", 1)[1]
            sym = self._lookup_symbol(f"{module_name}.{attr}")
            if not sym:
                raise TypeError(f"Module '{module_name}' has no member '{attr}'")
            if sym["type"] == "function":
                raise TypeError(f"'{module_name}.{attr}' is a function and must be called")
            return sym["type"]
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
