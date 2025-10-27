from ast_nodes import NumberLiteral, StringLiteral, BinaryOp, Call, Program, Var

class Parser:
    #We pass in the tokens which we got from the lexer
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # Get the current token we are parsing
    def current(self):
        return self.tokens[self.pos]

    # consume the current token then increment the pos
    def eat(self, type_):
        tok = self.current()
        if tok.type == type_:
            self.pos += 1
            return tok
        raise SyntaxError(f"Expected {type_} at position {tok.position}, got {tok.type}")

    # parse an entire given program as a Program, using ; as the delimeter
    def parse(self, printAST=False):
        statements = []
        while self.current().type != "EOF":
            stmt = self.statement()
            statements.append(stmt)
            if self.current().type == "SEMI":
                self.eat("SEMI")  
            elif self.current().type != "EOF":
                raise SyntaxError(f"Expected ';' got {self.current().type}")
        if printAST:
            for stmt in statements:
                self.print_ast(stmt)
        return Program(statements)
    
    def statement(self):
        tok = self.current()
        if tok.type == "PRINT": #print moved to call (handled in term)
            pass # Placeholder for future statement handling
        else:
            return self.expr()

    def expr(self):
        node = self.term()
        while self.current().type in ("PLUS", "MINUS", "MUL", "DIV"):
            op = self.current().type
            self.eat(op)
            right = self.term()
            node = BinaryOp(op, node, right)
        return node

    def term(self):
        tok = self.current()
        if tok.type == "INT":
            self.eat("INT")
            return NumberLiteral(int(tok.value))
        elif tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberLiteral(float(tok.value))
        elif tok.type == "STRING":
            self.eat("STRING")
            return StringLiteral(tok.value.strip('"'))
        
        elif tok.type == "ID":
            # Possible function call
            id_tok = self.eat("ID")
            if self.current().type == "LPAREN":
                self.eat("LPAREN")
                args = []
                if self.current().type != "RPAREN":
                    args.append(self.expr())
                    while self.current().type == "COMMA":
                        self.eat("COMMA")
                        args.append(self.expr())
                self.eat("RPAREN")
                return Call(func=Var(id_tok.value), args=args)
            else:
                # variable reference
                return Var(id_tok.value)


        elif tok.type == "LPAREN":
            self.eat("LPAREN")
            node = self.expr()
            self.eat("RPAREN")
            return node
        else:
            raise SyntaxError(f"Unexpected token {tok.type} at {tok.position}")

    def print_ast(self, node, indent=0):
        if indent == 0:
            print("AST Structure:")
        prefix = "  " * indent
        match node:
            case NumberLiteral(value):
                print(f"{prefix}NumberLiteral({value})")
            case StringLiteral(value):
                print(f"{prefix}StringLiteral({value})")
            case BinaryOp(op, left, right):
                print(f"{prefix}BinaryOp({op})")
                self.print_ast(left, indent + 1)
                self.print_ast(right, indent + 1)
            case Call(func, args):
                func_name = func.name if isinstance(func, Var) else str(func)
                print(f"{prefix}Call({func_name})")
                for arg in args:
                    self.print_ast(arg, indent + 1)
            case _:
                print(f"{prefix}Unknown node type: {node}")
        if indent == 0:
            print("\n")