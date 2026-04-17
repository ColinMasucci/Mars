import os

def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _rel_path(path: str | None) -> str:
    if not path:
        return "<input>"
    root = _repo_root()
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def _line_info(source: str, position: int) -> tuple[int, int, str]:
    if position < 0:
        position = 0
    if position > len(source):
        position = len(source)

    line_start = source.rfind("\n", 0, position)
    line_start = 0 if line_start < 0 else line_start + 1
    line_end = source.find("\n", position)
    if line_end < 0:
        line_end = len(source)

    line_text = source[line_start:line_end]
    line_no = source.count("\n", 0, position) + 1
    col = position - line_start + 1
    return line_no, col, line_text


def _caret_line(line_text: str, col: int) -> str:
    if col < 1:
        col = 1
    prefix = line_text[: col - 1]
    caret_pos = len(prefix.expandtabs(4))
    return " " * caret_pos + "^"


def format_source_error(message: str, source: str, position: int, source_path: str | None, context: str | None = None) -> str:
    line_no, col, line_text = _line_info(source, position)
    header = f"File \"{_rel_path(source_path)}\", line {line_no}"
    if context:
        header += f", in {context}"
    caret = _caret_line(line_text, col)
    return "\n".join([header, f"  {line_text}", f"  {caret}", message])


def _find_node_position(node, seen: set[int] | None = None):
    if node is None:
        return None

    position = getattr(node, "source_position", None)
    if position is not None:
        return position

    if seen is None:
        seen = set()
    node_id = id(node)
    if node_id in seen:
        return None
    seen.add(node_id)

    if isinstance(node, (list, tuple)):
        for item in node:
            position = _find_node_position(item, seen)
            if position is not None:
                return position
        return None

    if isinstance(node, dict):
        for key, value in node.items():
            position = _find_node_position(key, seen)
            if position is not None:
                return position
            position = _find_node_position(value, seen)
            if position is not None:
                return position
        return None

    data = getattr(node, "__dict__", None)
    if not data:
        return None

    for value in data.values():
        position = _find_node_position(value, seen)
        if position is not None:
            return position
    return None


def format_node_error(message: str, source: str | None, node, source_path: str | None, context: str | None = None) -> str:
    if source is None:
        return message
    position = _find_node_position(node)
    if position is None:
        return message
    return format_source_error(message, source, position, source_path, context)
