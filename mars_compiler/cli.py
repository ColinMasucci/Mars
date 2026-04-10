import argparse
from mars_compiler.interpreter import interpret_code_from_file
from mars_compiler import ros_tools
from mars_compiler.ros_tools import list_topics

def main():
    parser = argparse.ArgumentParser(prog="mars")

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("file")


    ros = sub.add_parser("ros")
    ros_sub = ros.add_subparsers(dest="ros_command", required=True)
    ros_sub.add_parser("bridge")

    ros_topics = ros_sub.add_parser("topics")
    ros_topics.add_argument("--show")
    ros_topics.add_argument("--search")

    args = parser.parse_args()

    if args.command == "run":
        interpret_code_from_file(args.file)

    elif args.command == "ros":
        if args.ros_command == "bridge":
            interpret_code_from_file(
                "ros_stub.mars",
                ros_autostart=True
            )

        elif args.ros_command == "topics":
            if args.show:
                ros_tools.show_topic(args.show)
            elif args.search:
                ros_tools.search_topics(args.search)
            else:
                ros_tools.list_topics()