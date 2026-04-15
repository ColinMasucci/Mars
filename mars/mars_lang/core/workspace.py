from pathlib import Path

def create_workspace(name: str):
    base_path = Path.cwd() / name

    print(f"Creating MARS workspace: {base_path}")

    # Create directories
    (base_path / "mars_tools").mkdir(parents=True, exist_ok=True)
    (base_path / "mars_examples").mkdir(parents=True, exist_ok=True)
    (base_path / "mars_configs").mkdir(parents=True, exist_ok=True)

    # Write project metadata
    with open(base_path / "mars_project.json", "w") as f:
        f.write("""{
  "name": "%s",
  "version": "0.1.0",
  "type": "mars-workspace"
}""" % name)

    print("Workspace created successfully.")