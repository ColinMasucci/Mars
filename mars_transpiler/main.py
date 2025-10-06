from lexer import tokenize
from parser import Parser
from interpreter import evaluate
from ast_visualizer import visualize

import os
import platform
import subprocess



# Access and read the test file
with open("test_file.mars", "r", encoding="utf-8") as f:
    code = f.read()

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