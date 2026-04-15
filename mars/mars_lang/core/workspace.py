from pathlib import Path
import shutil
import importlib.resources as resources

def create_workspace(name: str, seed: bool = False):
    base = Path.cwd() / name

    print(f"Creating MARS workspace: {base}")

    # Always create structure
    (base / "mars_tools").mkdir(parents=True, exist_ok=True)
    (base / "mars_examples").mkdir(parents=True, exist_ok=True)
    (base / "mars_configs").mkdir(parents=True, exist_ok=True)

    # Optional seeding
    if seed:
        print("Populating workspace with templates...")

        with resources.path("mars.mars_lang.mars_templates", "") as template_dir:
            shutil.copytree(template_dir / "mars_tools", base / "mars_tools", dirs_exist_ok=True)
            shutil.copytree(template_dir / "mars_examples", base / "mars_examples", dirs_exist_ok=True)
            shutil.copytree(template_dir / "mars_configs", base / "mars_configs", dirs_exist_ok=True)

    # Metadata file
    with open(base / "mars_project.json", "w") as f:
        f.write(f"""{{
  "name": "{name}",
  "seeded": {str(seed).lower()},
  "type": "mars-workspace"
}}""")

    print("Workspace created successfully.")