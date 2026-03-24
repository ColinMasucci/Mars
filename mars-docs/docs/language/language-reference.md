# Language Reference

## Lexical Structure
- Identifiers match `[A-Za-z_][A-Za-z0-9_]*`.
- Line comments start with `#` and run to end of line.
- Block comments use `/* ... */`.
- Whitespace is ignored.
- Keywords: `int`, `float`, `bool`, `string`, `void`, `dict`, `class`, `const`, `component`, `extends`, `subcomponents`, `parameters`, `functions`, `requirements`, `optional`, `import`, `return`, `if`, `else`, `while`, `for`, `break`, `continue`, `true`, `false`.

## Types
- Primitives: `int`, `float`, `bool`, `string`, `void`.
- Arrays: `T[]` with any depth, for example `int[]`, `float[][]`.
- Dictionaries: `dict<K,V>`, for example `dict<int,string>`.
- Unit types: `float::unit`, for example `float::m`, `float::m/s^2`.
- Class types: class names are valid types.
- Component types: component names are valid types.

## Literals
- Integers: `123`
- Floats: `3.14`
- Strings: `"hello"`
- Booleans: `true`, `false`
- Arrays: `[1, 2, 3]`
- Dictionaries: `{1: "a", 2: "b"}`
- Unit tags on expressions: `10::cm`, `(a + b)::m/s`

## Expressions
- Member access: `obj.field`, `module.fn`, `component.sub.param`.
- Calls: `fn(a, b)`, `obj.method(a)`.
- Indexing: `arr[i]`, `dict[key]`.
- Unary operators: `-x`, `+x`, `!x`, `x++`, `x--` (postfix `++`/`--` require `int` variables).
- Binary operators: `+`, `-`, `*`, `/`, `^`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `||`.

Operator precedence (highest to lowest):
| Precedence | Operators | Notes |
| --- | --- | --- |
| 7 | `x++`, `x--` | postfix |
| 6 | `-x`, `+x`, `!x`, `^` | `^` is right-associative |
| 5 | `*`, `/` | |
| 4 | `+`, `-` | |
| 3 | `<`, `<=`, `>`, `>=` | |
| 2 | `==`, `!=` | |
| 1 | `&&` | |
| 0 | `||` | |

## Statements
- Variable declaration: `int x = 3;` or `float y;`
- Constants: `const int k = 5;`
- Assignment: `x = 1;`, `x += 2;`, `x -= 2;`, `x *= 2;`, `x /= 2;`
- Block: `{ ... }`
- If/else: `if (cond) { ... } else { ... }`
- While: `while (cond) { ... }`
- For: `for (init; cond; increment) { ... }`
- Break/continue: `break;`, `continue;` (loops only)
- Return: `return expr;` or `return;` in `void` functions
- Import: `import math;`

## Functions
- Definition: `int add(int a, int b) { return a + b; }`
- Prototypes are allowed: `void foo();`
- Parameters must have types and cannot be `void`.
- `void` functions may use `return;` but may not return a value.

## Classes
- Definition:
```mars
class Point {
    float x;
    float y;
    Point(float x, float y) { this.x = x; this.y = y; }
    float len() { return x*x + y*y; }
}
```
- Fields may be `const`.
- Methods use explicit return types.
- Constructors use the class name.
- `this` refers to the current instance.
- Requirements are documented separately in `docs/requirements.md`.

## Grammar Notes
- Declarations require explicit types; there is no type inference for variables.
- Unit types are only allowed on `float`, and unit tags apply only to numeric expressions.
- Array indices must be `int`; dictionary keys must match the declared key type.
