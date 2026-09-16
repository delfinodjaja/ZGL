from Tools.basic import (readDirectory,
                         readFile, writeFile,
                         deleteFile, createDirectory,
                         deleteDirectory)
from pathlib import Path
import Tools

def setWorkingDirectory(path):
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    Tools.basic.working_directory = resolved

TOOL_REGISTRY = {
    "readDirectory": readDirectory,
    "readFile": readFile,
    "writeFile": writeFile,
    "deleteFile": deleteFile,
    "createDirectory": createDirectory,
    "deleteDirectory": deleteDirectory,
}