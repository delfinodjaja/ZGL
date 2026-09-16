import os
import shutil
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