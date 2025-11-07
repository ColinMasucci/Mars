from ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, If, While, VarDecl, UnaryOp

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
            statements.append(self.parse_statement())
        if printAST:
            for stmt in statements:
                self.print_ast(stmt)
        return Program(statements)
    
    def parse_statement(self):
        tok = self.current()

        # Handle typed variable declarations
        if tok.type in ("INT_KW", "FLOAT_KW", "BOOL_KW", "STRING_KW"):
            vartype = self.eat(tok.type).type.replace("_KW", "").lower()  # e.g., "INT_KW" → "int"
            name = self.eat("ID").value
            self.eat("ASSIGN")
            value = self.expr()
            stmt = VarDecl(vartype, name, value)

        # Handle if/else/while
        elif tok.type == "IF":
            return self.parse_if()
        elif tok.type == "WHILE":
            return self.parse_while()
        elif tok.type == "FOR":
            return self.parse_for()
        elif tok.type == "LBRACE":
            return self.parse_block()

        # Handle variable assignment like: x = expr;
        elif tok.type == "ID" and self.peek().type == "ASSIGN":
            next_tok = self.tokens[self.pos + 1]
            if next_tok.type == "ASSIGN":
                name = self.eat("ID").value
                self.eat("ASSIGN")
                value = self.expr()
                stmt = Assign(name, value)
        else:
            stmt = self.expr()
        
        # Expect a semicolon after the statement
        if self.current().type == "SEMI":
            self.eat("SEMI")
        else:
            raise SyntaxError(f"Expected ';' after statement, got {self.current().type}")

        return stmt
        

        
    
    def parse_if(self):
        self.eat("IF")
        condition = self.parse_condition() # parse the condition expression
        then_branch = self.parse_blockorstatement() #parse the then branch
        else_branch = None
        if self.current().type == "ELSE":
            self.eat("ELSE")
            else_branch = self.parse_blockorstatement()
        return If(condition, then_branch, else_branch)

    def parse_while(self):
        self.eat("WHILE")
        condition = self.parse_condition() # parse the condition expression
        body = self.parse_blockorstatement()
        return While(condition, body)
    
    def parse_condition(self):
        self.eat("LPAREN")
        if self.current().type == "RPAREN":
            raise SyntaxError("Empty condition in if/while statement")
        condition = self.expr() # parse the condition expression
        self.eat("RPAREN")
        return condition
    
    def parse_for(self):
        self.eat("FOR")
        self.eat("LPAREN")

        # init can be assignment or empty
        init = None
        if self.current().type != "SEMI":
            init = self.parse_simple_statement()
        self.eat("SEMI")

        # condition can be empty
        condition = None
        if self.current().type != "SEMI":
            condition = self.expr()
        self.eat("SEMI")

        # increment can be empty
        increment = None
        if self.current().type != "RPAREN":
            increment = self.parse_simple_statement()
        self.eat("RPAREN")

        body = self.parse_blockorstatement()

        # Transform for into equivalent while
        if condition is None:
            condition = BooleanLiteral(True)
        if increment is None:
            loop_body = body
        else:
            loop_body = Block([body, increment])

        if init is not None:
            return Block([init, While(condition, loop_body)])
        return While(condition, loop_body)
    
    def parse_simple_statement(self):
        """
        Parses a simple statement (assignment, variable declaration, or expression).
        Does NOT consume a trailing semicolon.
        """
        tok = self.current()
        # --- Variable declaration ---
        if tok.type in ("INT_KW", "FLOAT_KW", "STRING_KW", "BOOL_KW"):
            vartype = self.eat(tok.type).type.replace("_KW", "").lower()  # store type as lowercase string
            name = self.eat("ID").value
            value = None
            if self.current().type == "ASSIGN":
                self.eat("ASSIGN")
                value = self.expr()
            return VarDecl(vartype, name, value)
        # --- Assignment ---
        if tok.type == "ID" and self.peek().type == "ASSIGN":
            name = self.eat("ID").value
            self.eat("ASSIGN")
            value = self.expr()
            return Assign(name, value)
        # --- Otherwise treat as an expression statement ---
        return self.expr()


    
    def parse_block(self):
        stmts = []
        self.eat("LBRACE")
        while self.current().type != "RBRACE":
            stmts.append(self.parse_statement())
            if self.current().type == "EOF":
                raise SyntaxError("Expected '}' before end of file")
        self.eat("RBRACE")
        return Block(stmts)
    
    def parse_blockorstatement(self):
        if self.current().type == "LBRACE":
            return self.parse_block()
        else:
            return self.parse_statement()


    ### SHUNTING YARD ALGORITHM FOR EXPRESSIONS ###
    # operator table:
    # key -> (precedence, associativity, arity (num ops), role)
    # role is "prefix", "postfix", or "binary" — used mostly for clarity/debug
    # higher precedence number -> binds tighter
    global OP_INFO
    OP_INFO = {
        # postfix unary
        "INC":  (7, "left", 1, "postfix"),
        "DEC":  (7, "left", 1, "postfix"),

        # prefix unary
        "NEGATE": (6, "right", 1, "prefix"),  # unary negation
        "BANG":  (6, "right", 1, "prefix"),  # logical not

        # multiplicative
        "MUL":       (5, "left", 2, "binary"),
        "DIV":       (5, "left", 2, "binary"),

        # additive
        "PLUS":      (4, "left", 2, "binary"),
        "MINUS":     (4, "left", 2, "binary"),  # binary minus

        # exponentiation
        "POW": (6, "right", 2, "binary"),

    }


    def expr(self):
        """Parse an expression up to a stop token (SEMI, RPAREN, COMMA, RBRACE)."""
        return self.parse_expression(stop_tokens={"SEMI", "RPAREN", "COMMA", "RBRACE"})

    def parse_expression(self, stop_tokens):
        """Shunting-yard implementation to parse expressions with operator precedence.\n
        stop_tokens: set of token types that indicate the end of the expression."""

        output = []   # AST node stack
        ops = []      # operator stack (items: dicts with fields "tok", "key")

        def peek_ops():
            return ops[-1] if ops else None

        def is_token_end():
            return self.current().type in stop_tokens or self.current().type == "EOF"

        # Sets our context, we need to know whether the next operator we see should be treated as prefix if we reach operators
        # At the start we are in a "prefix-allowed" context (i.e., we expect a unary/prefix or primary) because we haven't seen a left operand yet
        expect_operand = True

        while not is_token_end():
            tok = self.current()

            # Literals / identifiers / function calls / parenthesized expressions
            if tok.type in ("INT", "FLOAT", "STRING", "TRUE", "FALSE", "ID", "LPAREN"):
                # If it's a parenthesized expression -> parse inner expression recursively
                if tok.type == "LPAREN":
                    self.eat("LPAREN")
                    # parse inner expression until RPAREN
                    node = self.parse_expression(stop_tokens={"RPAREN"})
                    self.eat("RPAREN")
                    output.append(node)
                    expect_operand = False
                    continue

                # Literals
                if tok.type == "INT":
                    self.eat("INT")
                    output.append(NumberLiteral(int(tok.value)))
                    expect_operand = False
                    continue
                if tok.type == "FLOAT":
                    self.eat("FLOAT")
                    output.append(NumberLiteral(float(tok.value)))
                    expect_operand = False
                    continue
                if tok.type == "STRING":
                    self.eat("STRING")
                    output.append(StringLiteral(tok.value.strip('"')))
                    expect_operand = False
                    continue
                if tok.type == "TRUE":
                    self.eat("TRUE")
                    output.append(BooleanLiteral(True))
                    expect_operand = False
                    continue
                if tok.type == "FALSE":
                    self.eat("FALSE")
                    output.append(BooleanLiteral(False))
                    expect_operand = False
                    continue

                # Identifier: variable or function call
                if tok.type == "ID":
                    id_tok = self.eat("ID")
                    # function call?
                    if self.current().type == "LPAREN":
                        # parse call arguments (possibly empty)
                        self.eat("LPAREN")
                        args = []
                        if self.current().type != "RPAREN":
                            while True:
                                arg = self.parse_expression(stop_tokens={"COMMA", "RPAREN"})
                                args.append(arg)
                                if self.current().type == "COMMA":
                                    self.eat("COMMA")
                                    continue
                                break
                        self.eat("RPAREN")
                        output.append(Call(func=Var(id_tok.value), args=args))
                    else:
                        output.append(Var(id_tok.value))
                    expect_operand = False
                    continue

            # Comma — end of expression in argument lists; stop and let caller handle (TODO: implement)
            if tok.type == "COMMA":
                # exit to allow caller (arg parser) to consume comma
                break

            # Operators
            # Distinguish prefix unary vs binary vs postfix by expect_operand context
            if tok.type in ("PLUS", "MINUS", "BANG", "INC", "DEC", "MUL", "DIV", "POW"):
                if expect_operand:
                    # we are expecting/allowing a prefix/unary operator
                    if expect_operand:
                        if tok.type == "MINUS":
                            key = "NEGATE"  # lexer does not know context, so we convert to NEGATE here
                            self.eat("MINUS")
                        elif tok.type == "BANG":
                            key = "BANG"
                            self.eat("BANG")
                    else:
                        # INC/DEC are not allowed as prefix per your requirement
                        if tok.type in ("INC", "DEC"):
                            raise SyntaxError(f"Prefix {tok.type} not supported as a prefix operation. Please use postfix form (ex: myVar++;) at {tok.position}")
                        # PLUS as prefix is allowed (no-op) but we'll treat it as unary plus (we can ignore it)
                        if tok.type == "PLUS":
                            # eat it and do nothing (unary plus)
                            self.eat("PLUS")
                            continue
                        # otherwise unexpected
                        raise SyntaxError(f"Unexpected prefix operator {tok.type} at {tok.position}")
                else:
                    # expecting a binary or postfix operator
                    # check for postfix (INC/DEC) — valid only in this position (after an operand)
                    if tok.type in ("INC", "DEC"):
                        # postfix binding
                        key = f"{tok.type}"
                        self.eat(tok.type)
                        # Because postfix has very high precedence and arity 1, we will push it on ops
                        # but we can also apply it immediately: treat like normal operator push (below)
                    else:
                        # it's binary (MUL, DIV, PLUS, MINUS)
                        key = tok.type
                        self.eat(tok.type)

                # now we have 'key' for operator; apply shunting-yard operator popping rules
                # get info for this operator
                if key not in OP_INFO:
                    raise SyntaxError(f"Unknown operator form {key} at {tok.position}")
                prec, assoc, arity, role = OP_INFO[key]

                # While there is an operator on the ops stack with greater precedence, or equal precedence and left-associative, pop and apply it.
                while True:
                    top = peek_ops()
                    if not top or top["tok"].type == "LPAREN":
                        break
                    top_key = top["key"]
                    top_prec, top_assoc, _, _ = OP_INFO[top_key]
                    if (top_prec > prec) or (top_prec == prec and assoc == "left"):
                        # pop and apply top
                        self._apply_op(output, ops.pop()["key"])
                    else:
                        break

                # push current operator
                ops.append({"tok": tok, "key": key})
                # after an operator, we expect an operand next if it's prefix or binary operator;
                # but if it was postfix we just consumed it and now we do not expect operand.
                expect_operand = (role in ("prefix", "binary"))
                continue

            # 4) Parentheses closing / unexpected tokens
            # If we reach here and didn't match anything, break to avoid infinite loop
            break

        # end loop: pop remaining operators until empty
        while ops:
            top = ops.pop()
            if top["tok"].type == "LPAREN":
                raise SyntaxError("Mismatched '('")
            self._apply_op(output, top["key"])

        if not output:
            raise SyntaxError(f"Expected expression but found {self.current().type} at {self.current().position}")

        if len(output) != 1:
            # should reduce to single AST node; if not, it's an error
            raise SyntaxError("Expression parsing error: output stack did not convert to AST correctly. Possible causes: incorrect syntax, recieved an empty expression, missed operators during process")

        return output[0]

    def _apply_op(self, output_stack, op_key):
        """Helper to consume operator 'op_key' and build AST nodes using nodes from output_stack.
        \nMutates output_stack (list)."""

        if op_key not in OP_INFO:
            raise SyntaxError(f"Internal error: unknown operator {op_key}")
        prec, assoc, arity, role = OP_INFO[op_key]

        if arity == 2:
            # binary operator
            if len(output_stack) < 2:
                raise SyntaxError("Not enough operands for binary operator")
            right = output_stack.pop()
            left = output_stack.pop()
            # use op_key as operator name for BinaryOp (keep original token names like "PLUS")
            output_stack.append(BinaryOp(op_key, left, right))
            return

        if arity == 1:
            if len(output_stack) < 1:
                raise SyntaxError("Not enough operands for unary operator")
            operand = output_stack.pop()
            # Handle postfix INC/DEC specially if needed (they act on variables)
            if op_key == "INC":
                output_stack.append(UnaryOp("INC", operand))
                return
            if op_key == "DEC":
                output_stack.append(UnaryOp("DEC", operand))
                return
            if op_key == "NEGATE":
                output_stack.append(UnaryOp("NEGATE", operand))
                return
            if op_key == "BANG":
                output_stack.append(UnaryOp("BANG", operand))
                return
            raise SyntaxError(f"Unhandled unary op {op_key}")









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