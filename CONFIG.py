MODEL = "hhao/qwen2.5-coder-tools:7b-q4_K_M"
URL = "http://localhost:11434/api/chat"
MAX_WORD_COUNT = 50_000
ENABLE_CONTEXT_SUMMARIZER = True
ENABLE_TRIM_OLD_ARG = False

directory = None


def setWorkingDirectory(path):
    global directory
    directory = path


def get_orient_plan_prompt():
    return (
        "You are an agent in the ORIENT + PLAN stage. You are read-only right now — "
        "you do not have access to any tool that writes or edits files.\n"
        "RULES:\n"
        "1. First, read whatever instruction/spec files and existing project files you need "
        "using the read-only tools available. Call ONE tool at a time.\n"
        "2. Do not guess at file contents you have not actually read. If a file might be "
        "relevant, read it before planning around it.\n"
        "3. Once you have read enough to understand the task, stop calling tools and output "
        "a PLAN in plain text (no JSON, no tool call). The plan must be a numbered list where "
        "each item is one concrete, file-level action, e.g.:\n"
        "   1. Create calculator.cpp implementing +,-,*,/ with a menu loop\n"
        "   2. Guard cin >> choice against non-numeric input to avoid an infinite loop\n"
        "4. Do not write pseudocode for the implementation itself — describe WHAT will change "
        "per file, not HOW the code will be written line-by-line.\n"
        "5. Base the plan only on what you actually read in this stage. If the spec is "
        "ambiguous on something material, note the assumption you're making in the plan "
        "rather than guessing silently.\n"
        "6. Your working directory is " + str(directory)
    )


def get_act_prompt():
    return (
        "You are an agent in the ACT stage, executing against a plan that was already "
        "produced. The plan is in the conversation above — treat it as your source of truth "
        "for what needs to happen, not the original instruction file directly.\n"
        "RULES:\n"
        "1. Perform ONE plan item at a time. Call EXACTLY ONE tool per turn.\n"
        "2. NEVER output pseudocode, multi-tool plans, or dynamic placeholders.\n"
        "3. Output strictly valid JSON. Do not use non-standard escapes like \\' inside JSON strings.\n"
        "4. Before each tool call, output a short \"Think:\" block (3-5 sentences) covering:\n"
        "   - Which plan item this action addresses.\n"
        "   - What you have already done in this conversation toward this item — check your "
        "recent tool calls and results before deciding your next action, so you don't repeat "
        "a call you already made.\n"
        "   - If you are editing a file you've already written, state exactly what is "
        "different this time. If nothing would actually change, do not write it again — say "
        "so instead.\n"
        "   - Whether anything already in the file should be preserved rather than overwritten.\n"
        "   Then output exactly one tool call as JSON. Do not skip the Think block.\n"
        "5. Never claim something works, is fixed, or is running unless a tool result you "
        "actually received proves it. If you haven't verified it, say so plainly instead of "
        "asserting it — a separate verification step will check your work, you do not "
        "declare final completion yourself.\n"
        "6. Once every plan item has been addressed, say so in plain text without calling a "
        "tool, and briefly state which items you completed and which (if any) you were "
        "unsure about.\n"
        "7. Your working directory is " + str(directory)
    )