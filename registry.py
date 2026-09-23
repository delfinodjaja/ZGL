from Tools.basic import (readDirectory,
                         readFile, writeFile,
                         deleteFile, createDirectory,
                         deleteDirectory, replaceInFile, reportPlanComplete,
                         reportStepComplete, insertInFile)
from pathlib import Path
import Tools

def setWorkingDirectory(path):
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    Tools.basic.working_directory = resolved

TOOL_REGISTRY = {
    "listDirectory": readDirectory,
    "readFile": readFile,
    "writeFile": writeFile,
    "insertInFile": insertInFile,
    "replaceInFile": replaceInFile,
    "deleteFile": deleteFile,
    "createDirectory": createDirectory,
    "deleteDirectory": deleteDirectory,
    "reportStepComplete": reportStepComplete,
    "reportPlanComplete": reportPlanComplete
}