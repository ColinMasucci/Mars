from asyncio import subprocess
from pathlib import Path

import os
import subprocess

# TOPICS_FILE = "ros_topics.txt"


def get_ros_dir(workspace_root: Path):
    return workspace_root / "ros"


def get_topics_file(workspace_root: Path):
    return get_ros_dir(workspace_root) / "topics.txt"


def ensure_ros_dir(workspace_root: Path):
    ros_dir = get_ros_dir(workspace_root)
    ros_dir.mkdir(exist_ok=True)
    return ros_dir


def _load_topics_file(workspace_root: Path):
    topics_file = get_topics_file(workspace_root)
    if not os.path.exists(topics_file):
        raise FileNotFoundError(f"{topics_file} not found. Run 'mars ros bridge' first.")

    with open(topics_file, "r") as f:
        return f.read()


def _parse_topics(raw_text):
    """
    Parses the topics file into a dictionary:
    {
        "/cmd_vel": {
            "type": "geometry_msgs/msg/Twist",
            "details": "raw block text..."
        }
    }
    """
    topics = {}
    lines = raw_text.splitlines()

    current_topic = None
    current_block = []

    for line in lines:
        # Detect topic header (starts with /)
        if line.startswith("/"):
            if current_topic:
                topics[current_topic]["details"] = "\n".join(current_block)

            parts = line.split(" ", 1)
            topic_name = parts[0]
            topic_type = parts[1].strip("()") if len(parts) > 1 else "unknown"

            topics[topic_name] = {"type": topic_type, "details": ""}

            current_topic = topic_name
            current_block = []

        else:
            current_block.append(line)

    # Save last topic
    if current_topic:
        topics[current_topic]["details"] = "\n".join(current_block)

    return topics


# ========================
# CLI FUNCTIONS
# ========================


def list_topics(workspace_root: Path):
    raw = _load_topics_file(workspace_root=workspace_root)
    topics = _parse_topics(raw)

    print("Available ROS Topics:\n")
    for name, data in topics.items():
        print(f"{name}  [{data['type']}]")


def show_topic(topic_name: str, workspace_root: Path):
    raw = _load_topics_file(workspace_root=workspace_root)
    topics = _parse_topics(raw)

    if topic_name not in topics:
        print(f"Topic '{topic_name}' not found.")
        return

    print(f"{topic_name} ({topics[topic_name]['type']})\n")
    print(topics[topic_name]["details"])


def search_topics(keyword: str, workspace_root: Path):
    raw = _load_topics_file(workspace_root=workspace_root)
    topics = _parse_topics(raw)

    print(f"Searching for '{keyword}'...\n")

    for name, data in topics.items():
        if keyword in name or keyword in data["type"]:
            print(f"{name}  [{data['type']}]")


def fetch_topics_live(workspace_root: Path, duration=5):
    ros_dir = ensure_ros_dir(workspace_root)
    topics_file = get_topics_file(workspace_root)

    cmd = [
        "python3",
        "-m",
        "mars_lang.ros.fetch_ros_topics",
        "--ros-version",
        "2",
        "--output",
        str(topics_file),
        "--duration",
        str(duration),
        "--ros-bridge-python",
        "/usr/bin/python3.8",
        "--ros-bridge-pythonpath",
        "/opt/ros/foxy/lib/python3.8/site-packages",
    ]

    subprocess.run(cmd, check=True)
