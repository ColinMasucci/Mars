from lexer import tokenize
from parser import Parser
from interpreter import evaluate #This backend is great for testeing our AST to make sure that it is working asintended before attempting to convert into a C++ file.
from ast_visualizer import visualize
from codegen import emit_cpp #This backend is what we use for our actual final implementation, converting our.mars file into a C++ file.

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


## Visualize AST
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



#Run full pipeline from .mars like lines into c++
def transpile_text_to_cpp(source_text: str, out_cpp_path: str = "out.cpp"):
    tokens = tokenize(source_text)
    parser = Parser(tokens)
    ast = parser.parse()           # this is your AST root
    cpp_source = emit_cpp(ast, out_path=out_cpp_path)
    print(f"Wrote C++ to {out_cpp_path}")
    return cpp_source

if __name__ == "__main__":
    examples = [
        '42 + 5',                 # int + int
        '3.5 + 2',                # float + int -> double
        '"hi" + " there"',        # string + string
        '1 + " apples"',          # number + string -> concatenation
        '"x: " + 3.14',           # string + number -> concatenation
        '10 - 2'                  # subtraction
    ]
    for i, ex in enumerate(examples, start=1):
        path = f"out_example_{i}.cpp"
        print("Source:", ex)
        cpp = transpile_text_to_cpp(ex, out_cpp_path=path)
        print("C++ snippet:\n", cpp)
        print("-" * 40)