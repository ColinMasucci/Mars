from graphviz import Digraph
from dataclasses import is_dataclass, fields
import colorsys
import hashlib

def visualize(node):
    """Generate a Graphviz Digraph from the AST."""
    dot = Digraph(comment="Abstract Syntax Tree", format="png")

    def add_node(n, parent_id=None):
        node_id = str(id(n))

        # Determine label dynamically
        label = type(n).__name__
        
        if is_dataclass(n):
            # Include field names and values (basic literals only)
            parts = []
            for f in fields(n):
                val = getattr(n, f.name)
                if isinstance(val, (int, float, str)):
                    parts.append(f"{f.name}={repr(val)}")
            if parts:
                label += "\\n" + "\\n".join(parts)
        else:
            label += f"\\n{repr(n)}"

        color = _pattern_tint(label)
        dot.node(node_id, label, shape="box", style="filled", fillcolor=color)

        # Recurse into dataclass fields that look like child nodes
        if is_dataclass(n):
            for f in fields(n):
                val = getattr(n, f.name)
                if is_dataclass(val):  # child node
                    add_node(val, node_id)
                elif isinstance(val, list):  # e.g. lists of child nodes
                    for item in val:
                        if is_dataclass(item):
                            add_node(item, node_id)

        if parent_id:
            dot.edge(parent_id, node_id)

    add_node(node)
    return dot


def _pattern_tint(name: str) -> str:
    """Color nodes based on naming patterns, with fallback to a random-generated color based on node name."""
    if "Literal" in name:
        return "#d1f7c4"  # light green
    elif "Op" in name:
        return "#ffcccc"  # soft red
    elif "Decl" in name or "Def" in name:
        return "#d0e0ff"  # blue tint
    elif "Stmt" in name or "Statement" in name:
        return "#ffe7b3"  # yellow tint
    return _class_color(name)  # fallback to generated color

def _class_color(name: str) -> str:
    """Generate a stable pastel color for a given class name."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    hue = (h % 360) / 360.0
    lightness = 0.85
    saturation = 0.5
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
