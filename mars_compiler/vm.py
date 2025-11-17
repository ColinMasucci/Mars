from typing import List, Tuple, Any
import importlib.util
import os


Instr = Tuple[str, ...]

class VMError(Exception): pass

class VM:
    def __init__(self, bytecode: List[Instr]):
        self.code = bytecode
        self.stack = []
        self.pc = 0
        self.locals = {}  # {name: (value, vartype)}
        self._modules = {}  # module_name -> module object
        self.call_stack = []  # stack of (return_pc, locals_snapshot)


    def run(self):
        while self.pc < len(self.code):
            instr = self.code[self.pc]
            op, *args = instr  # unpack opcode and any arguments
            # debug: print(self.pc, instr, "stack:", self.stack)

            match op:
                case "PUSH_INT":
                    self.stack.append(int(args[0]))
                case "PUSH_FLOAT":
                    self.stack.append(float(args[0]))
                case "PUSH_STR":
                    self.stack.append(args[0])
                case "PUSH_BOOL":
                    self.stack.append(bool(args[0]))

                case "ADD":
                    b = self.stack.pop(); a = self.stack.pop()
                    # String concatenation if either is str
                    if isinstance(a, str) or isinstance(b, str):
                        self.stack.append(str(a) + str(b))
                    else:
                        self.stack.append(a + b)

                case "SUB":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a - b)

                case "MUL":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a * b)

                case "DIV":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a / b)

                case "POW":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a ** b)
                
                case "AND":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a and b)
                
                case "OR":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a or b)

                case "LT":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a < b)

                case "GT":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a > b)

                case "LEQ":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a <= b)

                case "GEQ":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a >= b)

                case "EQ":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a == b)

                case "NEQ":
                    b = self.stack.pop(); a = self.stack.pop()
                    self.stack.append(a != b)

                case "NEGATE":
                    val = self.stack.pop()
                    self.stack.append(-val)

                case "NOT":
                    val = self.stack.pop()
                    # Numbers: 0->True, nonzero->False; bools invert normally
                    if isinstance(val, (int, float)):
                        self.stack.append(val == 0)
                    else:
                        self.stack.append(not val)

                case "INC":
                    name = args[0]
                    if name not in self.locals:
                        raise VMError(f"Undefined variable '{name}'")
                    val, vartype = self.locals[name]
                    self.locals[name] = (val + 1, vartype)
                    self.stack.append(val) 

                case "DEC":
                    name = args[0]
                    if name not in self.locals:
                        raise VMError(f"Undefined variable '{name}'")
                    val, vartype = self.locals[name]
                    self.locals[name] = (val - 1, vartype)
                    self.stack.append(val) 

                case "DECLARE":
                    name, vartype = args[0], args[1]
                    val = self.stack.pop()
                    if name in self.locals:
                        raise VMError(f"Variable '{name}' already declared")
                    self.locals[name] = (val, vartype)

                case "STORE":
                    name = args[0]
                    val = self.stack.pop()
                    if name not in self.locals:
                        raise VMError(f"Assignment to undeclared variable '{name}'")
                    old_val, vartype = self.locals[name]
                    self.locals[name] = (val, vartype)

                case "LOAD":
                    name = args[0]  # could be "math.PI"
                    if name not in self.locals:
                        raise VMError(f"Undefined variable '{name}'")
                    val, _type = self.locals[name]
                    self.stack.append(val)


                case "PRINT":
                    n = int(args[0])  # number of arguments to print
                    if n > len(self.stack):
                        raise VMError(f"PRINT expected {n} values but stack has {len(self.stack)}")

                    # Pop n values (last pushed first, so reverse to print in original order)
                    vals = [self.stack.pop() for _ in range(n)][::-1]
                    print(*vals)

                case "JUMP":
                    self.pc = int(args[0])
                    continue

                case "JUMP_IF_FALSE":
                    target = int(args[0])
                    cond = self.stack.pop()
                    if isinstance(cond, (int, float)):# Numbers collapse to bools
                        cond = cond != 0
                    if not cond:
                        self.pc = target
                        continue

                case "HALT":
                    break

                case "IMPORT":
                    module_name = args[0]

                    if module_name in self._modules:
                        break

                    spec = importlib.util.spec_from_file_location(module_name, f"builtins/{module_name}.py")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    self._modules[module_name] = module

                    # populate locals with dotted names
                    funcs_dict = getattr(module, f"{module_name.upper()}_FUNCS", {})
                    for name, val in funcs_dict.items():
                        self.locals[f"{module_name}.{name}"] = (val, "function" if callable(val) else type(val).__name__)


                case "FUNC_BEGIN":
                    # Skip function body if running normally
                    # args: name, param_count
                    self.pc += 1
                    while self.pc < len(self.code):
                        next_op = self.code[self.pc][0]
                        if next_op == "FUNC_END":
                            break
                        self.pc += 1
                    continue  # skip executing function body

                case "FUNC_END":
                    # Nothing: return should handle exiting
                    pass

                case "CALL":
                    func_name, n_args = args
                    n_args = int(n_args)
                    arg_values = [self.stack.pop() for _ in range(n_args)][::-1]

                    # Lookup locals for user-defined functions / builtins
                    func_val, typ = self.locals.get(func_name, (None, None))
                    if typ == "function" and callable(func_val):
                        # Built-in Python function
                        result = func_val(*arg_values)
                        self.stack.append(result)
                    else:
                        # User-defined function: find FUNC_BEGIN index
                        func_pc = None
                        for idx, instr in enumerate(self.code):
                            if instr[0] == "FUNC_BEGIN" and instr[1] == func_name:
                                # idx points at FUNC_BEGIN; function body first instr is idx+1
                                func_pc = idx + 1
                                func_begin_idx = idx
                                break
                        if func_pc is None:
                            raise VMError(f"User function '{func_name}' not found")

                        # Read parameter count from FUNC_BEGIN tuple (third element)
                        param_count = int(self.code[func_begin_idx][2]) if len(self.code[func_begin_idx]) > 2 else 0

                        # Read parameter names from the next param_count instructions.
                        # Expect those to be DECLARE instructions emitted by the compiler.
                        param_names = []
                        for i in range(param_count):
                            decl_idx = func_pc + i
                            if decl_idx >= len(self.code):
                                raise VMError(f"Malformed function '{func_name}': missing parameter DECLAREs")
                            decl_instr = self.code[decl_idx]
                            if decl_instr[0] != "DECLARE":
                                raise VMError(f"Malformed function '{func_name}': expected DECLARE for parameter at bytecode index {decl_idx}, found {decl_instr[0]}")
                            # DECLARE format: ("DECLARE", name, vartype)
                            param_names.append(decl_instr[1])

                        # Save current pc+1 (next instruction after CALL) and locals snapshot on call stack
                        self.call_stack.append((self.pc + 1, self.locals.copy()))

                        # Install fresh locals and bind parameters
                        self.locals = {}
                        for name, val in zip(param_names, arg_values):
                            self.locals[name] = (val, "unknown")  # type info optional

                        # Jump to the first instruction of the function body (skip the param DECLAREs)
                        self.pc = func_pc + param_count
                        continue


                case "RETURN":
                    # Optional: push return value
                    ret_val = self.stack.pop() if self.stack else None

                    if not self.call_stack:
                        raise VMError("Return outside function")

                    self.pc, self.locals = self.call_stack.pop()
                    if ret_val is not None:
                        self.stack.append(ret_val)
                    continue



                case _:
                    raise VMError(f"Unknown opcode {op}")

            self.pc += 1
