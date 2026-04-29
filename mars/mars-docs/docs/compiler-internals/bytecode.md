---
id: bytecode
title: Bytecode Compiler
sidebar_label: Bytecode
sidebar_position: 3
---

The bytecode compiler transforms the **Abstract Syntax Tree (AST)** into a sequence of low-level **instructions** executed by the stack-based virtual machine.

---

## Overview

The compiler performs a **single-pass traversal** of the AST and emits bytecode instructions.

Each instruction is represented as:

```python
Instr = Tuple[str, ...]
```

Examples:
```python
("PUSH_INT", 42)
("ADD",)
("CALL", "foo", 2)
```

The resulting instruction list is executed directly by the VM.

---

## Entry Point

Compilation begins with:
```python
compile_program(program: ast.Program) -> List[Instr]
```
This function:

1. Initializes global compiler state
2. Emits function and class bytecode
3. Compiles top-level statements
4. Produces a complete instruction sequence ending in:
```python
("HALT",)
```

---

## Program Layout

The compiler organizes bytecode into two sections:

1. ### Function Definitions

All functions (including class and component functions) are compiled first.

A jump is inserted at the beginning:
```python
("JUMP", main_start)
```

This ensures function bodies are skipped during initial execution.

2. ### Main Program

After function compilation:
- Component imports are emitted
- Global/component parameters are declared
- Remaining statements are executed sequentially

---

## Compilation Strategy

Compilation is handled by two core functions:

`compile_node(node, code)`
- Emits bytecode for any AST node

`compile_statement(node, code)`
- Wraps `compile_node`
- Discards expression results using:
```python
("POP",)
```

---

## Stack-Based Execution Model

The compiler targets a stack machine:

- Values are pushed onto the stack
- Operations consume operands from the stack
- Results are pushed back onto the stack

Example:
```python
a + b
```

Compiles to:
```python
LOAD a
LOAD b
ADD
```

## Literals and Data Structures
### Literals
```python
("PUSH_INT", value)
("PUSH_FLOAT", value)
("PUSH_STR", value)
("PUSH_BOOL", value)
("PUSH_NONE",)
```
### Arrays
Elements compiled first
```python
("BUILD_ARRAY", N)
```

### Dictionaries
key, value pairs compiled in order
```python
("BUILD_DICT", N)
```

## Variables
### Declaration
```python
("DECLARE", name, type, readonly)
```

If no initializer is provided, default values are emitted:

- int, float → 0
- bool → False
- string → ""
- arrays → empty array
- dicts → empty dict
- others → None

### Access
```python
("LOAD", name)
```

### Assignment
```python
("STORE", name)
```
### Member Assignment
```python
("SET_FIELD", field)
("GET_FIELD", field)
```

### Indexed Assignment
```python
("INDEX_SET",)
("INDEX_GET",)
```
---

## Expressions
### Binary Operations

Operators are compiled as:

`ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `POW`
`AND`, `OR`
`LT`, `GT`, `LEQ`, `GEQ`, `EQ`, `NEQ`

### Unary Operations
`NEGATE`
`NOT`
`INC name`
`DEC name`

---

## Control Flow
### If Statements
```python
JUMP_IF_FALSE <else>
...
JUMP <end>
```
Jump targets are patched after compilation.

### While Loops
```python
loop_start:
  condition
  JUMP_IF_FALSE end
  body
  JUMP loop_start
end:
```

### For Loops

Compiled into:

- initialization
- condition check
- body
- increment
- loop back

### Step Loops

A specialized loop that injects:
```python
("UPDATE",)
```
at the start of each iteration.

### Break / Continue

Handled using a loop context stack:

`break` → patched to loop end
`continue` → patched to loop start or increment

---

## Functions
### Definition
```python
("FUNC_BEGIN", name, param_count)
...
("FUNC_END", name)
```

Parameters are declared as local variables.

### Return
```python
("RETURN",)
```

If no return is provided:
```python
PUSH_NONE
RETURN
```

---

## Function Calls
### Regular Calls
```python
("CALL", name, arg_count)
```
### Method Calls
```python
("CALL_METHOD", method, arg_count)
```
### Constructors
```python
("NEW_CALL", arg_count)
```
### Built-in Functions

Special instructions:

- print(...) → PRINT
- publish(...) → PUBLISH
- wait(...) → WAIT
- update() → UPDATE

## Components and Classes

The compiler tracks:
- Component base names
- Instance paths
- Class names

This enables:
- Namespaced function calls
- Component method dispatch
- Constructor handling

## Imports
```python
("IMPORT", module_name)
```

Modules are validated at compile time and loaded dynamically.

## Type Handling

The compiler performs minimal type coercion:
```python
CAST_INT
CAST_FLOAT
```
Unit annotations are stripped during compilation and do not affect runtime execution.

## Scope Management

Blocks generate scope instructions:
```python
("ENTER_SCOPE",)
...
("EXIT_SCOPE",)
```

---

## Future Improvements
Improved debug
Register-based VM backend (alternative execution model for better performance)