# MARS
This is a WPI MQP project related to Robotics and Computer Science. This is just placeholder text for now.



### AST Visualizer
The AST Visualizer development tool uses a library called Graphviz. Steps to download it:
    1. Follow the instructions https://graphviz.org/download/. Make sure it is added to your PATH.
    2. pip install graphviz

### ROS Bridge (Optional)
The VM can talk to ROS through an optional bridge process. When enabled, the compiler can auto-start the bridge and connect the VM without manual shell commands.

Requirements:
1. ROS1 or ROS2 must be installed and sourced in the same environment that launches the compiler.
2. The ROS Python packages must be importable (`rospy` for ROS1 or `rclpy` for ROS2).

How it works:
1. The compiler starts `mars_compiler/ros_bridge.py` as a separate process.
2. The VM connects to the bridge over a local TCP socket.
3. The bridge exposes topics and message schemas (no hardcoded message types in the VM).

Enable from code:
```python
from interpreter import interpret_code_from_file

interpret_code_from_file(
    "test_file.mars",
    ros_autostart=True,
    ros_bridge="auto",       # defaults to 127.0.0.1:5566
    ros_topics_file="ros_topics.txt",
    ros_version="1",         # or "2"; optional if ROS_VERSION is set
)
```

Enable from CLI:
```bash
python mars_compiler/main.py test_file.mars  --ros-autostart  --ros-bridge auto  --ros-topics-file ros_topics.txt 
  --ros-version 1
```

Topics file:
1. When the bridge is connected, a topics file is written (default `ros_topics.txt`).
2. Each entry includes the topic name, ROS message type, and a simplified schema (float/int/string/arrays/nested objects).

Basic bridge test:
- See `docs/basic_bridge_test.md` for a combined manual check and a small ROS2 harness.
