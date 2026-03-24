# Basic Bridge Test (ROS2)

This combines a quick manual check with a small automated harness. It assumes ROS2 is installed and sourced.

## Manual Steps
1. Source ROS2:
   - `source /opt/ros/<distro>/setup.bash`
2. Run the compiler with the bridge enabled:
   - `python mars_compiler/main.py test_file.mars --ros-autostart --ros-bridge auto --ros-topics-file ros_topics.txt --ros-version 2`
3. Verify the topics file exists and includes your ROS2 topics:
   - `cat ros_topics.txt`

## Automated Harness
The harness starts the bridge, subscribes via the bridge, publishes one ROS2 message, and verifies the message is received.

Run:
```bash
python mars_compiler/basic_bridge_test.py --ros-version 2
```

Expected output:
- `PASS: received message from /mars_test`

If it fails, confirm:
- ROS2 is installed and sourced.
- `ros2` is on PATH.
- The environment can import `rclpy`.