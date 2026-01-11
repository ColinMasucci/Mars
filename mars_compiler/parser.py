from ast_nodes import ArrayAccess, ArrayLiteral, DictLiteral, NumberLiteral, StringLiteral, BooleanLiteral, BinaryOp, Call, Program, Block, Var, Assign, AugAssign, If, While, VarDecl, UnaryOp, Import, FuncDecl, Return, ComponentDef, SubcomponentDecl, ClassDecl, FieldDecl, MethodDecl, MemberAccess, RequirementSpec, RequirementParam, RequirementFunction

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
        components = []
        classes = []
        while self.current().type != "EOF":
                if self.current().type == "COMPONENT":
                    components.append(self.parse_component())
                elif self.current().type == "CLASS":
                    classes.append(self.parse_class())
                else:
                    statements.append(self.parse_statement())
        if printAST:
            for stmt in statements:
                self.print_ast(stmt)
        return Program(statements, components, classes)
    

    def parse_component(self):
        self.eat("COMPONENT")
        name = self.eat("ID").value

        parent = None
        if self.current().type == "EXTENDS":
            self.eat("EXTENDS")
            parent = self.eat("ID").value

        self.eat("LBRACE")

        subcomponents = []
        parameters = []
        functions = []

        while not self.current().type == "RBRACE":
            if self.current().type == "SUBCOMPONENTS":
                self.eat("SUBCOMPONENTS")
                subcomponents = self.parse_subcomponents_block()
            elif self.current().type == "PARAMETERS":
                self.eat("PARAMETERS")
                parameters = self.parse_parameters_block()
            elif self.current().type == "FUNCTIONS":
                self.eat("FUNCTIONS")
                functions = self.parse_functions_block()
            else:
                raise SyntaxError(self.peek(), "Unexpected token in component body")

        self.eat("RBRACE")


        return ComponentDef(name, parent, subcomponents, parameters, functions)

    def parse_subcomponents_block(self):
        self.eat("LBRACE")
        subcomponents = []

        while not self.current().type == "RBRACE":
            comp_type = self.eat("ID").value
            name = self.eat("ID").value

            bindings = []
            if self.current().type == "LPAREN":
                self.eat("LPAREN")
                if self.current().type != "RPAREN":
                    while True:
                        bname = self.eat("ID").value
                        self.eat("ASSIGN")
                        bval = self.parse_expression({"COMMA", "RPAREN"})
                        bindings.append((bname, bval))
                        if self.current().type == "COMMA":
                            self.eat("COMMA")
                            continue
                        break
                self.eat("RPAREN")

            self.eat("SEMI")
            subcomponents.append(SubcomponentDecl(comp_type, name, bindings))

        self.eat("RBRACE")
        return subcomponents

    def parse_parameters_block(self):
        params = []

        self.eat("LBRACE")

        while not self.current().type == "RBRACE":
            param = self.parse_var_decl()
            params.append(param)

        self.eat("RBRACE")
        return params


    def parse_functions_block(self):
        self.eat("LBRACE")
        functions = []

        while not self.current().type == "RBRACE":
            # function return type and name
            rettype = self.parse_type()
            name = self.eat("ID").value

            func = self.parse_function(rettype, name)
            functions.append(func)

        self.eat("RBRACE")
        return functions



    def parse_dotted_var(self):
        """Parse a variable or dotted access like a.b.c into MemberAccess chain"""
        id_tok = self.eat("ID")
        node = Var(id_tok.value)

        while self.current().type == "DOT":
            self.eat("DOT")
            attr = self.eat("ID").value
            node = MemberAccess(node, attr)

        return node
    
    def parse_assignable(self):
        """
        Parse something that can appear on the LEFT of '='
        Examples:
        x
        obj.field
        arr[0]
        matrix[1][2]
        """
        node = self.parse_dotted_var()

        while self.current().type == "LBRACKET":
            self.eat("LBRACKET")
            index = self.parse_expression(stop_tokens={"RBRACKET"})
            self.eat("RBRACKET")
            node = ArrayAccess(node, index)

        return node

    
    def parse_statement(self):
        tok = self.current()

        # --- IMPORT ---
        if tok.type == "IMPORT":
            self.eat("IMPORT")
            module_name = self.eat("ID").value
            self.eat("SEMI")
            return Import(module_name)

        # --- RETURN ---
        if tok.type == "RETURN":
            self.eat("RETURN")
            value = None
            if self.current().type not in ("SEMI", "RBRACE"):
                value = self.expr()
            self.eat("SEMI")
            return Return(value)

        # --- IF ---
        if tok.type == "IF":
            stmt = self.parse_if()
            return stmt

        # --- WHILE ---
        if tok.type == "WHILE":
            stmt = self.parse_while()
            return stmt

        # --- FOR ---
        if tok.type == "FOR":
            stmt = self.parse_for()
            return stmt

        # --- BLOCK ---
        if tok.type == "LBRACE":
            stmt = self.parse_block()
            return stmt

        # --- VAR / FUNC DECLARATION (supports const and user types) ---
        if tok.type in ("CONST_KW","INT_KW","FLOAT_KW","BOOL_KW","STRING_KW","VOID_KW","DICT_KW","ID"):
            save_pos = self.pos
            readonly = False
            if tok.type == "CONST_KW":
                self.eat("CONST_KW")
                readonly = True
            try:
                vartype = self.parse_type()
            except SyntaxError:
                # not a declaration
                self.pos = save_pos
                readonly = False
            else:
                if self.current().type == "ID":
                    name = self.eat("ID").value
                    if self.current().type == "LPAREN":
                        if readonly:
                            raise SyntaxError("Functions cannot be declared const")
                        return self.parse_function(vartype, name)
                    value = None
                    if self.current().type == "ASSIGN":
                        self.eat("ASSIGN")
                        value = self.expr()
                    decl = VarDecl(vartype, name, value, readonly)
                    self.eat("SEMI")
                    return decl
                else:
                    # not actually a declaration; rewind
                    self.pos = save_pos
                    readonly = False

        # --- ASSIGNMENT OR EXPRESSION ---
        if tok.type in ("ID", "LPAREN", "LBRACKET"):
            save_pos = self.pos
            if tok.type == "ID":
                target = self.parse_assignable()
                if self.current().type in ("ASSIGN", "PLUS_ASSIGN", "MINUS_ASSIGN", "MUL_ASSIGN", "DIV_ASSIGN"):
                    op_tok = self.current().type
                    self.eat(op_tok)
                    value = self.expr()
                    if op_tok == "ASSIGN":
                        stmt = Assign(target, value)
                    else:
                        op_map = {
                            "PLUS_ASSIGN": "PLUS",
                            "MINUS_ASSIGN": "MINUS",
                            "MUL_ASSIGN": "MUL",
                            "DIV_ASSIGN": "DIV",
                        }
                        stmt = AugAssign(target, op_map[op_tok], value)
                    self.eat("SEMI")
                    return stmt
                # Roll back and treat as expression
                self.pos = save_pos

            stmt = self.expr()
            self.eat("SEMI")
            return stmt

        # --- Anything else is invalid ---
        raise SyntaxError(f"Unexpected token {tok.type} at position {tok.position}")
    
    def parse_var_decl(self, require_semi=True, readonly=False):
        vartype = self.parse_type()
        name = self.eat("ID").value

        value = None
        if self.current().type == "ASSIGN":
            self.eat("ASSIGN")
            value = self.expr()

        decl = VarDecl(vartype, name, value, readonly)

        if require_semi:
            self.eat("SEMI")

        return decl

    
    # Parse types (Used in variable and function declarations above) Ex. int, float, dict<int,string>, string[][], dict<string,dict<int,float>>[]
    def parse_type(self):
        tok = self.current()

        # Primitive, dict, or void
        if tok.type in ("INT_KW","FLOAT_KW","BOOL_KW",
                        "STRING_KW","VOID_KW","DICT_KW"):

            base = self.eat(tok.type).type.replace("_KW","").lower()

            # dict<K,V>
            if base == "dict":
                self.eat("LT")
                key = self.parse_type()
                self.eat("COMMA")
                val = self.parse_type()
                self.eat("GT")
                base = f"dict<{key},{val}>"

            # array suffix: int[][], dict<int,string>[][]
            while self.current().type == "LBRACKET":
                self.eat("LBRACKET")
                self.eat("RBRACKET")
                base += "[]"

            return base

        # User-defined types (This is for later when we add classes/structs) (The typechecker should handle checking if these types exist)
        elif tok.type == "ID":
            return self.eat("ID").value

        else:
            raise SyntaxError(f"Unexpected type token: {tok.type}")


        
    def parse_function(self, rettype, name):
        # Parameter list
        self.eat("LPAREN")
        params = []

        if self.current().type != "RPAREN":
            while True:
                ptype = self.parse_type()

                if ptype == "void":
                    raise SyntaxError("Parameter type cannot be void")

                pname = self.eat("ID").value
                params.append((ptype, pname))

                if self.current().type == "COMMA":
                    self.eat("COMMA")
                else:
                    break

        self.eat("RPAREN")

        # Body may be omitted (prototype) when followed by ';'
        if self.current().type == "SEMI":
            self.eat("SEMI")
            body = None
        else:
            # Body must be a block
            body = self.parse_block()

        return FuncDecl(rettype, name, params, body)
    


    def parse_import(self):
        self.eat("IMPORT")
        module_name = self.eat("ID").value  # we only support single module imports for now
        stmt = Import(module_name)
        #self.eat("SEMI")
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
        # --- Variable declaration (supports const and user types) ---
        if tok.type in ("CONST_KW","INT_KW","FLOAT_KW","STRING_KW","BOOL_KW","ID","DICT_KW","VOID_KW"):
            save_pos = self.pos
            readonly = False
            if tok.type == "CONST_KW":
                self.eat("CONST_KW")
                readonly = True
            try:
                vartype = self.parse_type()
            except SyntaxError:
                self.pos = save_pos
                readonly = False
            else:
                if self.current().type == "ID":
                    name = self.eat("ID").value
                    value = None
                    if self.current().type == "ASSIGN":
                        self.eat("ASSIGN")
                        value = self.expr()
                    return VarDecl(vartype, name, value, readonly)
                else:
                    self.pos = save_pos
                    readonly = False


        # --- Assignment ---
        if tok.type == "ID":
            save_pos = self.pos
            target = self.parse_assignable()
            if self.current().type in ("ASSIGN", "PLUS_ASSIGN", "MINUS_ASSIGN", "MUL_ASSIGN", "DIV_ASSIGN"):
                op_tok = self.current().type
                self.eat(op_tok)
                value = self.expr()
                if op_tok == "ASSIGN":
                    return Assign(target, value)
                op_map = {
                    "PLUS_ASSIGN": "PLUS",
                    "MINUS_ASSIGN": "MINUS",
                    "MUL_ASSIGN": "MUL",
                    "DIV_ASSIGN": "DIV",
                }
                return AugAssign(target, op_map[op_tok], value)
            self.pos = save_pos

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
    # precedence is an integer (higher number = higher precedence), We perform operations with higher precedence first.
    # associativity is "left" or "right" meaning if two operators of same precedence appear, which one to apply first (ex. 2^3^4 is right associative = 2^(3^4) vs 2*3*4 is left associative = (2*3)*4).
    # arity is number of operands/numbers used for operation (1 for unary, 2 for binary)
    # role is "prefix", "postfix", or "binary" — used mostly for clarity/debug
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

        # comparison
        "LT":   (3, "left", 2, "binary"),
        "GT":   (3, "left", 2, "binary"),
        "LEQ":  (3, "left", 2, "binary"),
        "GEQ":  (3, "left", 2, "binary"),

        # equality
        "EQ":   (2, "left", 2, "binary"),
        "NEQ":  (2, "left", 2, "binary"),

        # logical
        "AND":  (1, "left", 2, "binary"),
        "OR":   (0, "left", 2, "binary"),

        # exponentiation
        "POW": (6, "right", 2, "binary"),

    }


    def expr(self):
        """Parse an expression up to a stop token (SEMI, RPAREN, COMMA, RBRACE)."""
        return self.parse_expression(stop_tokens={"SEMI", "RPAREN", "COMMA", "RBRACE"})


    def parse_expression(self, stop_tokens):
        """Shunting-yard implementation to parse expressions with operator precedence.
        stop_tokens: set of token types that indicate the end of the expression."""

        output = [self.parse_prefix()] # initial operand (If we see a prefix operator, we must immediately parse the thing it belongs to and push that result to the output first.)
        ops = []    # operator stack

        # While not at end of expression, start implement shunting-yard
        while self.current().type not in stop_tokens and self.current().type != "EOF": 

            if self.current().type not in OP_INFO: # For Unrecognized operators, Quit parsing
                break
            
            # Get current token info
            op_tok = self.current()
            key = op_tok.type
            prec, assoc, _, _ = OP_INFO[key]
            self.eat(op_tok.type)

            # While there is an operator on the ops stack with greater precedence (Ex. if we have * on the ops stack while the current_op/op_tok is +), 
            # or equal precedence and left-associative (Ex. if we have + on the ops stack while the current_op/op_tok is +),
            # pop and apply it.
            while ops:
                top = ops[-1]
                top_prec, _, _, _ = OP_INFO[top]

                if (top_prec > prec) or (top_prec == prec and assoc == "left"):
                    self._apply_op(output, ops.pop())
                else:
                    break
            
            # Otherwise, push the current operator onto the ops stack
            ops.append(key)
            if self.current().type in stop_tokens or self.current().type == "EOF":
                raise SyntaxError(f"Missing operand after {key} at {op_tok.position}")
            output.append(self.parse_prefix())

        # After we reach the end of the expression, pop and apply all remaining operators to finish shunting-yard
        while ops:
            self._apply_op(output, ops.pop())

        if not output:
            raise SyntaxError(f"Expected expression but found {self.current().type} at {self.current().position}")
        
        if len(output) != 1:
            # should reduce to single AST node; if not, it's an error
            raise SyntaxError("Expression parsing error: output stack did not convert to AST correctly. Possible causes: incorrect syntax, recieved an empty expression, missed operators during process")

        return output[0]
    
    # Prefix unary operators, then return to postfix/primary parsing
    # Note: When calling this function, 
    #       First all prefix operators will be consumed, 
    #       then the primary expression will be parsed,
    #       then any postfix operators will be applied to the primary expression.
    def parse_prefix(self):
        tok = self.current()

        if tok.type == "MINUS":       # unary negation
            self.eat("MINUS")
            return UnaryOp("NEGATE", self.parse_prefix())

        if tok.type == "BANG":        # logical not
            self.eat("BANG")
            return UnaryOp("BANG", self.parse_prefix())

        if tok.type == "PLUS":        # unary plus (does nothing, but valid)
            self.eat("PLUS")
            return self.parse_prefix()
        
        # Otherwise, parse primary and then postfix
        return self.parse_postfix(self.parse_primary())

    # Postfix unary operators and array indexing
    def parse_postfix(self, node):
        while True:
            # array indexing
            if self.current().type == "LBRACKET":
                self.eat("LBRACKET")
                index = self.parse_expression({"RBRACKET"})
                if self.current().type != "RBRACKET":
                    raise SyntaxError(f"Expected ']' at {self.current().position}")
                self.eat("RBRACKET")
                node = ArrayAccess(node, index)
                continue

            # postfix ++ / --
            if self.current().type in ("INC", "DEC"):
                op = self.eat(self.current().type).type
                node = UnaryOp(op, node)
                continue
            break
        return node

    # Primary expressions: literals, grouped expressions, variables, function calls
    def parse_primary(self):
        tok = self.current()

        # DICTIONARY LITERAL
        if tok.type == "LBRACE":
            self.eat("LBRACE")
            pairs = []

            if self.current().type != "RBRACE":
                while True:
                    # Parse key
                    key = self.parse_expression({"COLON"})

                    if self.current().type != "COLON":
                        raise SyntaxError(f"Expected ':' in dictionary at {self.current().position}")

                    self.eat("COLON")

                    # Parse value
                    value = self.parse_expression({"COMMA", "RBRACE"})

                    pairs.append((key, value))

                    if self.current().type == "COMMA":
                        self.eat("COMMA")
                        continue # if theres a comma, continue parsing more key:value pairs
                    break
            
            self.eat("RBRACE")
            return DictLiteral(pairs)


        # ARRAY LITERAL
        if tok.type == "LBRACKET":
            self.eat("LBRACKET")
            elements = []

            if self.current().type != "RBRACKET":
                while True:
                    elements.append(self.parse_expression({"COMMA", "RBRACKET"}))
                    if self.current().type == "COMMA":
                        self.eat("COMMA")
                        continue # if theres a comma, continue parsing more elements
                    break

            self.eat("RBRACKET")
            return ArrayLiteral(elements)

        # GROUPED EXPRESSION (parentheses)
        if tok.type == "LPAREN":
            self.eat("LPAREN")
            if self.current().type == "RPAREN":
                raise SyntaxError(f"Empty parentheses at {self.current().position}")
            node = self.parse_expression({"RPAREN"})
            if self.current().type != "RPAREN":
                raise SyntaxError(f"Expected ')' at {self.current().position}")
            self.eat("RPAREN")
            return node

        # LITERALS
        if tok.type == "INT":
            self.eat("INT")
            return NumberLiteral(int(tok.value))

        if tok.type == "FLOAT":
            self.eat("FLOAT")
            return NumberLiteral(float(tok.value))

        if tok.type == "STRING":
            self.eat("STRING")
            return StringLiteral(tok.value.strip('"'))

        if tok.type == "TRUE":
            self.eat("TRUE")
            return BooleanLiteral(True)

        if tok.type == "FALSE":
            self.eat("FALSE")
            return BooleanLiteral(False)

        # VARIABLE / CALL / ACCESS
        if tok.type == "ID":
            node = self.parse_dotted_var()

            # function / method / constructor call
            if self.current().type == "LPAREN":
                self.eat("LPAREN")
                args = []

                if self.current().type != "RPAREN":
                    while True:
                        args.append(self.parse_expression({"COMMA","RPAREN"}))
                        if self.current().type == "COMMA":
                            self.eat("COMMA")
                            continue
                        break

                self.eat("RPAREN")
                node = Call(node, args)

            return node

        raise SyntaxError(f"Unexpected token {tok.type} in expression")


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
            case AugAssign(name, op, value):
                print(f"{prefix}AugAssign({op} {name})")
                self.print_ast(value, indent + 1)
            case VarDecl(vartype, name, value):
                print(f"{prefix}VarDecl({vartype} {name})")
                if value:
                    self.print_ast(value, indent+1)
            case ArrayLiteral(elements):
                print(f"{prefix}ArrayLiteral([")
                for el in elements:
                    self.print_ast(el, indent+1)
                print(f"{prefix}])")
            case ArrayAccess(array, index):
                print(f"{prefix}ArrayAccess")
                self.print_ast(array, indent+1)
                self.print_ast(index, indent+1)
            case DictLiteral(pairs):
                print(f"{prefix}DictLiteral{{")
                for k, v in pairs:
                    print(f"{prefix}  Key:")
                    self.print_ast(k, indent + 2)
                    print(f"{prefix}  Value:")
                    self.print_ast(v, indent + 2)
                print(f"{prefix}}}")

            case _:
                print(f"{prefix}Unknown node type: {node}")
        if indent == 0:
            print("\n")
    def parse_class(self):
        self.eat("CLASS")
        name = self.eat("ID").value
        self.eat("LBRACE")

        fields = []
        methods = []
        constructor = None
        requirements = []

        while self.current().type != "RBRACE":
            if self.current().type == "REQUIREMENTS":
                self.eat("REQUIREMENTS")
                requirements = self.parse_requirements_block()
                continue
            is_const = False
            if self.current().type == "CONST_KW":
                self.eat("CONST_KW")
                is_const = True

            # Constructor shorthand: ClassName(params) without a leading return type
            if self.current().type == "ID" and self.current().value == name and self.peek().type == "LPAREN":
                self.eat("ID")
                ctor = self.parse_function(name, name)
                constructor = MethodDecl(name, name, ctor.params, ctor.body, True)
                continue

            # type
            vartype = self.parse_type()
            member_name = self.eat("ID").value

            # constructor (name == class name and followed by LPAREN)
            if member_name == name and self.current().type == "LPAREN":
                # treat as constructor
                ctor = self.parse_function(vartype, member_name)
                ctor = MethodDecl(vartype, member_name, ctor.params, ctor.body, True)
                constructor = ctor
                continue

            if self.current().type == "LPAREN":
                # method
                fn = self.parse_function(vartype, member_name)
                methods.append(MethodDecl(vartype, member_name, fn.params, fn.body, False))
            else:
                # field
                value = None
                if self.current().type == "ASSIGN":
                    self.eat("ASSIGN")
                    value = self.expr()
                self.eat("SEMI")
                fields.append(FieldDecl(vartype, member_name, value, is_const))

        self.eat("RBRACE")
        return ClassDecl(name, fields, methods, constructor, requirements)

    def parse_requirements_block(self):
        self.eat("LBRACE")
        requirements = []

        while self.current().type != "RBRACE":
            requirements.append(self.parse_requirement_item())

        self.eat("RBRACE")
        return requirements

    def parse_requirement_item(self):
        spec = self.parse_requirement_spec()
        self.eat("SEMI")
        return spec

    def parse_requirement_spec(self):
        optional = False
        if self.current().type == "OPTIONAL":
            self.eat("OPTIONAL")
            optional = True

        type_name = self.eat("ID").value
        spec = RequirementSpec(type_name, optional, [], [], [])

        if self.current().type == "LPAREN":
            self.eat("LPAREN")
            if self.current().type != "RPAREN":
                while True:
                    key_tok = self.current()
                    if key_tok.type not in ("SUBCOMPONENTS", "PARAMETERS", "FUNCTIONS"):
                        raise SyntaxError(f"Unexpected requirement key {key_tok.type} at {key_tok.position}")
                    self.eat(key_tok.type)
                    self.eat("ASSIGN")

                    if key_tok.type == "SUBCOMPONENTS":
                        spec.subcomponents.extend(self.parse_requirement_spec_list())
                    elif key_tok.type == "PARAMETERS":
                        spec.parameters.extend(self.parse_requirement_param_list())
                    elif key_tok.type == "FUNCTIONS":
                        spec.functions.extend(self.parse_requirement_func_list())

                    if self.current().type == "COMMA":
                        self.eat("COMMA")
                        continue
                    break
            self.eat("RPAREN")

        return spec

    def parse_requirement_spec_list(self):
        specs = []
        if self.current().type == "LBRACKET":
            self.eat("LBRACKET")
            while self.current().type != "RBRACKET":
                specs.append(self.parse_requirement_spec())
                if self.current().type == "COMMA":
                    self.eat("COMMA")
                    continue
                break
            self.eat("RBRACKET")
            return specs

        specs.append(self.parse_requirement_spec())
        return specs

    def parse_requirement_param_list(self):
        params = []
        if self.current().type == "LBRACKET":
            self.eat("LBRACKET")
            while self.current().type != "RBRACKET":
                params.append(self.parse_requirement_param())
                if self.current().type == "COMMA":
                    self.eat("COMMA")
                    continue
                break
            self.eat("RBRACKET")
            return params

        params.append(self.parse_requirement_param())
        return params

    def parse_requirement_param(self):
        optional = False
        if self.current().type == "OPTIONAL":
            self.eat("OPTIONAL")
            optional = True
        expr = self.parse_expression(stop_tokens={"COMMA", "RPAREN", "RBRACKET"})
        return RequirementParam(expr, optional)

    def parse_requirement_func_list(self):
        funcs = []
        if self.current().type == "LBRACKET":
            self.eat("LBRACKET")
            while self.current().type != "RBRACKET":
                funcs.append(self.parse_requirement_func())
                if self.current().type == "COMMA":
                    self.eat("COMMA")
                    continue
                break
            self.eat("RBRACKET")
            return funcs

        funcs.append(self.parse_requirement_func())
        return funcs

    def parse_requirement_func(self):
        optional = False
        if self.current().type == "OPTIONAL":
            self.eat("OPTIONAL")
            optional = True
        name = self.eat("ID").value
        self.eat("LPAREN")
        self.eat("RPAREN")
        return RequirementFunction(name, optional)
