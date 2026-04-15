import argparse
import subprocess
import sys
import time

from ros_bridge_client import RosBridgeClient


def main():
    parser = argparse.ArgumentParser(description="Basic ROS bridge test (ROS2)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5566)
    parser.add_argument("--ros-version", default="2")
    parser.add_argument("--topic", default="/mars_test")
    parser.add_argument("--type", dest="msg_type", default="std_msgs/msg/String")
    parser.add_argument("--message", default="hello")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    bridge_cmd = [
        sys.executable,
        "-u",
        "mars_compiler/ros_bridge.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--ros-version",
        args.ros_version,
    ]

    bridge_proc = None
    try:
        bridge_proc = subprocess.Popen(bridge_cmd)
        client = RosBridgeClient(host=args.host, port=args.port, connect_timeout=1.0)
        if not _connect_with_retry(client, retries=30, delay=0.1):
            print("FAIL: could not connect to bridge")
            return 1

        client.subscribe([{"name": args.topic, "type": args.msg_type}])

        pub_cmd = [
            "ros2",
            "topic",
            "pub",
            "--once",
            args.topic,
            args.msg_type,
            f"{{data: '{args.message}'}}",
        ]
        subprocess.check_call(pub_cmd)

        deadline = time.time() + args.timeout
        while time.time() < deadline:
            for msg in client.poll():
                if msg.get("op") == "msg" and msg.get("topic") == args.topic:
                    payload = msg.get("msg", {})
                    data = payload.get("data")
                    if data == args.message:
                        print(f"PASS: received message from {args.topic}")
                        return 0
            time.sleep(0.05)

        print("FAIL: did not receive message in time")
        return 2
    finally:
        if bridge_proc:
            try:
                bridge_proc.terminate()
                bridge_proc.wait(timeout=2)
            except Exception:
                try:
                    bridge_proc.kill()
                except Exception:
                    pass


def _connect_with_retry(client: RosBridgeClient, retries: int, delay: float) -> bool:
    for _ in range(retries + 1):
        if client.connect():
            return True
        time.sleep(delay)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
