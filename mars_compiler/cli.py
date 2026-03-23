import argparse
from mars_compiler.interpreter import interpret_code_from_file

def main():
    parser = argparse.ArgumentParser(prog="mars")

    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run")
    run.add_argument("file")

    ros = sub.add_parser("ros")
    ros_sub = ros.add_subparsers(dest="ros_command")
    ros_sub.add_parser("bridge")

    args = parser.parse_args()

    if args.command == "run":
        interpret_code_from_file(args.file)

    elif args.command == "ros":
        if args.ros_command == "bridge":
            interpret_code_from_file(
                "ros_stub.mars",
                ros_autostart=True
            )