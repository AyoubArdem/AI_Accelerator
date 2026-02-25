#!/usr/bin/env python
import argparse
import glob
import os
import sys
import zipfile


DEFAULT_REQUIRED = [
    "deployment/Dockerfile",
    "deployment/requirements.txt",
    "deployment/fast_api.py",
    "monitoring/Dockerfile",
    "monitoring/requirements.txt",
    "users/templates/users/activation_result.html",
    "users/static/users/logo.png",
]


def _pick_wheel(path_or_glob: str) -> str:
    matches = sorted(glob.glob(path_or_glob))
    wheels = [m for m in matches if m.endswith(".whl")]
    if not wheels:
        raise FileNotFoundError(f"No wheel found for pattern: {path_or_glob}")
    return wheels[-1]


def _contains_member(names: list[str], target: str) -> bool:
    normalized_target = target.replace("\\", "/")
    for name in names:
        if name.replace("\\", "/").endswith(normalized_target):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify required files are included in a wheel.")
    parser.add_argument(
        "--wheel",
        default="dist/*.whl",
        help="Wheel file path or glob pattern (default: dist/*.whl)",
    )
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="Additional required path suffix (can be used multiple times).",
    )
    args = parser.parse_args()

    required = DEFAULT_REQUIRED + args.require

    try:
        wheel_path = _pick_wheel(args.wheel)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    with zipfile.ZipFile(wheel_path, "r") as zf:
        names = zf.namelist()

    missing = [item for item in required if not _contains_member(names, item)]

    print(f"Wheel checked: {os.path.basename(wheel_path)}")
    if not missing:
        print("OK: all required runtime/package files are present.")
        return 0

    print("ERROR: missing required files in wheel:")
    for item in missing:
        print(f"- {item}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

