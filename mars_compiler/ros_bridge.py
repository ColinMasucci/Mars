# Actual ROS Node

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import select
import socket
import sys
import time


ROS1_PRIMITIVES = {
    "bool": "bool",
    "int8": "int",
    "uint8": "int",
    "int16": "int",
    "uint16": "int",
    "int32": "int",
    "uint32": "int",
    "int64": "int",
    "uint64": "int",
    "float32": "float",
    "float64": "float",
    "string": "string",
    "char": "int",
    "byte": "int",
    "time": "time",
    "duration": "duration",
}

ROS2_PRIMITIVES = {
    "boolean": "bool",
    "bool": "bool",
    "int8": "int",
    "uint8": "int",
    "int16": "int",
    "uint16": "int",
    "int32": "int",
    "uint32": "int",
    "int64": "int",
    "uint64": "int",
    "float32": "float",
    "float64": "float",
    "double": "float",
    "string": "string",
    "wstring": "string",
    "char": "int",
    "byte": "int",
}

ROS1_ARRAY_RE = re.compile(r"^(?P<base>[^\[]+)(?:\[(?P<len>\d*)\])?$")
ROS2_SEQ_RE = re.compile(r"^sequence<(?P<base>.+?)(?:,\s*(?P<len>\d+))?>$")
ROS2_ARRAY_RE = re.compile(r"^array<(?P<base>.+?),\s*(?P<len>\d+)>$")


class BridgeServer:
    def __init__(self, bridge, host: str, port: int):
        self.bridge = bridge
        self.host = host
        self.port = port
        self.sock = None
        self.client = None
        self._buffer = b""

    def run(self):
        self.bridge.init_ros()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        self.sock.setblocking(False)

        try:
            while True:
                self._accept_client()
                self._handle_client_input()
                self._flush_outbox()
                self.bridge.spin_once()
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        finally:
            self._close_client()
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass

    def _accept_client(self):
        try:
            client, _addr = self.sock.accept()
        except BlockingIOError:
            return
        except OSError:
            return

        self._close_client()
        client.setblocking(False)
        self.client = client
        self._buffer = b""

    def _close_client(self):
        if self.client:
            try:
                self.client.close()
            except OSError:
                pass
        self.client = None
        self._buffer = b""

    def _handle_client_input(self):
        if not self.client:
            return

        try:
            rlist, _, _ = select.select([self.client], [], [], 0)
        except (OSError, ValueError):
            self._close_client()
            return

        if not rlist:
            return

        try:
            chunk = self.client.recv(4096)
        except BlockingIOError:
            return
        except OSError:
            self._close_client()
            return

        if not chunk:
            self._close_client()
            return

        self._buffer += chunk
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception as e:
                self._send({"op": "error", "message": f"Invalid JSON: {e}"})
                continue
            self._handle_command(msg)

    def _handle_command(self, msg):
        op = msg.get("op")
        if op == "get_topics":
            topics = self.bridge.list_topics()
            self._send({"op": "topics", "topics": topics})
            return
        if op == "subscribe":
            topics = msg.get("topics", [])
            for entry in topics:
                self.bridge.subscribe(entry.get("name"), entry.get("type"))
            return
        if op == "publish":
            self.bridge.publish(msg.get("topic"), msg.get("type"), msg.get("msg"))
            return

        self._send({"op": "error", "message": f"Unknown op: {op}"})

    def _flush_outbox(self):
        if not self.client:
            return
        while True:
            try:
                msg = self.bridge.outbox.get_nowait()
            except queue.Empty:
                return
            self._send(msg)

    def _send(self, payload):
        if not self.client:
            return
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self.client.sendall(data)
        except OSError:
            self._close_client()


