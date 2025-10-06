from lexer import tokenize
from parser import Parser
from interpreter import evaluate
from ast_visualizer import visualize

import os
import platform
import subprocess


code = '42 + 3.5 + "hello"'
tokens = tokenize(code)
parser = Parser(tokens)
ast = parser.parse()
result = evaluate(ast)

print("Tokens: ", tokens)
print("AST: ", ast)
print("Result: ", result)


### Visualize AST
dot = visualize(ast)
dot.render("ast_output", cleanup=True)
output_path = dot.render("ast_output", cleanup=True)
print(f"AST visualization saved as {output_path}")

# Open image upon creation  
def open_image(path):
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", path])
        else:  # Linux and others
            subprocess.run(["xdg-open", path])
    except Exception as e:
        print(f"Could not open image automatically: {e}")

open_image(output_path)