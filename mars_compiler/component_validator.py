from ast_nodes import ComponentDef


class ComponentValidationError(Exception):
    pass


class ComponentValidator:
    """
    Validates component inheritance, required functions/params, and subcomponent references.
    Produces a component interface map: name -> {params, funcs, subcomponents}.
    funcs entries carry: return, params (list), has_body (bool)
    """

    def __init__(self, components):
        # Map name -> ComponentDef
        self.components = {c.name: c for c in components}
        if len(self.components) != len(components):
            raise ComponentValidationError("Duplicate component names found")

        self.interfaces = {}
        self._building = set()  # for cycle detection

    def validate(self):
        for name in self.components:
            self._build_interface(name)
        return self.interfaces

    def _build_interface(self, name):
        if name in self.interfaces:
            return self.interfaces[name]
        if name in self._building:
            raise ComponentValidationError(f"Inheritance cycle detected involving '{name}'")

        comp = self.components.get(name)
        if comp is None:
            raise ComponentValidationError(f"Component '{name}' not found")

        self._building.add(name)

        # Inherit from parent
        if comp.parent:
            parent_iface = self._build_interface(comp.parent)
        else:
            parent_iface = {"params": {}, "funcs": {}, "subcomponents": {}}

        iface = {
            "params": dict(parent_iface["params"]),
            "funcs": dict(parent_iface["funcs"]),
            "subcomponents": dict(parent_iface["subcomponents"]),
            "parent": comp.parent,
        }

        # Parameters: allow override only if type matches
        for param in comp.parameters:
            pname = param.name
            ptype = self._normalize_type(param.vartype)
            if pname in iface["params"] and iface["params"][pname] != ptype:
                raise ComponentValidationError(
                    f"Parameter '{pname}' in '{comp.name}' must match inherited type '{iface['params'][pname]}'"
                )
            iface["params"][pname] = ptype

        # Subcomponents: ensure referenced types exist
        for sub in comp.subcomponents:
            if sub.type_name not in self.components:
                raise ComponentValidationError(
                    f"Subcomponent '{sub.name}' in '{comp.name}' references unknown component '{sub.type_name}'"
                )
            if self._is_robot_family(sub.type_name):
                raise ComponentValidationError(
                    f"Subcomponent '{sub.name}' in '{comp.name}' cannot be a Robot-derived component ('{sub.type_name}')"
                )
            iface["subcomponents"][sub.name] = sub.type_name
            # Enforce mandatory params on subcomponent are bound or have defaults
            required = self._required_params(self.components[sub.type_name])
            bindings = {b[0]: b[1] for b in (sub.bindings or [])}
            for rname, rtype in required.items():
                if rname not in bindings:
                    raise ComponentValidationError(
                        f"Subcomponent '{sub.name}' of type '{sub.type_name}' in '{comp.name}' is missing required parameter '{rname}'"
                    )

        # Functions: allow override with different params; return type must match
        for func in comp.functions:
            sig_params = [self._normalize_type(ptype) for ptype, _ in func.params]
            finfo = {
                "return": self._normalize_type(func.return_type),
                "params": sig_params,
                "has_body": func.body is not None,
            }

            if func.name in iface["funcs"]:
                parent_info = iface["funcs"][func.name]
                if parent_info["return"] != finfo["return"]:
                    raise ComponentValidationError(
                        f"Function '{func.name}' in '{comp.name}' must match inherited return type"
                    )
            iface["funcs"][func.name] = finfo

        self._building.remove(name)
        self.interfaces[name] = iface
        return iface

    def _normalize_type(self, typ: str):
        """Mirror the parser/type-checker array normalization (int[] -> array<int>)."""
        if typ.endswith("[]"):
            return f"array<{self._normalize_type(typ[:-2])}>"
        return typ

    def _is_robot_family(self, type_name: str) -> bool:
        if type_name == "Robot":
            return True
        cur = self.components.get(type_name)
        while cur and cur.parent:
            if cur.parent == "Robot":
                return True
            cur = self.components.get(cur.parent)
        return False

    def _required_params(self, comp_def):
        """Return params without defaults (value is None)."""
        req = {}
        for p in comp_def.parameters:
            if p.value is None:
                req[p.name] = self._normalize_type(p.vartype)
        return req
