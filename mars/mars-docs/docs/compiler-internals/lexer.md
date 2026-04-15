---
id: lexer
title: Lexer
sidebar_label: Lexer
sidebar_position: 1
---


The lexer (tokenizer) is responsible for converting raw source code into a sequence of tokens. These tokens form the input to the parser.

---

### Overview

The Mars lexer is implemented as a **single-pass, regex-based tokenizer**. It scans the source code from left to right and matches patterns using a compiled master regular expression.

Each match produces a `Token` object:


```python
@dataclass
class Token:
    type: str
    value: str
    position: int
```

---

### Tokenization Strategy

All token patterns are defined in `TOKEN_SPEC` and combined into a single regular expression:


```python
MASTER_REGEX = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
)
```

The lexer repeatedly:
1. Matches the next token at the current position
2. Identifies the token type via named groups
3. Advances the cursor
4. Appends the token to the output list

---

### Token Categories

The lexer recognizes several categories of tokens:

#### Keywords
- Types: `int`, `float`, `bool`, `string`, `void`, `dict`
- Control flow: `if`, `else`, `while`, `for`, `break`, `continue`
- Structural: `class`, `component`, `extends`

#### Literals
- Integers: `123`
- Floats: `3.14`
- Strings: `"hello"`
- Booleans: `true`, `false`

#### Operators
- Arithmetic: `+`, `-`, `*`, `/`, `^`
- Assignment: `=`, `+=`, `-=`, `*=`, `/=`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `&&`, `||`, `!`

#### Punctuation
- Braces: `{ }`
- Parentheses: `( )`
- Separators: `;`, `,`, `:`
- Access: `.`

#### Identifiers
- Pattern: `[A-Za-z_][A-Za-z0-9_]*`
- Used for variable names, function names, etc.

---

### Order Matters

Token patterns are matched **in order**, which is critical for correctness.

Examples:
- `FLOAT` must appear before `INT`  
  → ensures `3.14` is not parsed as `3` and `.14`
- `==` must appear before `=`  
  → ensures equality is not split into two tokens
- Keywords must appear before `ID`  
  → ensures `if` is not treated as an identifier

---

### Skipped Tokens

The lexer ignores:
- Whitespace (`SKIP`)
- Line comments (`# comment`)
- Block comments (`/* comment */`)

These tokens are matched but not emitted.

---

### Error Handling

If no token matches the current input:

```python
if not m:
    raise SyntaxError(...)
```

The lexer:
- Stops immediately
- Reports the exact position
- Uses `format_source_error` for detailed diagnostics

---

### End of File

After processing all input, the lexer appends:

```python
Token("EOF", "", pos)
```

This marks the end of the token stream for the parser.

---

### Example

Input:
```python
int x = 5;
```

Output:
```python
INT_KW(int)
ID(x)
ASSIGN(=)
INT(5)
SEMI(;)
EOF
```

---

### Design Notes

- The lexer is **deterministic and single-pass**
- It does not perform semantic validation
- All structure is deferred to the parser and later stages

---

### Future Improvements

- Track line/column numbers (currently only `position`)
- Support escape sequences in strings
- Improve error recovery (continue after failure)