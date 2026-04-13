import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from typing import List, Optional


def format_list(items: List[str]) -> str:
    if not items:
        return "<FONT POINT-SIZE=\"8\">&nbsp;</FONT>"
    return "<BR ALIGN=\"LEFT\"/>".join([f"+ {item}" for item in items])


def node_label(
    title: str,
    subcomponents: List[str],
    parameters: List[str],
    functions: List[str],
    width_points: Optional[int],
) -> str:
    width_attr = f' WIDTH="{width_points}"' if width_points else ""
    return (
        "<"
        "<FONT FACE=\"Helvetica Neue, Helvetica, Arial\">"
        "<TABLE BORDER=\"1\" CELLBORDER=\"1\" CELLSPACING=\"0\" CELLPADDING=\"4\">"
        f"<TR><TD{width_attr} BGCOLOR=\"#9fafb7\" ALIGN=\"CENTER\"><B><FONT POINT-SIZE=\"15\">{title}</FONT></B></TD></TR>"
        f"<TR><TD{width_attr} ALIGN=\"LEFT\" BGCOLOR=\"#FFFFFF\"><B>Subcomponents</B><BR ALIGN=\"LEFT\"/>{format_list(subcomponents)}</TD></TR>"
        f"<TR><TD{width_attr} ALIGN=\"LEFT\" BGCOLOR=\"#FFFFFF\"><B>Parameters</B><BR ALIGN=\"LEFT\"/>{format_list(parameters)}</TD></TR>"
        f"<TR><TD{width_attr} ALIGN=\"LEFT\" BGCOLOR=\"#FFFFFF\"><B>Functions</B><BR ALIGN=\"LEFT\"/>{format_list(functions)}</TD></TR>"
        "</TABLE>"
        "</FONT>"
        ">"
    )


def build_dot(width_points: Optional[int]) -> str:
    nodes = {
        "IMU": node_label(
            "IMU",
            subcomponents=[],
            parameters=["bool accelerometer", "bool gyro", "bool magnetometer"],
            functions=[
                "void init()",
                "float[] getAcceleration()",
                "float[] getAngularVelocity()",
                "float[] getMagneticField()",
            ],
            width_points=width_points,
        ),
        "MPU6050": node_label(
            "MPU6050",
            subcomponents=[],
            parameters=["bool accelerometer = true", "bool gyro = true", "bool magnetometer = false"],
            functions=[
                "void init()",
                "float[] getAcceleration()",
                "float[] getAngularVelocity()",
                "@Override float[] getMagneticField()",
            ],
            width_points=width_points,
        ),
    }

    lines = [
        "digraph Inheritance {",
        "  bgcolor=\"transparent\";",
        "  rankdir=TB;",
        "  nodesep=0.35;",
        "  ranksep=0.5;",
        "  node [shape=plaintext fontname=\"Helvetica Neue\"];",
        "  edge [arrowhead=normal];",
        "",
    ]

    for name, label in nodes.items():
        lines.append(f"  {name} [label={label}];")

    lines.extend(
        [
            "",
            "  IMU -> MPU6050;",
            "",
            "}",
        ]
    )

    return "\n".join(lines)


def estimate_mpu_width_points() -> int:
    lines = [
        "MPU6050",
        "Subcomponents",
        "Parameters",
        "Functions",
        "+ bool accelerometer = true",
        "+ bool gyro = true",
        "+ bool magnetometer = false",
        "+ @Override float[] getMagneticField()",
    ]
    max_chars = max(len(line) for line in lines)
    approx_char_width = 7  # points, tuned for default Helvetica size
    padding = 8  # 4 left + 4 right
    return max(1, int(max_chars * approx_char_width + padding))


def measure_mpu_width_points(dot_exe: str) -> Optional[int]:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dot", mode="w", encoding="utf-8") as tmp:
            tmp.write(build_dot(width_points=None))
            tmp_path = tmp.name
        output = subprocess.check_output([dot_exe, "-Tplain", tmp_path], text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            if line.startswith("node MPU6050 "):
                parts = shlex.split(line)
                if len(parts) >= 6:
                    width_in = float(parts[4])
                    return max(1, int(round(width_in * 72)))
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return None


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def render_svg(dot_path: str, svg_path: str) -> bool:
    dot_exe = shutil.which("dot")
    if not dot_exe:
        return False
    subprocess.run([dot_exe, "-Tsvg", dot_path, "-o", svg_path], check=False)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate inheritance diagram (Graphviz DOT + optional SVG).")
    parser.add_argument(
        "--out-prefix",
        default="inheritance_diagram",
        help="Output file prefix (default: inheritance_diagram)",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Output directory (default: current directory)",
    )
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    dot_path = os.path.join(out_dir, f"{args.out_prefix}.dot")
    svg_path = os.path.join(out_dir, f"{args.out_prefix}.svg")

    width_points = None
    dot_exe = shutil.which("dot")
    if dot_exe:
        width_points = measure_mpu_width_points(dot_exe)
    if width_points is None:
        width_points = estimate_mpu_width_points()

    dot = build_dot(width_points=width_points)
    write_file(dot_path, dot)

    rendered = render_svg(dot_path, svg_path)
    if rendered:
        print(f"Wrote {dot_path} and {svg_path}")
    else:
        print(f"Wrote {dot_path} (SVG not rendered; Graphviz 'dot' not found in PATH)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
