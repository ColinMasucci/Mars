---
id: parser
title: Parser
sidebar_label: Parser
sidebar_position: 2
---

The parser transforms a sequence of tokens into an **Abstract Syntax Tree (AST)**, representing the structure of the program.

---

## Overview

The Mars parser is a **hybrid parser** combining:

- **Recursive descent parsing** for statements and program structure
- **Shunting Yard algorithm** for expressions with operator precedence

This approach provides both:
- readability for high-level constructs
- correctness for complex expressions

---

## Entry Point

The parser produces a top-level AST node:

```python
Program(statements, components, classes)
```

The source file is divided into three categories:

- Statements → general executable code
- Components → configuration-style structures
- Classes → object-oriented constructs
Parsing Strategy

The parser processes tokens sequentially using a cursor:
```python
self.pos
self.current()
```

Tokens are consumed using:
```python
self.eat(type)
```

If the expected token does not match, a syntax error is raised.

---

## Statement Parsing

Statements are parsed using a dispatch-style approach:

- Import statements
- Variable declarations
- Function declarations
- Control flow (`if`, `while`, `for`)
- Blocks (`{ ... }`)
- Assignments and expressions

---

## Ambiguity Handling (Backtracking)

Some constructs are ambiguous at the start.

Example:
```python
x = 5;
x + 5;
```
As `x` appears, it is unknown whether it will be used as a declaration or assignment.

To resolve this, the parser:

1. Attempts one interpretation (e.g. declaration or assignment)
2. If it fails, rewinds (self.pos)
3. Parses using an alternative rule

This avoids needing complex grammar lookahead.

---

## Blocks and Scope

Blocks are parsed as:

```python
{
    statement*
}
```

They produce:

Block([...])

Blocks are used in:

- functions
- conditionals
- loops

---

## Expression Parsing (Shunting Yard)

Expressions are parsed using the Shunting Yard algorithm, ensuring correct precedence and associativity.

### Operator Table

Each operator is defined with:

- precedence
- associativity (left/right)
- arity (unary/binary)

Example:
```python
"PLUS": (4, "left", 2, ROLE_BINARY)
```

---

## Expression Features
### Binary operators
- Arithmetic: `+`, `-`, `*`, `/`, `^`
- Comparison: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Logical: `&&`, `||`
### Unary operators
- Prefix: `-`, `!`
- Postfix: `++`, `--`
### Complex expressions
- Function calls: `foo(x)`
- Member access: `obj.field`
- Array indexing: `arr[i]`
- Nested expressions: `(a + b) * c`

---

## Primary Expressions

Supported primary expressions include:

- Literals:
  - `numbers`
  - `strings`
  - `booleans`
- Arrays:
  - `[1, 2, 3]`
- Dictionaries:
  - `{ key: value }`
- Variables and function calls

---

## Type Parsing

Types are parsed separately from expressions.

### Supported types

Primitive types:

`int`, `float`, `bool`, `string`

Dictionary types:

`dict<string, int>`


Array types:

`int[][]`

---

## Unit Tagging

The language supports unit-aware expressions:

distance :: m
velocity :: m/s^2

These are parsed into:

UnitTag(expression, unit)

Unit expressions support:

multiplication (*)
division (/)
exponentiation (^)

---

## Components

Components are structured configuration blocks:

```python
component Engine {
    parameters { ... }
    subcomponents { ... }
    functions { ... }
}
```

They are parsed into:

ComponentDef(...)

---

## Classes

Classes support:

- Fields
- Methods
- Constructors
- Requirements

### Example:
```python
class MyClass {
    int x;
    void foo() { ... }
}
```

---

## Requirements System

The parser includes a custom requirements DSL.

Supported features:

Logical operators: AND, OR, NOT
Optional modifiers
Nested expressions

Example:

optional Sensor AND (Motor OR Camera)
Error Handling

Errors are:

context-aware (via _context_stack)
position-aware (via token position)

Example:

Expected ')', got ';'

This produces precise diagnostics.

---

## Design Notes
- The parser is single-pass with controlled backtracking
- It builds a fully structured AST
- Only syntax is validated here (no semantic checks)

---

## Future Improvements
- Better error recovery (continue after failure)
- Improved diagnostics for deeply nested expressions
- Performance optimizations for large files