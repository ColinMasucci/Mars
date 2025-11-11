from ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, If, While, VarDecl, UnaryOp, Import
import os
import importlib.util


class TypeChecker:
    def __init__(self):
        self.symbols = {}  #  variable dictionary {name : type}
        self._loaded_modules = {}  # cache loaded builtin modules

    def _type_from_python_obj(self, obj):
        """Map Python object -> MARS type or 'function'."""
        if callable(obj):
            return "function"
        if isinstance(obj, bool):
            return "bool"
        if isinstance(obj, int):
            return "int"
        if isinstance(obj, float):
            return "float"
        if isinstance(obj, str):
            return "string"
        return type(obj).__name__


    def _register_module_members(self, module_name, mod):
        """Load vars & functions from library module."""
        # primary exported mapping name (e.g., MATH_FUNCS)
        keyname = f"{module_name.upper()}_FUNCS"
        funcs_dict = getattr(mod, keyname, {})

        # Register everything in that mapping (functions or constants)
        for name, obj in funcs_dict.items():
            full = f"{module_name}.{name}"
            self.symbols[full] = self._type_from_python_obj(obj)

        # Optionally support a separate CONSTS mapping if library author used it
        const_key = f"{module_name.upper()}_CONSTS"
        consts_dict = getattr(mod, const_key, {})
        for name, obj in consts_dict.items():
            full = f"{module_name}.{name}"
            self.symbols[full] = self._type_from_python_obj(obj)


    def check(self, node):
        match node:
            case Program(statements):
                for stmt in statements:
                    self.check(stmt)

            case Block(statements):
                for stmt in statements:
                    self.check(stmt)

            case VarDecl(vartype, name, value):
                if name in self.symbols:
                    raise TypeError(f"Variable '{name}' already declared")

                value_type = self.check(value)
                if vartype != value_type:
                    raise TypeError(f"Type mismatch in declaration of '{name}': expected {vartype}, got {value_type}")

                self.symbols[name] = vartype
                return vartype

            case Assign(name, value):
                if name not in self.symbols:
                    raise TypeError(f"Assignment to undeclared variable '{name}'")
                value_type = self.check(value)
                expected = self.symbols[name]
                if expected != value_type:
                    raise TypeError(f"Type mismatch in assignment to '{name}': expected {expected}, got {value_type}")
                return expected

            case Var(name):
                # handle dotted module.member names e.g., "math.PI"
                if "." in name:
                    if name not in self.symbols:
                        raise TypeError(f"Undefined variable '{name}'")
                    return self.symbols[name]
                # otherwise normal variable
                if name not in self.symbols:
                    raise TypeError(f"Undefined variable '{name}'")
                return self.symbols[name]


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
                    if operand_type not in ("int", "float"):
                        raise TypeError(f"Postfix '{op}' requires numeric type, got {operand_type}")
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

            case Call(func, args):
                for arg in args:
                    self.check(arg)

                # If calling a module function like math.round, verify it exists & is callable
                if isinstance(func, Var) and "." in func.name:
                    if func.name not in self.symbols:
                        raise TypeError(f"Undefined function '{func.name}'")
                    typ = self.symbols[func.name]
                    if typ != "function":
                        raise TypeError(f"'{func.name}' is not callable")
                    # We don't have detailed signatures yet — assume numeric return
                    return "int"

                # Top-level calls (print) — accept for now
                return "int"



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
