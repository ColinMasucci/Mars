import argparse
from mars.mars_lang.core.interpreter import interpret_code_from_file
from mars.mars_lang.ros import ros_tools

VERSION = "0.1.0" #grab this version from the actual release once we have multiple on github

def main():
    parser = argparse.ArgumentParser(prog="mars")

    parser.add_argument("--version", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    # run command
    run = sub.add_parser("run")
    run.add_argument("file")

    # ros command
    ros = sub.add_parser("ros")
    ros_sub = ros.add_subparsers(dest="ros_command", required=True)

    ros_sub.add_parser("bridge")

    ros_topics = ros_sub.add_parser("topics")
    ros_topics.add_argument("--show")
    ros_topics.add_argument("--search")

    # parse
    args = parser.parse_args()

    # version override (before command execution)
    if args.version:
        print(f"mars {VERSION}")
        return

    # dispatch
    if args.command == "run":
        interpret_code_from_file(args.file)

    elif args.command == "ros":
        if args.ros_command == "bridge":
            interpret_code_from_file("ros_stub.mars", ros_autostart=True)

        elif args.ros_command == "topics":
            if args.show:
                ros_tools.show_topic(args.show)
            elif args.search:
                ros_tools.search_topics(args.search)
            else:
                ros_tools.list_topics()