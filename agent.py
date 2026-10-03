import difflib
import shutil
import tempfile
from pathlib import Path

from brain import ask_model
from tools import apply_patch, read_failing_files, restore, run_tests


def fake_model(test_output, files, history):
    """A pretend model for testing without a key. Not used in the real demo."""
    if "cart.py" not in files:
        return {
            "diagnosis": "I cannot see the source file.",
            "hypothesis": "",
            "confidence": 0.1,
            "action": "give_up",
            "patch": [],
            "expected_effect": "",
            "give_up_reason": "cart.py was not provided.",
        }
    if not history:
        new_code = "def total(prices, discount):\n    return 0\n"
        hypothesis = "Return zero (a deliberately bad first guess)."
    else:
        new_code = (
            "def total(prices, discount):\n"
            "    subtotal = sum(prices)\n"
            "    return subtotal * (1 - discount)\n"
        )
        hypothesis = "Apply the discount as a fraction of the subtotal."
    return {
        "diagnosis": "The discount is multiplied by 100 instead of applied as a fraction.",
        "hypothesis": hypothesis,
        "confidence": 0.8,
        "action": "patch",
        "patch": [{"path": "cart.py", "new_content": new_code}],
        "expected_effect": "The failing tests should pass.",
        "give_up_reason": "",
    }


def make_diffs(patch, backups):
    """Build a readable before/after diff for each changed file."""
    diffs = {}
    for item in patch:
        name = item["path"]
        old = backups.get(name) or ""
        diffs[name] = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                item["new_content"].splitlines(keepends=True),
                fromfile=f"{name} (before)",
                tofile=f"{name} (after)",
            )
        )
    return diffs


def run_agent(source_folder, model_fn=ask_model, max_attempts=5):
    """Repair a project step by step. Yields one event per step for the UI."""
    workdir = Path(tempfile.mkdtemp(prefix="repo_surgeon_")) / "project"
    shutil.copytree(
        source_folder,
        workdir,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    workdir = str(workdir)

    history = []
    result = run_tests(workdir)
    yield {"type": "start", "result": result}

    for attempt in range(1, max_attempts + 1):
        if result["all_green"]:
            yield {"type": "success", "attempts": attempt - 1, "result": result}
            return

        files = read_failing_files(workdir, result["output"])
        try:
            reply = model_fn(result["output"], files, history)
        except Exception as error:
            yield {"type": "error", "message": str(error)}
            return

        if reply.get("action") == "give_up" or not reply.get("patch"):
            reason = reply.get("give_up_reason") or "The model proposed no fix."
            yield {"type": "gave_up", "reason": reason, "reply": reply}
            return

        try:
            backups = apply_patch(workdir, reply["patch"])
        except (ValueError, KeyError, TypeError, OSError) as error:
            history.append(
                {
                    "attempt": attempt,
                    "hypothesis": reply.get("hypothesis", ""),
                    "problem": f"Patch rejected: {error}",
                }
            )
            yield {"type": "rejected", "attempt": attempt, "reply": reply, "message": str(error)}
            continue

        diffs = make_diffs(reply["patch"], backups)
        new_result = run_tests(workdir)
        failed_before = result["failed"]
        reverted = new_result["failed"] > failed_before
        if reverted:
            restore(workdir, backups)
        else:
            result = new_result

        history.append(
            {
                "attempt": attempt,
                "hypothesis": reply.get("hypothesis", ""),
                "failing_before": failed_before,
                "failing_after": new_result["failed"],
                "reverted": reverted,
            }
        )
        yield {
            "type": "attempt",
            "attempt": attempt,
            "reply": reply,
            "diffs": diffs,
            "failed_before": failed_before,
            "failed_after": new_result["failed"],
            "reverted": reverted,
        }

    if result["all_green"]:
        yield {"type": "success", "attempts": max_attempts, "result": result}
    else:
        yield {"type": "out_of_attempts", "result": result}