class Ros1Bridge:
    def __init__(self):
        self.outbox = queue.Queue()
        self._subs = {}
        self._pubs = {}
        self._topic_type_cache = {}

    def init_ros(self):
        import rospy

        rospy.init_node("mars_bridge", anonymous=True, disable_signals=True)
        self._rospy = rospy
        self._roslib = __import__("roslib.message", fromlist=["message"])
        self._genpy = __import__("genpy")

    def spin_once(self):
        # rospy callbacks are handled in background threads
        return

    def list_topics(self):
        topics = []
        for name, msg_type in self._rospy.get_published_topics(""):
            self._topic_type_cache[name] = msg_type
            schema = self._schema_for_type(msg_type, depth=2, visited=set())
            topics.append({"name": name, "type": msg_type, "schema": schema})
        return topics

    def subscribe(self, topic: str | None, msg_type: str | None):
        if not topic:
            return
        if topic in self._subs:
            return
        msg_type = msg_type or self._resolve_topic_type(topic)
        if not msg_type:
            self.outbox.put({"op": "error", "message": f"Unknown type for {topic}"})
            return

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            self.outbox.put({"op": "error", "message": f"Type not found: {msg_type}"})
            return

        self._topic_type_cache[topic] = msg_type
        self._subs[topic] = self._rospy.Subscriber(
            topic,
            msg_cls,
            self._make_callback(topic, msg_type),
            queue_size=1,
        )

    def publish(self, topic: str | None, msg_type: str | None, msg: dict | None):
        if not topic:
            return
        msg_type = msg_type or self._resolve_topic_type(topic)
        if not msg_type:
            self.outbox.put({"op": "error", "message": f"Unknown type for {topic}"})
            return

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            self.outbox.put({"op": "error", "message": f"Type not found: {msg_type}"})
            return

        pub = self._pubs.get(topic)
        if not pub:
            pub = self._rospy.Publisher(topic, msg_cls, queue_size=10)
            self._pubs[topic] = pub

        if isinstance(msg, dict):
            ros_msg = self._dict_to_msg(msg, msg_cls)
        else:
            ros_msg = msg_cls()
        pub.publish(ros_msg)

    def _make_callback(self, topic, msg_type):
        def cb(msg):
            payload = {
                "op": "msg",
                "topic": topic,
                "type": msg_type,
                "msg": self._msg_to_dict(msg, msg_type),
            }
            self.outbox.put(payload)

        return cb

    def _resolve_topic_type(self, topic: str) -> str | None:
        for name, msg_type in self._rospy.get_published_topics(""):
            if name == topic:
                return msg_type
        return None

    def _message_class(self, msg_type: str):
        return self._roslib.get_message_class(msg_type)

    def _schema_for_type(self, msg_type: str, depth: int, visited: set[str]):
        if depth <= 0:
            return msg_type
        if msg_type in visited:
            return msg_type
        visited.add(msg_type)

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            return msg_type

        slots = getattr(msg_cls, "__slots__", [])
        slot_types = getattr(msg_cls, "_slot_types", [])
        schema = {}
        for name, ftype in zip(slots, slot_types):
            schema[name] = self._schema_for_field(ftype, depth - 1, visited)
        return schema

    def _schema_for_field(self, ftype: str, depth: int, visited: set[str]):
        base, is_array, _size = _parse_ros1_array(ftype)
        if is_array:
            return [self._schema_for_field(base, depth, visited)]
        if base in ROS1_PRIMITIVES:
            return ROS1_PRIMITIVES[base]
        return self._schema_for_type(base, depth, visited)

    def _msg_to_dict(self, msg, msg_type: str):
        slots = getattr(msg, "__slots__", [])
        slot_types = getattr(msg, "_slot_types", [])
        result = {}
        for name, ftype in zip(slots, slot_types):
            result[name] = self._value_to_json(getattr(msg, name), ftype)
        return result

    def _value_to_json(self, value, ftype: str):
        base, is_array, _size = _parse_ros1_array(ftype)
        if is_array:
            return [self._value_to_json(v, base) for v in value]
        if base in ROS1_PRIMITIVES:
            if base in ("time", "duration"):
                return {"secs": value.secs, "nsecs": value.nsecs}
            return value
        return self._msg_to_dict(value, base)

    def _dict_to_msg(self, data: dict, msg_cls):
        msg = msg_cls()
        slots = getattr(msg_cls, "__slots__", [])
        slot_types = getattr(msg_cls, "_slot_types", [])
        for name, ftype in zip(slots, slot_types):
            if name not in data:
                continue
            setattr(msg, name, self._json_to_value(data[name], ftype))
        return msg

    def _json_to_value(self, data, ftype: str):
        base, is_array, _size = _parse_ros1_array(ftype)
        if is_array:
            return [self._json_to_value(v, base) for v in (data or [])]
        if base in ROS1_PRIMITIVES:
            if base in ("time", "duration"):
                if isinstance(data, dict):
                    secs = int(data.get("secs", 0))
                    nsecs = int(data.get("nsecs", 0))
                    if base == "time":
                        return self._rospy.Time(secs, nsecs)
                    return self._rospy.Duration(secs, nsecs)
                try:
                    if base == "time":
                        return self._rospy.Time.from_sec(float(data))
                    return self._rospy.Duration.from_sec(float(data))
                except Exception:
                    return self._rospy.Time(0, 0) if base == "time" else self._rospy.Duration(0, 0)
            if ROS1_PRIMITIVES[base] == "float":
                return float(data)
            if ROS1_PRIMITIVES[base] == "int":
                return int(data)
            if ROS1_PRIMITIVES[base] == "bool":
                return bool(data)
            if ROS1_PRIMITIVES[base] == "string":
                return str(data)
            return data

        msg_cls = self._message_class(base)
        if msg_cls and isinstance(data, dict):
            return self._dict_to_msg(data, msg_cls)
        return data


