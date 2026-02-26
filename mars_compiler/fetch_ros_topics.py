from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from ros_bridge_client import RosBridgeClient, write_topics_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Autostart ROS bridge, fetch topics once, and exit")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5566)
    parser.add_argument("--ros-version", default=None, help="1 or 2")
    parser.add_argument("--output", default="ros_topics.txt")
    parser.add_argument("--duration", type=float, default=5.0, help="poll duration in seconds")
    parser.add_argument("--ros-bridge-python", default=None, help="python executable used for autostarted ros_bridge.py")
    parser.add_argument("--ros-bridge-pythonpath", default=None, help="extra PYTHONPATH prepended for autostarted bridge")
    args = parser.parse_args()

    bridge_proc = _start_bridge(args)
    if bridge_proc is None:
        _clear_file(args.output)
        print("no topics")
        return 0

    client = RosBridgeClient(host=args.host, port=args.port, connect_timeout=1.0)
    duration = max(0.1, float(args.duration))
    end_time = time.monotonic() + duration
    try:
        while time.monotonic() < end_time:
            if client.connect():
                break
            time.sleep(0.05)

        if not client.is_connected():
            _clear_file(args.output)
            print("no topics")
            return 0

        latest_non_empty_topics = None
        next_request_time = 0.0
        while time.monotonic() < end_time:
            now = time.monotonic()
            if now >= next_request_time:
                client.request_topics()
                next_request_time = now + 0.5
            for msg in client.poll():
                op = msg.get("op")
                if op == "topics":
                    topics = msg.get("topics", [])
                    if not isinstance(topics, list):
                        topics = []
                    if topics:
                        latest_non_empty_topics = topics
                if op == "error":
                    message = msg.get("message")
                    if message:
                        print(f"[ros] {message}")
            time.sleep(0.05)

        if latest_non_empty_topics:
            write_topics_file(args.output, latest_non_empty_topics)
            print(f"wrote {len(latest_non_empty_topics)} topics to {args.output}")
            return 0

        _clear_file(args.output)
        print("no topics")
        return 0
    finally:
        client.close()
        _stop_bridge(bridge_proc)


def _start_bridge(args) -> subprocess.Popen | None:
    bridge_python = args.ros_bridge_python or os.environ.get("MARS_ROS_BRIDGE_PYTHON") or sys.executable
    bridge_pythonpath = args.ros_bridge_pythonpath or os.environ.get("MARS_ROS_BRIDGE_PYTHONPATH")
    script_path = os.path.join(os.path.dirname(__file__), "ros_bridge.py")

    cmd = [bridge_python, "-u", script_path, "--host", args.host, "--port", str(args.port)]
    if args.ros_version:
        cmd.extend(["--ros-version", args.ros_version])

    child_env = os.environ.copy()
    if bridge_pythonpath:
        existing = child_env.get("PYTHONPATH")
        child_env["PYTHONPATH"] = f"{bridge_pythonpath}:{existing}" if existing else bridge_pythonpath

    try:
        proc = subprocess.Popen(cmd, env=child_env)
    except Exception as e:
        print(f"[ros] Failed to start bridge process: {e}")
        return None

    if bridge_pythonpath:
        print(f"[ros] Autostarted bridge using {bridge_python} with bridge PYTHONPATH prefix {bridge_pythonpath}")
    else:
        print(f"[ros] Autostarted bridge using {bridge_python}")
    return proc


def _stop_bridge(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _clear_file(path: str) -> None:
    with open(path, "w", encoding="utf-8"):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
