TOOL_LIST = [
    {
        "type": "function",
        "function": {
            "name": "listDirectory",
            "description": "List files and folders inside a given directory path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readFile",
            "description": "Read and return the full text contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "writeFile",
            "description": "Write content to a file, overwriting it completely if it already exists. Use insertInFile or replaceInFile instead for small code edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full text content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insertInFile",
            "description": (
                "Insert new text into a file next to existing content, without "
                "changing what's already there. Use this to add a new function, "
                "method, import, or config entry. anchor_text must match existing "
                "file content exactly (whitespace included) and must be unique — "
                "use the shortest unique line you can, e.g. 'def login(self):' "
                "rather than a multi-line block. Do NOT use this to change or "
                "remove existing content — use replaceInFile for that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file."
                    },
                    "anchor_text": {
                        "type": "string",
                        "description": "Exact existing line to insert next to. Must be unique in the file."
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text to insert."
                    },
                    "position": {
                        "type": "string",
                        "enum": ["before", "after"],
                        "description": "Whether to insert before or after anchor_text. Defaults to 'after'."
                    }
                },
                "required": ["path", "anchor_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replaceInFile",
            "description": (
                "Replace an exact substring in a file. Use this to change or remove "
                "existing content. The old_text must match the file's current content "
                "exactly, including whitespace. If old_text isn't found, read the "
                "file first to see what's actually there."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file."
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact existing text to find."
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The replacement text. Pass an empty string to delete old_text."
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deleteFile",
            "description": "Delete a single file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to delete",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createDirectory",
            "description": "Create a new directory at the given path, including any missing parent folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to create",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteDirectory",
            "description": "Delete a directory and everything inside it, recursively.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to delete",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reportStepComplete",
            "description": (
                "Call this when you have finished the current step. "
                "Provide a one-line summary of what you changed. "
                "This is the ONLY correct way to signal that a step is done — "
                "do not simply stop calling tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "One-line summary of what was changed in this step."
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reportPlanComplete",
            "description": (
                "Call this when your numbered plan is ready. "
                "Provide the plan as plain text in the 'plan' argument. "
                "This is the ONLY correct way to signal the plan is done."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "string",
                        "description": "The full numbered plan as plain text."
                    }
                },
                "required": ["plan"]
            }
        }
    },
]