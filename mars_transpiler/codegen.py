#This was used to generate C++ code from expressions for our previous transpiler before we switched to a VM model.

from typing import Tuple
import ast_nodes as ast #import in our literals

def _escape_cpp_string(s: str) -> str:
    """if the string contains " or \ or newline we must escape them so the generated "<text>" is valid C++."""
    # minimal escaping: backslash and double-quote, and keep newlines
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def gen_literal(node) -> Tuple[str, str]:
    """
    Return (cpp_expr, cpp_type) for literal nodes.
    cpp_type is one of: 'int', 'double', 'std::string'

    Convert a literal AST node (a number or a string) into:
        a C++ expression (text), and
        the C++ type label ("int", "double", or "std::string").
    """
    if isinstance(node, ast.NumberLiteral):
        if isinstance(node.value, int):
            return (str(node.value), "int")
        else:  # float
            # ensure decimal point present for C++ literal
            v = node.value
            text = repr(float(v))
            if "." not in text and "e" not in text:
                text = text + ".0"
            return (text, "double")
    if isinstance(node, ast.StringLiteral):
        lit = _escape_cpp_string(node.value)
        return (f'"{lit}"', "std::string")
    raise TypeError(f"Unknown literal node: {type(node)}")

def gen_expr(node) -> Tuple[str, str]:
    """
    Generate a C++ expression and its type.
    Returns (expr_text, cpp_type) where cpp_type in {'int','double','std::string'}.

    Same thing as the above gen_literal however it now does this for expressions like the binop.
    """
    # Literals
    #If node is a literal, just reuse gen_literal.
    if isinstance(node, ast.NumberLiteral) or isinstance(node, ast.StringLiteral):
        return gen_literal(node)

    # Binary operations
    #For a binary op, recursively generate code+type for left and right. This is where the function becomes recursive: it keeps descending until it hits literals.
    if isinstance(node, ast.BinaryOp):
        left_expr, left_type = gen_expr(node.left)
        right_expr, right_type = gen_expr(node.right)

        # Helper for converting a numeric expression to a string expression:
        def num_to_string(expr_text, expr_type):
            # wrap numeric into std::to_string(...) which returns std::string
            if expr_type == "int":
                return (f"std::to_string({expr_text})", "std::string")
            if expr_type == "double":
                # to get shorter precision in output you could use ostringstream; for now std::to_string
                return (f"std::to_string({expr_text})", "std::string")
            raise TypeError("num_to_string called on non-numeric type")

        # PLUS
        if node.op == "PLUS":
            # If either side is a string, produce std::string concatenation
            if left_type == "std::string" or right_type == "std::string":
                # ensure both sides are std::string expressions
                if left_type != "std::string":
                    left_expr, _ = num_to_string(left_expr, left_type)
                if right_type != "std::string":
                    right_expr, _ = num_to_string(right_expr, right_type)
                # use operator+ for std::string concatenation
                return (f"({left_expr} + {right_expr})", "std::string")

            # otherwise both numeric: if any double -> double arithmetic
            if left_type == "double" or right_type == "double":
                # promote ints to double explicitly
                if left_type == "int":
                    left_expr = f"((double){left_expr})"
                if right_type == "int":
                    right_expr = f"((double){right_expr})"
                return (f"({left_expr} + {right_expr})", "double")

            # both int
            return (f"({left_expr} + {right_expr})", "int")

        # MINUS
        if node.op == "MINUS":
            # minus not allowed with strings
            if left_type == "std::string" or right_type == "std::string":
                raise TypeError("Cannot apply '-' to strings")
            # numeric: promote to double if needed
            if left_type == "double" or right_type == "double":
                if left_type == "int":
                    left_expr = f"((double){left_expr})"
                if right_type == "int":
                    right_expr = f"((double){right_expr})"
                return (f"({left_expr} - {right_expr})", "double")
            return (f"({left_expr} - {right_expr})", "int")

        raise NotImplementedError(f"Operator not supported: {node.op}")

    raise TypeError(f"Unknown AST node type: {type(node)}")

def emit_cpp(ast_root, program_name="mars_expr", out_path=None) -> str:
    """
    Generate a complete C++ source as string for the AST `ast_root`.
    If out_path is provided, write the file there.
    Returns the generated C++ source text.
    """
    expr_text, expr_type = gen_expr(ast_root)

    # choose a variable type
    if expr_type == "std::string":
        decl = f"std::string result = {expr_text};"
    elif expr_type == "double":
        decl = f"double result = {expr_text};"
    elif expr_type == "int":
        decl = f"long long result = {expr_text};"
    else:
        raise TypeError(f"Unsupported top-level type: {expr_type}")

    includes = [
        "#include <iostream>",
        "#include <string>",
        "#include <sstream>",  # in case user extends code for formatting
    ]
    header = "\n".join(includes) + "\n\nusing namespace std;\n\n"

    main_body = f"""int main() {{
    {decl}
    // print result
    {"cout << result << std::endl;" if expr_type != "std::string" else "cout << result << std::endl;"}
    return 0;
}}
"""
    full = header + main_body

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full)

    return full