class Ros2Bridge:
    def __init__(self):
        self.outbox = queue.Queue()
        self._subs = {}
        self._pubs = {}
        self._topic_type_cache = {}

    def init_ros(self):
        import rclpy
        from rclpy.node import Node
        from rosidl_runtime_py.utilities import get_message

        rclpy.init(args=None)
        self._rclpy = rclpy
        self._node = Node("mars_bridge")
        self._get_message = get_message

    def spin_once(self):
        if self._rclpy.ok():
            self._rclpy.spin_once(self._node, timeout_sec=0.0)

    def list_topics(self):
        topics = []
        for name, types in self._node.get_topic_names_and_types():
            msg_type = types[0] if types else None
            if not msg_type:
                continue
            self._topic_type_cache[name] = msg_type
            schema = self._schema_for_type(msg_type, depth=2, visited=set())
            topics.append({"name": name, "type": msg_type, "schema": schema})
        return topics

    def subscribe(self, topic: str | None, msg_type: str | None):
        if not topic:
            return
        if topic in self._subs:
            return
        msg_type = msg_type or self._resolve_topic_type(topic)
        if not msg_type:
            self.outbox.put({"op": "error", "message": f"Unknown type for {topic}"})
            return

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            self.outbox.put({"op": "error", "message": f"Type not found: {msg_type}"})
            return

        self._topic_type_cache[topic] = msg_type
        self._subs[topic] = self._node.create_subscription(
            msg_cls,
            topic,
            self._make_callback(topic, msg_type),
            10,
        )

    def publish(self, topic: str | None, msg_type: str | None, msg: dict | None):
        if not topic:
            return
        msg_type = msg_type or self._resolve_topic_type(topic)
        if not msg_type:
            self.outbox.put({"op": "error", "message": f"Unknown type for {topic}"})
            return

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            self.outbox.put({"op": "error", "message": f"Type not found: {msg_type}"})
            return

        pub = self._pubs.get(topic)
        if not pub:
            pub = self._node.create_publisher(msg_cls, topic, 10)
            self._pubs[topic] = pub

        if isinstance(msg, dict):
            ros_msg = self._dict_to_msg(msg, msg_cls)
        else:
            ros_msg = msg_cls()
        pub.publish(ros_msg)

    def _make_callback(self, topic, msg_type):
        def cb(msg):
            payload = {
                "op": "msg",
                "topic": topic,
                "type": msg_type,
                "msg": self._msg_to_dict(msg, msg_type),
            }
            self.outbox.put(payload)

        return cb

    def _resolve_topic_type(self, topic: str) -> str | None:
        for name, types in self._node.get_topic_names_and_types():
            if name == topic and types:
                return types[0]
        return None

    def _message_class(self, msg_type: str):
        try:
            return self._get_message(_normalize_ros2_type(msg_type))
        except Exception:
            return None

    def _schema_for_type(self, msg_type: str, depth: int, visited: set[str]):
        if depth <= 0:
            return msg_type
        if msg_type in visited:
            return msg_type
        visited.add(msg_type)

        msg_cls = self._message_class(msg_type)
        if not msg_cls:
            return msg_type

        fields = msg_cls.get_fields_and_field_types()
        schema = {}
        for name, ftype in fields.items():
            schema[name] = self._schema_for_field(ftype, depth - 1, visited)
        return schema

    def _schema_for_field(self, ftype: str, depth: int, visited: set[str]):
        base, is_array, _size = _parse_ros2_array(ftype)
        if is_array:
            return [self._schema_for_field(base, depth, visited)]
        if base in ROS2_PRIMITIVES:
            return ROS2_PRIMITIVES[base]
        return self._schema_for_type(base, depth, visited)

    def _msg_to_dict(self, msg, msg_type: str):
        fields = msg.get_fields_and_field_types()
        result = {}
        for name, ftype in fields.items():
            result[name] = self._value_to_json(getattr(msg, name), ftype)
        return result

    def _value_to_json(self, value, ftype: str):
        base, is_array, _size = _parse_ros2_array(ftype)
        if is_array:
            return [self._value_to_json(v, base) for v in value]
        if base in ROS2_PRIMITIVES:
            return value
        return self._msg_to_dict(value, base)

    def _dict_to_msg(self, data: dict, msg_cls):
        msg = msg_cls()
        fields = msg.get_fields_and_field_types()
        for name, ftype in fields.items():
            if name not in data:
                continue
            setattr(msg, name, self._json_to_value(data[name], ftype))
        return msg

    def _json_to_value(self, data, ftype: str):
        base, is_array, _size = _parse_ros2_array(ftype)
        if is_array:
            return [self._json_to_value(v, base) for v in (data or [])]
        if base in ROS2_PRIMITIVES:
            if ROS2_PRIMITIVES[base] == "float":
                return float(data)
            if ROS2_PRIMITIVES[base] == "int":
                return int(data)
            if ROS2_PRIMITIVES[base] == "bool":
                return bool(data)
            if ROS2_PRIMITIVES[base] == "string":
                return str(data)
            return data

        msg_cls = self._message_class(base)
        if msg_cls and isinstance(data, dict):
            return self._dict_to_msg(data, msg_cls)
        return data


