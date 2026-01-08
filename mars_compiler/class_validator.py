from ast_nodes import ClassDecl, FieldDecl, MethodDecl


class ClassValidationError(Exception):
    pass


class ClassValidator:
    """
    Validates classes and produces class interfaces:
    name -> {fields: {name: type, readonly: bool}, methods: {name: {return, params}}, ctor: {params}}
    """
    def __init__(self, classes):
        self.classes = {c.name: c for c in classes}
        if len(self.classes) != len(classes):
            raise ClassValidationError("Duplicate class names found")
        self.interfaces = {}

    def validate(self):
        for name, c in self.classes.items():
            self.interfaces[name] = self._build_interface(c)
        return self.interfaces

    def _build_interface(self, cls: ClassDecl):
        fields = {}
        methods = {}
        ctor = None

        for f in cls.fields:
            if f.name in fields:
                raise ClassValidationError(f"Field '{f.name}' duplicated in class '{cls.name}'")
            fields[f.name] = {"type": f.vartype, "readonly": f.readonly}

        for m in cls.methods:
            if m.name in methods:
                raise ClassValidationError(f"Method '{m.name}' duplicated in class '{cls.name}'")
            methods[m.name] = {"return": m.return_type, "params": [ptype for ptype,_ in m.params]}

        if cls.constructor:
            ctor = {"params": [ptype for ptype,_ in cls.constructor.params]}

        return {"fields": {k:v["type"] for k,v in fields.items()},
                "readonly": {k:v["readonly"] for k,v in fields.items()},
                "methods": methods,
                "ctor": ctor}
