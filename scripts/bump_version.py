"""
Version bump script.

Usage:
    python scripts/bump_version.py patch    # 0.1.0 → 0.1.1
    python scripts/bump_version.py minor    # 0.1.0 → 0.2.0
    python scripts/bump_version.py major    # 0.1.0 → 1.0.0
    python scripts/bump_version.py 0.3.0   # set exact version

After running, commit and tag:
    git add pyproject.toml evalforge/__init__.py CHANGELOG.md
    git commit -m "chore: bump version to v0.2.0"
    git tag v0.2.0
    git push && git push --tags

The publish.yml workflow will then automatically build and push to PyPI.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version = "(.+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def bump(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        # Treat as explicit version
        parts = part.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Invalid version: {part!r}. Use major/minor/patch or X.Y.Z")
        return part


def update_file(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    updated = text.replace(old, new)
    if updated == text:
        print(f"  WARNING: {path.name} — no change made (pattern not found)")
        return
    path.write_text(updated)
    print(f"  Updated {path.name}")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    part = sys.argv[1]
    current = get_current_version()
    new_version = bump(current, part)

    print(f"\nBumping version: {current} → {new_version}\n")

    # pyproject.toml
    update_file(
        ROOT / "pyproject.toml",
        f'version = "{current}"',
        f'version = "{new_version}"',
    )

    # evalforge/__init__.py
    update_file(
        ROOT / "evalforge" / "__init__.py",
        f'__version__ = "{current}"',
        f'__version__ = "{new_version}"',
    )

    print(f"\nDone. Next steps:")
    print(f"  git add pyproject.toml evalforge/__init__.py")
    print(f"  git commit -m 'chore: bump version to v{new_version}'")
    print(f"  git tag v{new_version}")
    print(f"  git push && git push --tags")
    print(f"\nGitHub Actions will publish v{new_version} to PyPI automatically.")


if __name__ == "__main__":
    main()
