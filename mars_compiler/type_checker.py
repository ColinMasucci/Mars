from ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, If, While, VarDecl, UnaryOp, Import

class TypeChecker:
    def __init__(self):
        self.symbols = {}  #  variable dictionary {name : type}

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
                return "int"  # default, update if you add function signatures later
            
            case Import(module):
                return None  # imports don't have a type themselves


            case _:
                raise TypeError(f"Unknown AST node type: {type(node).__name__}")
