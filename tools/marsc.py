#!/usr/bin/env python3

#This file is what is used to translate our .mars file into a .cpp file that can be compiled and then executed.
#In order to run this type: python marsc.py ./examples/pickplace.mars
#Currently seperated from the rest of the project so it does not currently fully work. Just conceptual practice. (Was intended for converting previous version of project as well)
import sys
import re
from pathlib import Path


if len(sys.argv) < 2:
    print("Usage: python tools/marsc.py examples/pickplace.mars")
    sys.exit(1)

src = Path(sys.argv[1]).read_text().splitlines()
out = []
out.append('#include "robot_arm.h"')
out.append('#include <iostream>')
out.append('int main() {')
varname = "arm"

for line in src:
    line = line.strip()
    if not line or line.startswith('//'):
        continue
    # import "robot_arm" -> handled by include already
    if line.startswith("config "):
        # config "configs/robot_config_ur5.json"
        m = re.match(r'config\s+"([^"]+)"', line)
        if m:
            cfg = m.group(1)
            out.append(f'    RobotArm {varname} = RobotArm::fromConfig("{cfg}");')
    elif line == "home":
        out.append(f'    {varname}.home();')
    elif line.startswith("pick "):
        # pick 0.4 0.0 0.2
        parts = line.split()
        x,y,z = parts[1], parts[2], parts[3]
        out.append(f'    Pose pick{{{x},{y},{z},0,0,0}};')
        out.append(f'    {varname}.pick(pick);')
    elif line.startswith("place "):
        parts = line.split()
        x,y,z = parts[1], parts[2], parts[3]
        out.append(f'    Pose place{{{x},{y},{z},0,0,0}};')
        out.append(f'    {varname}.place(place);')
    else:
        out.append(f'    // unsupported: {line}')

out.append('    return 0;')
out.append('}')
out_path = Path("src/mars_generated.cpp")
out_path.write_text("\n".join(out))
print("Generated", out_path)
