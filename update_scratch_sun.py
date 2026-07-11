import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path


OLD_SUN = "0000100001000010000110001011110000111101000110000100001000010000"
NEW_SUN = "0010010000011000010110101011110110111101010110100001100000100100"


def update_project(path):
    source = Path(path).resolve()
    with zipfile.ZipFile(source, "r") as archive:
        project = json.loads(archive.read("project.json").decode("utf-8"))
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        replacements = 0
        for target in project.get("targets", []):
            for block in target.get("blocks", {}).values():
                fields = block.get("fields", {})
                matrix = fields.get("MATRIX8")
                if matrix and matrix[0] == OLD_SUN:
                    matrix[0] = NEW_SUN
                    replacements += 1
        if replacements == 0:
            if NEW_SUN in json.dumps(project, ensure_ascii=False):
                return 0
            raise RuntimeError("The original sun pattern was not found in the Scratch project.")

    handle, temp_name = tempfile.mkstemp(suffix=".sb3", dir=str(source.parent))
    os.close(handle)
    try:
        with zipfile.ZipFile(temp_name, "w", zipfile.ZIP_DEFLATED) as output:
            for info, original_data in entries:
                data = original_data
                if info.filename == "project.json":
                    data = json.dumps(
                        project,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                output.writestr(info, data)
        os.replace(temp_name, source)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return replacements


def main():
    parser = argparse.ArgumentParser(description="Improve the sun icon in a Scratch 3 project")
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    count = update_project(args.project)
    print("Updated {} sun matrix block(s).".format(count))


if __name__ == "__main__":
    main()
