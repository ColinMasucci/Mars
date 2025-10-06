from lexer import tokenize
from parser import Parser
from interpreter import evaluate

code = '42 + 3.5 + "hello"'
tokens = tokenize(code)
parser = Parser(tokens)
ast = parser.parse()
result = evaluate(ast)

print("Tokens: ", tokens)
print("AST: ", ast)
print("Result: ", result)
