import os
import importlib.util

def create_library_from_file(lib_name, file_path):
    """
    Generates a library file in 'builtins/' by scanning functions defined in another Python file.
    
    Example usage:
        create_library_from_file("math_lib", "src/math_funcs.py")
    """
    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(lib_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Collect all callable functions defined in the module
    funcs = {name: f"{lib_name}.{name}" for name, obj in module.__dict__.items() if callable(obj)}
    
    # Write the builtins library file
    filepath = f"{lib_name}.py"
    
    with open(filepath, "w") as f:
        f.write(f"import {lib_name}\n\n")
        f.write(f"{lib_name.upper()}_FUNCS = {{\n")
        for name, ref in funcs.items():
            f.write(f"    '{name}': {ref},\n")
        f.write("}\n")
    
    print(f"Library {lib_name}.py created with {len(funcs)} functions.")

# Example run
if __name__ == "__main__":
    create_library_from_file("math", "math_lib.py")
