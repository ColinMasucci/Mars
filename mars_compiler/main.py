import argparse

from interpreter import interpret_code_from_file


def main():
    parser = argparse.ArgumentParser(description="MARS compiler runner")
    parser.add_argument("file", nargs="?", default="test_file.mars")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--ros-autostart", action="store_true")
    parser.add_argument("--ros-bridge", default=None, help="host:port or 'auto'")
    parser.add_argument("--ros-topics-file", default=None)
    parser.add_argument("--ros-version", default=None, help="1 or 2")
    parser.add_argument("--ros-bridge-python", default=None, help="python executable used for autostarted ros_bridge.py")
    parser.add_argument("--ros-bridge-pythonpath", default=None, help="extra PYTHONPATH prepended for autostarted bridge")
    args = parser.parse_args()

    print("===EXAMPLE 001=================================================================================================================")
    interpret_code_from_file(
        args.file,
        config_dir=args.config_dir,
        debug=args.debug,
        ros_bridge=args.ros_bridge,
        ros_topics_file=args.ros_topics_file,
        ros_autostart=args.ros_autostart,
        ros_version=args.ros_version,
        ros_bridge_python=args.ros_bridge_python,
        ros_bridge_pythonpath=args.ros_bridge_pythonpath,
    )
    print("==============================================================================================================================\n")


if __name__ == "__main__":
    main()
