# Overview

## What MARS Is
- A small, typed language for robotics code plus a component configuration system.
- Designed to model and abstract robot hardware composition in `.marsc` files and run logic in `.mars` programs.
- Executes on a bytecode-interpreted VM with unit-aware numeric types and a small standard library.

## High-Level Architecture
- Language surface: `.mars` files with functions, control flow, classes, arrays/dicts, and units.
- Component configuration: `.marsc` files describe components, inheritance, parameters, and subcomponents.
- Execution runs on an internal VM; compiler details are intentionally kept out of the main documentation.
- Optional tooling: component graph visualizers (Graphviz).

## Hello World
Example:
```mars
print("hello, mars");
```

Run from the repo root:
```powershell
python mars_compiler\main.py
```

`main.py` executes `mars_compiler/test_file.mars` by default. To run another file, import and call the interpreter from Python:
```powershell
python - <<'PY'
from mars_compiler.interpreter import interpret_code_from_file
interpret_code_from_file("path/to/your_file.mars", debug=False)
PY
```
