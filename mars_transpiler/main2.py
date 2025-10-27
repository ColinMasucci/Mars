import ast_nodes as ast #our layed out AST nodes
from lexer import tokenize #tokenizer from lexer.py
from parser import Parser #parser from parser.py
from bytecodegen import compile_program #bytecode generator from bytecodegen.py
from vm import VM #the stack-based virtual machine from vm.py

from ast_visualizer import visualize #for visualizing the AST



#FULL PROGRAM EXECUTION FLOW
print("===EXAMPLE 001=================================================================================================================")

# Access and read the test file
with open("test_file.mars", "r", encoding="utf-8") as f:
    code = f.read()

#tokenize the input code
tokens = tokenize(code, True)
#Create Parser instance with tokens
parser = Parser(tokens)
#Parse the tokens into an AST
parsed_ast = parser.parse(True)

#Visualize AST
dot = visualize(parsed_ast)
output_path = dot.render("ast_output", cleanup=True)
print(f"AST visualization saved as {output_path} \n")

#prog1 = ast.Program(statements=[parsed_ast])  #wrap parsed AST in a Program node
bytecode1 = compile_program(parsed_ast, True) #compile the AST into bytecode (True for printing bytecode)
vm1 = VM(bytecode1) #create VM instance with the bytecode
vm1.run() #run the bytecode on the VM




# print("===EXAMPLE 002=================================================================================================================")
# # Example 1: print(1 + 2 * 3)
# prog = ast.Program(statements=[
#     ast.Print(expr=ast.BinaryOp("PLUS",
#         left=ast.NumberLiteral(1),
#         right=ast.BinaryOp("MUL", ast.NumberLiteral(2), ast.NumberLiteral(3))
#     ))
# ])

# #True is used for printing the bytecode (Can leave blank for default False)
# bytecode = compile_program(prog, True)
# vm = VM(bytecode)
# vm.run()  # should print 7


# print("===EXAMPLE 003=================================================================================================================")
# # Example 2: x = 10; print(x + 5)
# prog2 = ast.Program(statements=[
#     ast.Assign(name="x", value=ast.NumberLiteral(10)),
#     ast.Print(expr=ast.BinaryOp("PLUS", ast.Var("x"), ast.NumberLiteral(5)))
# ])

# bytecode2 = compile_program(prog2, True)
# vm2 = VM(bytecode2)
# vm2.run()  # should print 15
