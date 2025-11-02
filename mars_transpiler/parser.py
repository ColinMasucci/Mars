from ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, If, While

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

            needs_semi = True
            if (isinstance(stmt, If) or isinstance(stmt, While) or isinstance(stmt, Block)): #cases for if statement needs a ';'. (should probably implement a better way)
                needs_semi = False

            if needs_semi and self.current().type == "SEMI":
                self.eat("SEMI")
            elif needs_semi:
                raise SyntaxError(f"Expected ';' got {self.current().type}")
        if printAST:
            for stmt in statements:
                self.print_ast(stmt)
        return Program(statements)
    
    def statement(self):
        tok = self.current()

        # Handle if/else/while
        if tok.type == "IF":
            return self.if_statement() #helper defined below
        elif tok.type == "WHILE":
            return self.while_statement() #helper defined below

        # Handle variable assignment like: x = expr;
        if tok.type == "ID" and self.peek().type == "ASSIGN":
            next_tok = self.tokens[self.pos + 1]
            if next_tok.type == "ASSIGN":
                name = self.eat("ID").value
                self.eat("ASSIGN")
                value = self.expr()
                return Assign(name, value)
        else:
            return self.expr()
        
    
    def if_statement(self):
        self.eat("IF")
        self.eat("LPAREN")
        condition = self.expr() # parse the condition expression
        self.eat("RPAREN")

        if self.current().type == "LBRACE":
            then_branch = self.parse_block() # for if the then_branch is a block
        else:
            raise SyntaxError(f"Expected '{{' got {self.current().type}")
        else_branch = None
        if self.current().type == "ELSE":
            self.eat("ELSE")

            if self.current().type == "LBRACE":
                else_branch = self.parse_block() # for if the else_branch is a block
            else:
                raise SyntaxError(f"Expected '{{' got {self.current().type}")
        
        return If(condition, then_branch, else_branch)

    def while_statement(self):
        self.eat("WHILE")
        self.eat("LPAREN")
        condition = self.expr() # parse the condition expression
        self.eat("RPAREN")
        if self.current().type == "LBRACE":
            body = self.parse_block() # for if the body is a block
        else:
            raise SyntaxError(f"Expected '{{' got {self.current().type}")
        return While(condition, body)
    
    def parse_block(self):
        stmts = []
        self.eat("LBRACE")
        while self.current().type != "RBRACE":
            stmt = self.statement()
            stmts.append(stmt)

            needs_semi = True
            if (isinstance(stmt, If) or isinstance(stmt, While) or isinstance(stmt, Block)): #cases for if statement needs a ';'. (should probably implement a better way)
                needs_semi = False

            if self.current().type == "EOF":
                raise SyntaxError("Expected '}' before end of file")
            if needs_semi and self.current().type == "SEMI":
                self.eat("SEMI")
            elif needs_semi:
                raise SyntaxError(f"Expected ';' got {self.current().type}")

        self.eat("RBRACE")
        return Block(stmts)


    def expr(self):
        node = self.term()
        while self.current().type in ("PLUS", "MINUS"):
            op = self.current().type
            self.eat(op)
            right = self.term()
            node = BinaryOp(op, node, right)
        return node

    def term(self):
        node = self.factor()
        while self.current().type in ("MUL", "DIV"):
            op = self.current().type
            self.eat(op)
            right = self.factor()
            node = BinaryOp(op, node, right)
        return node

    def factor(self):
        tok = self.current()

        # Handle unary +/-
        if tok.type in ("PLUS", "MINUS"):
            op = tok.type
            self.eat(op)
            node = self.factor()
            # Treat unary as multiplying by -1 for MINUS, or just return node for PLUS
            if op == "MINUS":
                return BinaryOp("MUL", NumberLiteral(-1), node)
            return node

        # Parentheses have highest precedence
        if tok.type == "LPAREN":
            self.eat("LPAREN")
            node = self.expr()
            self.eat("RPAREN")
            return node

        # Literals and identifiers
        if tok.type == "INT":
            self.eat("INT")
            return NumberLiteral(int(tok.value))
        elif tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberLiteral(float(tok.value))
        elif tok.type == "STRING":
            self.eat("STRING")
            return StringLiteral(tok.value.strip('"'))
        elif tok.type == "TRUE":
            self.eat("TRUE")
            return BooleanLiteral(True)
        elif tok.type == "FALSE":
            self.eat("FALSE")
            return BooleanLiteral(False)
        elif tok.type == "ID":
            id_tok = self.eat("ID")
            if self.current().type == "LPAREN":
                # function call
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
                return Var(id_tok.value)

        raise SyntaxError(f"Unexpected token {tok.type} at {tok.position}")

        

    def peek(self, offset=1):
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return self.tokens[-1]  # return EOF token safely





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
            case Assign(name, value):
                print(f"{prefix}Assign({name})")
                self.print_ast(value, indent + 1)
            case _:
                print(f"{prefix}Unknown node type: {node}")
        if indent == 0:
            print("\n")