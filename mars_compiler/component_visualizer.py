from graphviz import Digraph


def visualize_components(components):
    """Create a Graphviz digraph of components, showing inheritance and subcomponent links."""
    dot = Digraph(comment="Component Tree", format="png")

    # Index components by name for lookup
    comp_map = {c.name: c for c in components}

    for comp in components:
        label_lines = [comp.name]
        if comp.parameters:
            params = "\\n".join(f"param: {p.vartype} {p.name}" for p in comp.parameters)
            label_lines.append(params)
        if comp.functions:
            funcs = "\\n".join(
                f"fn: {f.return_type} {f.name}({', '.join(pt for pt, _ in f.params)})"
                for f in comp.functions
            )
            label_lines.append(funcs)
        label = "\\n---\\n".join(label_lines)
        dot.node(comp.name, label, shape="box", style="rounded,filled", fillcolor="#e8f0ff")

        # Inheritance edge
        if comp.parent:
            dot.edge(comp.parent, comp.name, label="extends", style="dashed")

        # Subcomponent edges
        for sub in comp.subcomponents:
            binding_str = ""
            if sub.bindings:
                pairs = [f"{k}={getattr(v, 'value', v)}" for k, v in sub.bindings]
                binding_str = f" ({', '.join(pairs)})"
            label = f"{sub.name}{binding_str}"
            if sub.type_name in comp_map:
                dot.edge(comp.name, sub.type_name, label=label, style="solid")
            else:
                dot.edge(comp.name, sub.type_name, label=label, style="dotted", color="red")

    return dot
