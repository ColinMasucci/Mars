from typing import List, Tuple, Any

Instr = Tuple[str, ...]

class VMError(Exception): pass

class VM:
    def __init__(self, bytecode: List[Instr]):
        self.code = bytecode
        self.stack = []
        self.pc = 0
        self.locals = {}  # simple flat namespace for now

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

                case "STORE":
                    name = args[0]
                    val = self.stack.pop()
                    self.locals[name] = val

                case "LOAD":
                    name = args[0]
                    if name not in self.locals:
                        raise VMError(f"Undefined variable {name}")
                    self.stack.append(self.locals[name])

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
                    if not cond:
                        self.pc = target
                        continue

                case "HALT":
                    break

                case _:
                    raise VMError(f"Unknown opcode {op}")

            self.pc += 1
