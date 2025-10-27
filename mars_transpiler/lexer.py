import re
from dataclasses import dataclass

@dataclass
class Token:
    type: str
    value: str
    position: int
    #lineNumber

TOKEN_SPEC = [
    ("FLOAT",   r"\d+\.\d+"),          # check for float first (so 3.14 is not parsed as int + .14)
    ("INT",     r"\d+"),               # next we can check for ints
    ("STRING",  r'"[^"]*"'),           # string should be in double quotes
    ("ID",      r"[A-Za-z_][A-Za-z0-9_]*"), # identifiers (including 'print')
    ("INC",     r"\+\+"),              # check for increment operator
    ("DEC",     r"--"),                # check for decrement operator
    ("PLUS",    r"\+"),                # check for plus signs
    ("MINUS",   r"-"),                 # check for minus signs
    ("MUL",    r"\*"),                 # check for muliplication signs
    ("DIV",   r"/"),                   # check for division signs
    ("LPAREN",  r"\("),                # identifying parentheses for priority later on.
    ("RPAREN",  r"\)"),
    ("SEMI", r";"),                    # semicolon as statement separator
    ("SKIP",    r"[ \t\n]+"),          # whitespaces should be skipped
]

#combines all of the regexs into one big regular expression seperated by (|) "or"
MASTER_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

def tokenize(text, printTokens=False) -> list[Token]:
    tokens = []
    pos = 0
    while pos < len(text):
        m = MASTER_REGEX.match(text, pos) #trys to match the text to one of our reg exs starting at "pos"
        if not m: #if none found then print debug displaying where we couldnt find one.
            raise SyntaxError(f"Unexpected character {text[pos]!r} at {pos}")
        kind = m.lastgroup #.lastgroup: Returns the name of the last matched capturing group, or None if the group had no name or if no group was matched at all.
        val = m.group(kind)#.group(): Returns the string matched by the specified group.
        if kind != "SKIP": #Dont tokenize blank spaces
            tokens.append(Token(kind, val, pos)) #add the newly identified token to our token list
        pos = m.end() #(update pos) .end(): method returns the ending index (exclusive) of the substring matched by the regular expression.
    tokens.append(Token("EOF", "", pos)) #To mark end of our script we are tokenizing
    if printTokens:
        print_tokens(tokens)
    return tokens

def print_tokens(tokens: list[Token]):
    print("Generated Tokens:")
    for token in tokens:
        print(f"{token.position:04}: {token.type}({token.value})")
    print("\n")