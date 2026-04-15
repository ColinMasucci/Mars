# How MARS connects to ROS bridge (ros_bridge.py) to send/receive messages and query topics.

import json
import select
import socket
from typing import Any, Dict, List


class RosBridgeError(Exception):
    pass


class RosBridgeClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 5566, connect_timeout: float = 1.0):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self._sock = None
        self._buffer = b""
        self._connected = False

    def connect(self) -> bool:
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError:
            return False
        sock.setblocking(False)
        self._sock = sock
        self._connected = True
        return True

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def send(self, payload: Dict[str, Any]) -> None:
        if not self._connected or not self._sock:
            return
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self._sock.sendall(data)

    def request_topics(self) -> None:
        self.send({"op": "get_topics"})

    def subscribe(self, topics: List[Dict[str, Any]]) -> None:
        self.send({"op": "subscribe", "topics": topics})

    def publish(self, topic: str, msg_type: str, msg: Any) -> None:
        self.send({"op": "publish", "topic": topic, "type": msg_type, "msg": msg})

    def poll(self, max_messages: int = 100) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if not self._connected or not self._sock:
            return messages

        while len(messages) < max_messages:
            try:
                rlist, _, _ = select.select([self._sock], [], [], 0)
            except (OSError, ValueError):
                self.close()
                break

            if not rlist:
                break

            try:
                chunk = self._sock.recv(4096)
            except BlockingIOError:
                break

            if not chunk:
                self.close()
                break

            self._buffer += chunk
            while b"\n" in self._buffer and len(messages) < max_messages:
                line, self._buffer = self._buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    messages.append(json.loads(line.decode("utf-8")))
                except Exception as e:
                    messages.append({"op": "error", "message": f"Invalid JSON from bridge: {e}"})

        return messages


def write_topics_file(path: str, topics: List[Dict[str, Any]]) -> None:
    lines: List[str] = []
    if not topics:
        lines.append("# no topics")
    else:
        for entry in topics:
            name = entry.get("name", "<unknown>")
            msg_type = entry.get("type", "<unknown>")
            lines.append(f"{name} ({msg_type})")

            schema = entry.get("schema")
            if schema is not None:
                lines.extend(_format_schema(schema, indent=2))
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def _format_schema(schema: Any, indent: int) -> List[str]:
    pad = " " * indent
    lines: List[str] = []

    if isinstance(schema, dict):
        for key, val in schema.items():
            if isinstance(val, dict):
                lines.append(f"{pad}{key}:")
                lines.extend(_format_schema(val, indent + 2))
            elif isinstance(val, list):
                lines.append(f"{pad}{key}: [")
                for item in val:
                    lines.extend(_format_schema(item, indent + 2))
                lines.append(f"{pad}]")
            else:
                lines.append(f"{pad}{key}: {val}")
        return lines

    if isinstance(schema, list):
        lines.append(f"{pad}[")
        for item in schema:
            lines.extend(_format_schema(item, indent + 2))
        lines.append(f"{pad}]")
        return lines

    lines.append(f"{pad}{schema}")
    return lines
