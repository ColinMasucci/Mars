import argparse
from mars.mars_lang.core.interpreter import interpret_code_from_file
from mars.mars_lang.ros import ros_tools
from mars.mars_lang.core.workspace import create_workspace
from pathlib import Path

VERSION = "0.1.0" #grab this version from the actual release once we have multiple on github

def main():
    parser = argparse.ArgumentParser(prog="mars")

    parser.add_argument("--version", action="version", version=f"mars {VERSION}")

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
    ros_topics.add_argument("--cached", action="store_true")
    ros_topics.add_argument("--refresh", action="store_true")

    #init command
    init = sub.add_parser("init")
    init.add_argument("name")
    init.add_argument("--seed", action="store_true", help="Populate workspace with default templates")
    

    # parse
    args = parser.parse_args()

    # dispatch
    if args.command == "run":
        file_path = Path(args.file)

        workspace_root = find_workspace_root(file_path)
        if not workspace_root:
            raise FileNotFoundError(
                "No MARS workspace found (missing mars_project.json)"
            )

        config_dir = find_workspace_config(file_path)

        if not config_dir:
            raise FileNotFoundError(
                "No MARS configs found ('config' directory was removed from workspace)"
            )

        interpret_code_from_file(
            str(file_path),
            workspace_root=workspace_root,
            config_dir=str(config_dir),
        )

    elif args.command == "ros":

        workspace_root = find_workspace_root(Path.cwd())

        if not workspace_root:
            raise FileNotFoundError("No MARS workspace found")

        if args.ros_command == "bridge":
            interpret_code_from_file("ros_stub.mars", ros_autostart=True)

        elif args.ros_command == "topics":
            if not args.cached or args.refresh:
                ros_tools.fetch_topics_live(workspace_root=workspace_root)

            if args.show:
                ros_tools.show_topic(workspace_root=workspace_root, topic_name=args.show)
            elif args.search:
                ros_tools.search_topics(workspace_root=workspace_root, keyword=args.search)
            else:
                ros_tools.list_topics(workspace_root=workspace_root)

    if args.command == "init":
        create_workspace(args.name, args.seed)
        return



def find_workspace_config(start_path: Path):
    # walk upward until mars_project.json is found
    for parent in [start_path] + list(start_path.parents):
        if (parent / "mars_project.json").exists():
            return parent / "config"
    return None

def find_workspace_root(start_path: Path):
    # walk upward until mars_project.json is found
    for parent in [start_path] + list(start_path.parents):
        if (parent / "mars_project.json").exists():
            return parent
    return None