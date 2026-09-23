import os
import shutil
import difflib
from pathlib import Path

# Global working directory setting
working_directory = None


def _resolve_safe_path(path_str: str) -> Path:
    """
    Internal helper: Resolves any incoming relative/absolute path string
    against working_directory and verifies it does not escape.
    """
    if not working_directory:
        raise ValueError("working_directory is not set.")

    # 1. Join incoming path with working_directory
    target = (working_directory / path_str).resolve()

    # 2. Hard Containment Check (raises ValueError if target is outside working_directory)
    try:
        target.relative_to(working_directory)
    except ValueError:
        raise PermissionError(
            f"Access Denied: Path '{path_str}' escapes working directory '{working_directory}'"
        )

    return target


def readDirectory(path="."):
    try:
        safe_path = _resolve_safe_path(path)
        if not safe_path.is_dir():
            return f"Error: Path '{path}' is not a directory"
        return os.listdir(safe_path)
    except Exception as e:
        return f"Error: {e}"


def readFile(path):
    try:
        safe_path = _resolve_safe_path(path)
        with open(safe_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f"Error: {e}"


def writeFile(path, content, **unexpected):
    if unexpected:
        return (
            f"Error: writeFile received unexpected arguments {list(unexpected.keys())}. "
            "This usually means the JSON content wasn't escaped correctly — "
            "check for unescaped double quotes inside the file content."
        )
    try:
        safe_path = _resolve_safe_path(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as file:
            file.write(content)
        return f"Wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error: {e}"


def deleteFile(path):
    try:
        safe_path = _resolve_safe_path(path)
        if safe_path.is_dir():
            return f"Error: '{path}' is a directory, use deleteDirectory instead"
        os.remove(safe_path)
        return f"Deleted {path}"
    except Exception as e:
        return f"Error: {e}"


def createDirectory(path):
    try:
        safe_path = _resolve_safe_path(path)
        os.makedirs(safe_path, exist_ok=True)
        return f"Created directory {path}"
    except Exception as e:
        return f"Error: {e}"


def deleteDirectory(path):
    try:
        safe_path = _resolve_safe_path(path)
        if safe_path.exists():
            shutil.rmtree(safe_path)
            return f"Deleted directory {path}"
        return f"Directory {path} does not exist"
    except Exception as e:
        return f"Error: {e}"


def insertInFile(path: str, anchor_text: str, new_text: str, position: str = "after") -> str:
    """
    Insert new_text into the file, placed immediately before or after
    anchor_text. anchor_text must match the file's existing content
    exactly (whitespace included) and must be unique in the file.
    Use the SHORTEST unique line you can find as the anchor — e.g.
    'def login(self):' rather than a multi-line block.

    position: "before" or "after" (default "after").

    Use this to add a new function, method, import, or config entry next
    to related existing code. Do NOT use this to change existing content
    — use replaceInFile for that.
    """
    try:
        safe_path = _resolve_safe_path(path)
        if not safe_path.exists():
            return (
                f"Error: File '{path}' does not exist. "
                f"Create it first with writeFile."
            )

        with open(safe_path, "r", encoding="utf-8") as f:
            original = f.read()

        if anchor_text not in original:
            lines = [l.strip() for l in original.splitlines() if l.strip()]
            close = difflib.get_close_matches(anchor_text.strip(), lines, n=3, cutoff=0.6)
            hint = f" Closest existing lines: {close}" if close else ""
            return (
                f"Error: anchor_text not found in '{path}'.{hint} "
                f"Read the file first to confirm the exact text — check whitespace/quotes."
            )

        occurrences = original.count(anchor_text)
        if occurrences > 1:
            return (
                f"Error: anchor_text matched {occurrences} times in '{path}'. "
                f"Include one more line of context to make it unique."
            )

        if position == "before":
            updated = original.replace(anchor_text, new_text + anchor_text, 1)
        else:
            updated = original.replace(anchor_text, anchor_text + new_text, 1)

        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(updated)

        return f"Inserted {len(new_text)} characters {position} anchor in {path}"
    except Exception as e:
        return f"Error inserting in file: {e}"


def replaceInFile(path: str, old_text: str, new_text: str) -> str:
    """
    Replace an exact substring in a file. Use this to change or remove
    existing content. old_text must match the file's current content
    character-for-character, including whitespace.

    If old_text appears multiple times, only the first occurrence is
    replaced. If old_text isn't found, you'll get an error — read the
    file first to confirm the exact text.
    """
    try:
        safe_path = _resolve_safe_path(path)
        if not safe_path.exists():
            return f"Error: File '{path}' does not exist."

        with open(safe_path, "r", encoding="utf-8") as f:
            original = f.read()

        if old_text not in original:
            lines = [l.strip() for l in original.splitlines() if l.strip()]
            close = difflib.get_close_matches(old_text.strip(), lines, n=3, cutoff=0.6)
            hint = f" Closest existing lines: {close}" if close else ""
            return (
                f"Error: old_text not found in '{path}'.{hint} "
                f"The text you're trying to replace doesn't exist in the file. "
                f"Read the file first to confirm the exact text — old_text "
                f"must match character-for-character, including whitespace."
            )

        occurrences = original.count(old_text)
        updated = original.replace(old_text, new_text, 1)

        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(updated)

        msg = f"Replaced 1 occurrence in {path}"
        if occurrences > 1:
            msg += f" (note: old_text appeared {occurrences} times; only the first was replaced)"
        return msg
    except Exception as e:
        return f"Error replacing in file: {e}"


def reportStepComplete(summary: str) -> dict:
    """
    Call this when you have finished the current step. Provide a one-line
    summary of what you changed. This is how you signal completion —
    do not just stop calling tools.
    """
    return {"ok": True, "summary": summary}


def reportPlanComplete(plan: str) -> dict:
    """
    Call this when your plan is ready. Provide the full numbered plan as
    plain text. This is how you signal the plan is done.
    """
    return {"ok": True, "plan": plan}