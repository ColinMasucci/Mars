import re
from dataclasses import dataclass

from source_errors import format_source_error

@dataclass
class Token:
    type: str
    value: str
    position: int
    #lineNumber

TOKEN_SPEC = [
    # --- Comments ---
    ("COMMENT", r"#.*"),               # skip everything after #
    ("BLOCK_COMMENT", r"/\*[\s\S]*?\*/"), # skip everything between /* and */

    # --- Type Keywords ---
    ("INT_KW", r"\bint\b"),           # integer type keyword
    ("FLOAT_KW", r"\bfloat\b"),       # float type keyword
    ("BOOL_KW", r"\bbool\b"),         # boolean type keyword
    ("STRING_KW", r"\bstring\b"),     # string type keyword
    ("VOID_KW", r"\bvoid\b"),         # void type keyword
    ("DICT_KW", r"\bdict\b"),       # dict type keyword

    # --- Class/Const Keywords ---
    ("CLASS", r"\bclass\b"),
    ("CONST_KW", r"\bconst\b"),
    ("REQUIREMENTS", r"\brequirements\b"),
    ("OPTIONAL", r"\boptional\b"),

    #--- Config Keywords ---
    ("COMPONENT", r"\bcomponent\b"),
    ("EXTENDS", r"\bextends\b"),
    ("SUBCOMPONENTS", r"\bsubcomponents\b"),
    ("PARAMETERS", r"\bparameters\b"),
    ("FUNCTIONS", r"\bfunctions\b"),


    # --- Other Keywords ---
    ("IMPORT", r"\bimport\b"),  # import keyword
    ("RETURN", r"\breturn\b"),  # return keyword


    # --- Literals ---
    ("FLOAT",   r"\d+\.\d+"),          # check for float first (so 3.14 is not parsed as int + .14)
    ("INT",     r"\d+"),               # next we can check for ints
    ("STRING",  r'"[^"]*"'),           # string should be in double quotes
    ("TRUE",  r"\btrue\b"),            # boolean true literal
    ("FALSE", r"\bfalse\b"),           # boolean false literal

    # --- Boolean Operators ---
    ("AND", r"&&"),                    # logical AND
    ("OR", r"\|\|"),                    # logical OR
    ("EQ", r"=="),                     # equality operator
    ("NEQ", r"!="),                    # not equal operator
    ("LEQ", r"<="),                    # less than or equal to
    ("GEQ", r">="),                    # greater than or equal to
    ("LT", r"<"),                      # less than operator (also for dict<K,V>)
    ("GT", r">"),                      # greater than operator (also for dict<K,V>)

    # --- Operators ---
    ("PLUS_ASSIGN", r"\+="),
    ("MINUS_ASSIGN", r"-="),
    ("MUL_ASSIGN", r"\*="),
    ("DIV_ASSIGN", r"/="),
    ("INC",     r"\+\+"),              # check for increment operator
    ("DEC",     r"--"),                # check for decrement operator
    ("ASSIGN",  r"="),                 # check for operator
    ("BANG",    r"!"),                 # logical NOT
    ("PLUS",    r"\+"),                # check for plus signs
    ("POW", r"\^"),                    # check for exponent
    ("MINUS",   r"-"),                 # check for minus signs
    ("MUL",    r"\*"),                 # check for muliplication signs
    ("DIV",   r"/"),                   # check for division signs

    # --- Parentheses & punctuation ---
    ("LBRACE", r"\{"),                 # identifying braces for blocks and also for dictionaries.
    ("RBRACE", r"\}"),
    ("LPAREN",  r"\("),                # identifying parentheses for priority later on.
    ("RPAREN",  r"\)"),
    ("SEMI", r";"),                    # semicolon as statement separator
    ("DBLCOLON", r"::"),               # double colon for unit tags
    ("COLON", r":"),                  # colon for dict key-value pairs
    ("COMMA", r","),                   # comma as parameter separator
    ("DOT", r"\."),                    # for module.function syntax
    ("LBRACKET", r"\["),               # for arrays
    ("RBRACKET", r"\]"),

    # --- conditionals ---
    ("IF", r"\bif\b"),                 # check for if statements
    ("ELSE", r"\belse\b"),             # check for else statements
    ("WHILE", r"\bwhile\b"),           # check for while loops
    ("STEP", r"\bstep\b"),             # check for step loops
    ("FOR", r"\bfor\b"),               # check for for loops
    ("BREAK", r"\bbreak\b"),           # break out of loops
    ("CONTINUE", r"\bcontinue\b"),     # continue loops

    # --- Identifiers & Keywords ---
    ("ID",      r"[A-Za-z_][A-Za-z0-9_]*"), # identifiers (including 'print')

    # --- Blanks and Newlines ---
    ("SKIP",    r"[ \t\n]+"),          # whitespaces should be skipped

] 

#combines all of the regexs into one big regular expression seperated by (|) "or"
MASTER_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

def tokenize(text, printTokens=False, source_path=None) -> list[Token]:
    tokens = []
    pos = 0
    while pos < len(text):
        m = MASTER_REGEX.match(text, pos) #trys to match the text to one of our reg exs starting at "pos"
        if not m: #if none found then print debug displaying where we couldnt find one.
            msg = f"Unexpected character {text[pos]!r}."
            raise SyntaxError(format_source_error(msg, text, pos, source_path, "tokenize"))
        kind = m.lastgroup #.lastgroup: Returns the name of the last matched capturing group, or None if the group had no name or if no group was matched at all.
        val = m.group(kind)#.group(): Returns the string matched by the specified group.
        if kind not in ("SKIP", "COMMENT", "BLOCK_COMMENT"): #Dont tokenize blank spaces or comments
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
