import re
import subprocess
import sys


def run_tests(project_folder):
    """Run pytest inside the given folder and report the results."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"],
        cwd=project_folder,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr

    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)
    passed_match = re.search(r"(\d+) passed", output)

    failed = int(failed_match.group(1)) if failed_match else 0
    errors = int(error_match.group(1)) if error_match else 0
    passed = int(passed_match.group(1)) if passed_match else 0

    return {
        "passed": passed,
        "failed": failed + errors,
        "all_green": result.returncode == 0,
        "output": output,
    }

from pathlib import Path


def read_failing_files(project_folder, test_output, max_lines=300, max_files=8):
    """Read files named in the test output, plus the project's other source files."""
    base = Path(project_folder).resolve()
    named = re.findall(r"^([\w./\\-]+\.py):\d+", test_output, flags=re.MULTILINE)

    # Files named in the failure text come first, then every other .py file.
    candidates = list(named)
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(base).as_posix()
        if "__pycache__" not in rel and not rel.startswith("."):
            candidates.append(rel)

    files = {}
    for name in candidates:
        if name in files or len(files) >= max_files:
            continue
        path = (base / name).resolve()
        if path.is_file() and path.is_relative_to(base):
            lines = path.read_text(encoding="utf-8").splitlines()
            files[name] = "\n".join(lines[:max_lines])
    return files

def apply_patch(project_folder, patch):
    """Write the model's new file contents to disk. Returns backups for undoing."""
    base = Path(project_folder).resolve()
    backups = {}
    for item in patch:
        name = item["path"]
        path = (base / name).resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"Refusing to write outside the project: {name}")
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            raise ValueError(f"Refusing to modify a test file: {name}")
        backups[name] = path.read_text(encoding="utf-8") if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["new_content"], encoding="utf-8")
    return backups


def restore(project_folder, backups):
    """Undo a patch using the backups that apply_patch returned."""
    base = Path(project_folder).resolve()
    for name, old_text in backups.items():
        path = (base / name).resolve()
        if old_text is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(old_text, encoding="utf-8")