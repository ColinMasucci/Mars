from graphviz import Digraph

from ast_visualizer import _pattern_tint


def _parent_chain(comp, comp_map):
    chain = []
    parent = comp.parent
    while parent:
        chain.append(parent)
        parent_comp = comp_map.get(parent)
        if parent_comp is None:
            break
        parent = parent_comp.parent
    return chain


def _type_chain(type_name, comp_map):
    chain = [type_name]
    comp = comp_map.get(type_name)
    parent = comp.parent if comp else None
    while parent:
        chain.append(parent)
        parent_comp = comp_map.get(parent)
        if parent_comp is None:
            break
        parent = parent_comp.parent
    return chain


def _component_label(name, type_chain):
    parts = [f"<B>{name}</B>"]
    parts.extend(type_chain)
    return "<" + "<BR/>".join(parts) + ">"


def visualize_components(components):
    """Create a Graphviz digraph of components, showing subcomponent links only."""
    dot = Digraph(comment="Component Tree", format="png")
    dot.attr(fontname="Helvetica")
    dot.attr("node", shape="box", style="rounded,filled", fontname="Helvetica")
    dot.attr("edge", fontname="Helvetica")

    comp_map = {c.name: c for c in components}
    nodes = {}
    edges = []

    def _add_node(node_id, label, color):
        if node_id in nodes:
            return
        nodes[node_id] = (label, color)

    def _add_children(parent_id, type_name, type_stack):
        comp = comp_map.get(type_name)
        if comp is None:
            return
        for sub in comp.subcomponents:
            node_id = f"{parent_id}.{sub.name}"
            label = _component_label(sub.name, _type_chain(sub.type_name, comp_map))
            color = _pattern_tint(sub.type_name)
            _add_node(node_id, label, color)
            edges.append((parent_id, node_id))
            if sub.type_name in type_stack:
                continue
            _add_children(node_id, sub.type_name, type_stack + [sub.type_name])

    def _is_robot_family(comp):
        if comp.name == "Robot":
            return True
        return "Robot" in _parent_chain(comp, comp_map)

    for comp in components:
        if not _is_robot_family(comp):
            continue
        if comp.name == "Robot":
            continue
        root_id = comp.name
        label = _component_label(comp.name, _parent_chain(comp, comp_map))
        color = _pattern_tint(comp.name)
        _add_node(root_id, label, color)
        _add_children(root_id, comp.name, [comp.name])

    connected = set(nodes.keys())
    for src, dst in edges:
        connected.add(src)
        connected.add(dst)

    for node_id in connected:
        label, color = nodes[node_id]
        dot.node(node_id, label=label, fillcolor=color)

    for src, dst in edges:
        dot.edge(src, dst)

    return dot