def _parse_ros1_array(ftype: str) -> tuple[str, bool, int | None]:
    match = ROS1_ARRAY_RE.match(ftype)
    if not match:
        return ftype, False, None
    base = match.group("base")
    size = match.group("len")
    if size is not None and size != "":
        return base, True, int(size)
    if ftype.endswith("]"):
        return base, True, None
    return base, False, None


def _parse_ros2_array(ftype: str) -> tuple[str, bool, int | None]:
    match = ROS2_ARRAY_RE.match(ftype)
    if match:
        return match.group("base"), True, int(match.group("len"))
    match = ROS2_SEQ_RE.match(ftype)
    if match:
        size = match.group("len")
        return match.group("base"), True, int(size) if size else None
    return ftype, False, None


def _normalize_ros2_type(type_str: str) -> str:
    if "/msg/" not in type_str and "/" in type_str:
        pkg, name = type_str.split("/", 1)
        return f"{pkg}/msg/{name}"
    return type_str


def _detect_ros_version(explicit: str | None) -> str | None:
    if explicit:
        if explicit in ("1", "2"):
            return explicit
        if explicit.lower() == "ros1":
            return "1"
        if explicit.lower() == "ros2":
            return "2"

    env = os.environ.get("ROS_VERSION")
    if env in ("1", "2"):
        return env

    try:
        import rospy  # noqa: F401
        return "1"
    except Exception:
        pass

    try:
        import rclpy  # noqa: F401
        return "2"
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="MARS ROS bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5566)
    parser.add_argument("--ros-version", default=None)
    args = parser.parse_args()

    ros_version = _detect_ros_version(args.ros_version)
    if ros_version == "1":
        bridge = Ros1Bridge()
    elif ros_version == "2":
        bridge = Ros2Bridge()
    else:
        print("[ros] Unable to detect ROS version. Set ROS_VERSION or --ros-version.")
        sys.exit(1)

    server = BridgeServer(bridge, host=args.host, port=args.port)
    server.run()


if __name__ == "__main__":
    main()
