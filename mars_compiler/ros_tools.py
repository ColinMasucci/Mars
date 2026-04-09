import os

TOPICS_FILE = "ros_topics.txt"


def _load_topics_file():
    if not os.path.exists(TOPICS_FILE):
        raise FileNotFoundError(
            f"{TOPICS_FILE} not found. Run 'mars ros bridge' first."
        )

    with open(TOPICS_FILE, "r") as f:
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

            topics[topic_name] = {
                "type": topic_type,
                "details": ""
            }

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

def list_topics():
    raw = _load_topics_file()
    topics = _parse_topics(raw)

    print("Available ROS Topics:\n")
    for name, data in topics.items():
        print(f"{name}  [{data['type']}]")


def show_topic(topic_name):
    raw = _load_topics_file()
    topics = _parse_topics(raw)

    if topic_name not in topics:
        print(f"Topic '{topic_name}' not found.")
        return

    print(f"{topic_name} ({topics[topic_name]['type']})\n")
    print(topics[topic_name]["details"])


def search_topics(keyword):
    raw = _load_topics_file()
    topics = _parse_topics(raw)

    print(f"Searching for '{keyword}'...\n")

    for name, data in topics.items():
        if keyword in name or keyword in data["type"]:
            print(f"{name}  [{data['type']}]")