class ComponentRegistry:
    def __init__(self):
        self.components = {}

    def register(self, component_def):
        name = component_def.name
        if name in self.components:
            raise Exception(f"Component '{name}' already defined")
        self.components[name] = component_def

    def get(self, name):
        return self.components.get(name)
