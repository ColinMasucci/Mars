#This was used for the original interpreter approach before moving to bytecode and a VM.

from ast_nodes import NumberLiteral, StringLiteral, BinaryOp

def evaluate(node):
    if isinstance(node, NumberLiteral):
        return node.value
    if isinstance(node, StringLiteral):
        return node.value
    if isinstance(node, BinaryOp):
        left = evaluate(node.left)
        right = evaluate(node.right)
        if node.op == "PLUS":
            # string concatenation if either is string
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        elif node.op == "MINUS":
            if isinstance(left, str) or isinstance(right, str):
                raise TypeError("Cannot subtract with a string")
            return left - right
    raise TypeError(f"Unknown node type {type(node)}")
