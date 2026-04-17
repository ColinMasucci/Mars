from pathlib import Path
import shutil
import importlib.resources as resources


def create_workspace(name: str, seed: bool = False):
    base = Path.cwd() / name

    print(f"Creating MARS workspace: {base}")

    # Always create the base structure
    (base / "tools").mkdir(parents=True, exist_ok=True)
    (base / "mars_examples").mkdir(parents=True, exist_ok=True)
    (base / "config").mkdir(parents=True, exist_ok=True)
    (base / "config_examples").mkdir(parents=True, exist_ok=True)
    (base / "src").mkdir(parents=True, exist_ok=True)

    # Optional seeding — copy everything from mars_templates
    if seed:
        print("Populating workspace with templates...")

        with resources.path("mars_templates", "") as template_dir:
            template_dir = Path(template_dir)
            for child in template_dir.iterdir():
                # Skip __init__.py and __pycache__ — those are packaging artifacts
                if child.name.startswith("__"):
                    continue
                dest = base / child.name
                if child.is_dir():
                    shutil.copytree(child, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, dest)

    # Metadata file
    with open(base / "mars_project.json", "w") as f:
        f.write(f"""\
{{
  "name": "{name}",
  "seeded": {str(seed).lower()},
  "type": "mars-workspace"
}}""")

    print("Workspace created successfully.")
