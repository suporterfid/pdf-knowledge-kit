#!/usr/bin/env python3
"""Bump version across all project files.

This script updates version numbers in:
- app/__version__.py
- frontend/package.json
- package.json (root)

Usage:
    python tools/bump_version.py patch          # 1.0.0 -> 1.0.1
    python tools/bump_version.py minor          # 1.0.1 -> 1.1.0
    python tools/bump_version.py major          # 1.1.0 -> 2.0.0
    python tools/bump_version.py --set 1.2.3    # Set specific version
    python tools/bump_version.py minor --pre alpha  # 1.0.0 -> 1.1.0-alpha.1
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Tuple


def parse_version(version: str) -> Tuple[int, int, int, str, int]:
    """Parse semantic version string into components.
    
    Returns: (major, minor, patch, prerelease_type, prerelease_num)
    Example: "1.2.3-alpha.4" -> (1, 2, 3, "alpha", 4)
    """
    # Match X.Y.Z or X.Y.Z-prerelease.N
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-([a-z]+)\.(\d+))?$', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    pre_type = match.group(4) or ""
    pre_num = int(match.group(5)) if match.group(5) else 0
    
    return major, minor, patch, pre_type, pre_num


def format_version(major: int, minor: int, patch: int, pre_type: str = "", pre_num: int = 0) -> str:
    """Format version components into string."""
    version = f"{major}.{minor}.{patch}"
    if pre_type:
        version += f"-{pre_type}.{pre_num}"
    return version


def bump_version(current: str, bump_type: str, pre_type: str = "") -> str:
    """Bump version according to bump_type.
    
    Args:
        current: Current version string
        bump_type: One of 'major', 'minor', 'patch'
        pre_type: Prerelease type ('alpha', 'beta', 'rc') or empty
    
    Returns:
        New version string
    """
    major, minor, patch, curr_pre_type, curr_pre_num = parse_version(current)
    
    # If adding or continuing prerelease
    if pre_type:
        # If same prerelease type, increment number
        if curr_pre_type == pre_type:
            return format_version(major, minor, patch, pre_type, curr_pre_num + 1)
        
        # Otherwise, bump version and start prerelease at .1
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
        
        return format_version(major, minor, patch, pre_type, 1)
    
    # Regular version bump (no prerelease)
    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return format_version(major, minor, patch)


def get_current_version(project_root: Path) -> str:
    """Get current version from app/__version__.py."""
    version_file = project_root / "app" / "__version__.py"
    
    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")
    
    content = version_file.read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    
    if not match:
        raise ValueError("Could not find __version__ in __version__.py")
    
    return match.group(1)


def update_python_version(project_root: Path, new_version: str) -> None:
    """Update version in app/__version__.py."""
    version_file = project_root / "app" / "__version__.py"
    content = version_file.read_text()
    
    # Update __version__
    content = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{new_version}"',
        content
    )
    
    # Update __version_info__
    major, minor, patch, _, _ = parse_version(new_version)
    content = re.sub(
        r'__version_info__\s*=\s*tuple\(int\(i\)\s+for\s+i\s+in\s+__version__\.split\("\.".*?\)',
        f'__version_info__ = ({major}, {minor}, {patch})',
        content
    )
    
    version_file.write_text(content)
    print(f"✓ Updated {version_file}")


def update_package_json(package_file: Path, new_version: str) -> None:
    """Update version in package.json file."""
    if not package_file.exists():
        print(f"⚠ Skipping {package_file} (not found)")
        return
    
    data = json.loads(package_file.read_text())
    data["version"] = new_version
    
    package_file.write_text(json.dumps(data, indent=2) + "\n")
    print(f"✓ Updated {package_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Bump version across all project files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s patch              # Bump patch version (1.0.0 -> 1.0.1)
  %(prog)s minor              # Bump minor version (1.0.1 -> 1.1.0)
  %(prog)s major              # Bump major version (1.1.0 -> 2.0.0)
  %(prog)s --set 1.2.3        # Set specific version
  %(prog)s minor --pre alpha  # Create prerelease (1.0.0 -> 1.1.0-alpha.1)
  %(prog)s patch --pre alpha  # Increment prerelease (1.1.0-alpha.1 -> 1.1.0-alpha.2)
        """
    )
    
    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Type of version bump"
    )
    parser.add_argument(
        "--set",
        metavar="VERSION",
        help="Set specific version (e.g., 1.2.3 or 1.2.3-alpha.1)"
    )
    parser.add_argument(
        "--pre",
        metavar="TYPE",
        choices=["alpha", "beta", "rc"],
        help="Create or increment prerelease version"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.set and args.bump_type:
        parser.error("Cannot use both --set and bump_type")
    
    if not args.set and not args.bump_type:
        parser.error("Must specify either --set or bump_type")
    
    # Find project root
    project_root = Path(__file__).parent.parent
    
    try:
        # Get current version
        current_version = get_current_version(project_root)
        print(f"Current version: {current_version}")
        
        # Calculate new version
        if args.set:
            # Validate format
            parse_version(args.set)
            new_version = args.set
        else:
            new_version = bump_version(current_version, args.bump_type, args.pre or "")
        
        print(f"New version: {new_version}")
        
        if args.dry_run:
            print("\n[DRY RUN] Would update the following files:")
            print(f"  - {project_root / 'app' / '__version__.py'}")
            print(f"  - {project_root / 'frontend' / 'package.json'}")
            print(f"  - {project_root / 'package.json'}")
            return 0
        
        # Confirm
        response = input("\nProceed with version update? [y/N] ")
        if response.lower() != 'y':
            print("Aborted.")
            return 1
        
        # Update all version files
        print("\nUpdating version files...")
        update_python_version(project_root, new_version)
        update_package_json(project_root / "frontend" / "package.json", new_version)
        update_package_json(project_root / "package.json", new_version)
        
        print(f"\n✅ Version bumped to {new_version}")
        print("\nNext steps:")
        print("  1. Review changes: git diff")
        print("  2. Update CHANGELOG.md with release notes")
        print(f"  3. Commit: git commit -m 'chore: bump version to {new_version}'")
        print(f"  4. Tag: git tag -a v{new_version} -m 'Release version {new_version}'")
        print("  5. Push: git push && git push --tags")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
