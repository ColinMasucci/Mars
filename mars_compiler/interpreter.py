from lexer import tokenize #tokenizer from lexer.py
from parser import Parser #parser from parser.py
from type_checker import TypeChecker #type checker from type_checker.py
from bytecodegen import compile_program #bytecode generator from bytecodegen.py
from vm import VM #the stack-based virtual machine from vm.py

from ast_visualizer import visualize #for visualizing the AST


def interpret_code_from_file(file_path: str, print_debug: bool = False):
    
    # Access and read the test file
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    #1. tokenize the input code
    tokens = tokenize(code, print_debug)

    #2. Parse the tokens into an AST
    parser = Parser(tokens)
    parsed_ast = parser.parse(print_debug)

    #3. Type check the AST
    type_checker = TypeChecker()
    try:
        type_checker.check(parsed_ast)
        print("Static type checking passed\n")
    except TypeError as e:
        print(f"Type Error: {e}")
        exit(1)  # stop execution before codegen if types are invalid

    #(Optional) Visualize AST
    dot = visualize(parsed_ast)
    output_path = dot.render("ast_output", cleanup=True)
    print(f"AST visualization saved as {output_path} \n")

    #4. Compile the AST into bytecode
    bytecode1 = compile_program(parsed_ast, print_debug)

    #5. Run the bytecode on the VM
    vm1 = VM(bytecode1) #create VM instance with the bytecode
    vm1.run() #run the bytecode on the VM
