from dataclasses import dataclass
from typing import List, Any #Signals to type checker that it can be any value.

@dataclass #For simple testing floats and ints were both Number literals
class NumberLiteral:
    value: float

@dataclass
class StringLiteral:
    value: str

@dataclass
class BooleanLiteral:
    value: bool

@dataclass
class DictLiteral:
    pairs: List[tuple[Any, Any]]
    
@dataclass
class ArrayLiteral:
    elements: List[Any]

@dataclass
class ArrayAccess:
    array: Any
    index: Any

@dataclass
class BinaryOp: # (Ex. PLUS, MUL, DIV, MINUS)
    op: str
    left: Any
    right: Any

@dataclass
class UnaryOp:  # (Ex. NEGATE, INC, DEC, BANG)
    op: str
    operand: Any

#used for referencing variables (grabbing their value)
@dataclass
class Var:
    name: str

@dataclass
class VarDecl:
    vartype: str
    name: str
    value: Any
    readonly: bool = False

@dataclass
class MemberAccess:
    obj: Any
    attr: str

@dataclass
class FieldDecl:
    vartype: str
    name: str
    value: Any
    readonly: bool = False

@dataclass
class MethodDecl:
    return_type: Any
    name: str
    params: List[Any]
    body: Any
    is_constructor: bool = False

# used for assigning variables
@dataclass
class Assign:
    name: Any
    value: Any

@dataclass
class AugAssign:
    name: Any
    op: str
    value: Any

@dataclass
class If:
    condition: Any
    then_branch: Any
    else_branch: Any = None

@dataclass
class While:
    condition: Any
    body: Any

@dataclass
class Call:
    func: Any      
    args: List[Any] 

@dataclass
class Import:
    module: str

@dataclass
class SubcomponentDecl:
    type_name: str
    name: str
    bindings: list[tuple[str, Any]] = None

@dataclass
class FuncDecl:
    return_type: Any
    name: str
    params: List[Any]
    body: Any     

@dataclass
class Return:
    value: Any



#A block of statements (used for bodies of if/while)
@dataclass
class Block:
    statements: List[Any]

#The root node of a program, containing a list of statements. 
# (We havent added in all of our AST stuff yet however I think this is the "expression" part the we previously defined????)
@dataclass
class Program:
    statements: List[Any]
    components: List[Any]
    classes: List[Any] = None

@dataclass
class ComponentDef:
    def __init__(self, name, parent, subcomponents, parameters, functions):
        self.name = name
        self.parent = parent  # None or string
        self.subcomponents = subcomponents
        self.parameters = parameters
        self.functions = functions

@dataclass
class ClassDecl:
    name: str
    fields: List[FieldDecl]
    methods: List[MethodDecl]
    constructor: Any  # MethodDecl or None
    requirements: List[Any] = None


@dataclass
class RequirementParam:
    expr: Any
    optional: bool = False


@dataclass
class RequirementFunction:
    name: str
    optional: bool = False


@dataclass
class RequirementSpec:
    type_name: str
    optional: bool = False
    parameters: List[RequirementParam] = None
    functions: List[RequirementFunction] = None
    subcomponents: List[Any] = None


@dataclass
class RequirementExpr:
    op: str
    left: Any
    right: Any = None
