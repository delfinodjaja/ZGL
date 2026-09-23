import json
import os
import re

import requests

from CONFIG import (
    MODEL, PLAN_MODEL, URL,
    ENABLE_CONTEXT_SUMMARIZER, MAX_WORD_COUNT, ENABLE_TRIM_OLD_ARG,
    get_act_prompt, get_orient_plan_prompt,
    setWorkingDirectory as set_config_dir,
)
from Tools.toolList import TOOL_LIST
from registry import TOOL_REGISTRY, setWorkingDirectory as set_registry_dir
from FallbackParser import extract_fallback_tool_call
from contextSummarizer import estimate_word_count, summarize_context


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

NUM_CTX = 8000
PLAN_NUM_CTX = 8000
ACT_MAX_STEPS = 20
PLAN_MAX_STEPS = 8
TRIM_KEEP_LAST = 2
MAX_FORCED_RESEARCH = 3

SMALL_WRITE_NOTE = 200
SHRINK_REJECT_RATIO = 0.5

NUDGE_AFTER_CALLS = 8
MAX_ERROR_RETRIES = 2       # how many times we'll say "last call errored, retry" before giving up

READ_DEDUP_MIN_LEN = 200

PLAN_ALLOWED_TOOLS = ("readFile", "listDirectory")
MUTATING_TOOLS = {"writeFile", "appendToFile", "replaceInFile", "createDirectory", "deleteFile"}


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

ERROR_MARKERS = (
    "error", "traceback", "exception",
    "no such file", "not found", "permission denied",
    "failed", "errno",
)

MISSING_FILE_MARKERS = (
    "no such file", "does not exist", "not found",
    "is not a directory", "cannot find",
)


def looks_like_valid_plan(text):
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^\d+[\.\)]\s+\S', line) and len(line.split()) >= 3:
            return True
    return False


def plan_starts_with_reading(text):
    for line in text.splitlines():
        m = re.match(r'^\s*1[\.\)]\s+(.*)', line)
        if m:
            first = m.group(1).lower().strip()
            return (
                "readfile" in first
                or first.startswith("read ")
                or first.startswith("open ")
                or "read the instruction" in first
                or "read the file" in first
            )
    return False


def is_error_result(result):
    if isinstance(result, dict):
        if result.get("ok") is False:
            return True
        return bool(result.get("error"))
    if isinstance(result, str):
        lowered = result.strip().lower()
        return any(m in lowered[:200] for m in ERROR_MARKERS)
    return False


def is_missing_file_error(result):
    if not isinstance(result, str):
        return False
    lowered = result.lower()
    return any(m in lowered for m in MISSING_FILE_MARKERS)


def is_meaningful_write(tool_args):
    content = tool_args.get("content") if isinstance(tool_args, dict) else None
    return isinstance(content, str) and content.strip() != ""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def parse_tool_args(tool_args):
    if isinstance(tool_args, str):
        try:
            return json.loads(tool_args)
        except json.JSONDecodeError:
            return {}
    return tool_args if isinstance(tool_args, dict) else {}


def trim_old_tool_args(messages, keep_last=TRIM_KEEP_LAST):
    tool_msg_count = sum(1 for m in messages if m.get("role") == "tool")
    seen = 0
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for call in m["tool_calls"]:
                args = call["function"].get("arguments")
                if isinstance(args, dict) and args.get("content") not in (None, "[trimmed]"):
                    seen += 1
                    if seen <= tool_msg_count - keep_last:
                        note = m.get("content") or "(no note provided)"
                        args["content"] = f"[trimmed — see note: {note}]"
    return messages

def trim_old_tool_results(messages, keep_last_results=3):
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    cutoff = len(tool_indices) - keep_last_results
    for rank, i in enumerate(tool_indices):
        if rank < cutoff:
            m = messages[i]
            if len(m["content"]) > 300:
                m["content"] = (
                    f"[trimmed — was {len(m['content'])} chars from "
                    f"{m.get('name')}; re-call the tool if you need this again]"
                )
    return messages

def append_tool_result(messages, call, tool_name, content):
    messages.append({
        "role": "tool",
        "name": tool_name,
        "content": str(content),
        "tool_call_id": call.get("id"),
    })


def extract_top_level_steps(plan_text):
    steps, current, base_indent = [], [], None
    for line in plan_text.splitlines():
        match = re.match(r'^(\s*)(\d+)[\.\)]\s+\S', line)
        if match:
            indent = len(match.group(1))
            if base_indent is None:
                base_indent = indent
            if indent <= base_indent:
                if current:
                    steps.append("\n".join(current).rstrip())
                current = [line.strip()]
                continue
        if current:
            current.append(line)
    if current:
        steps.append("\n".join(current).rstrip())
    return [s for s in steps if s.strip()]


def _short(args, maxlen=120):
    s = json.dumps(args) if isinstance(args, dict) else str(args)
    return s if len(s) <= maxlen else s[:maxlen] + "..."


def _safe_filesize(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _suggest_alternate_path(bad_path, working_dir):
    if not working_dir or not bad_path:
        return None
    target_name = os.path.basename(bad_path).lower()
    if not target_name:
        return None
    try:
        for root, _dirs, files in os.walk(working_dir):
            for fname in files:
                if fname.lower() == target_name:
                    return os.path.join(root, fname)
    except OSError:
        return None
    return None


def _enrich_error(result, path, working_dir):
    if not is_missing_file_error(result) or not path or not working_dir:
        return result
    alt = _suggest_alternate_path(path, working_dir)
    if not alt:
        return result
    return (
        f"{result}\n"
        f"Note: a file with the same name exists at '{alt}'. "
        f"If you meant that one, use the full path."
    )


# ---------------------------------------------------------------------------
# Model I/O
# ---------------------------------------------------------------------------

def call_model(messages, model, num_ctx=NUM_CTX):
    if ENABLE_TRIM_OLD_ARG:
        trim_old_tool_args(messages)
        trim_old_tool_results(messages)

    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_LIST,
        "options": {
            "repeat_penalty": 1.1,
            "num_ctx": num_ctx,
            "temperature": 0.2,
        },
        "stream": False,
    }
    response = requests.post(URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]

# ---------------------------------------------------------------------------
# Plan stage
# ---------------------------------------------------------------------------

def plan(messages, max_steps=PLAN_MAX_STEPS, directory=None):
    listing = TOOL_REGISTRY["listDirectory"](path=directory)
    messages.append({
        "role": "user",
        "content": f"Files in the working directory: {listing}",
    })

    research_calls = 0
    forced_research_attempts = 0

    for step in range(max_steps):
        message = call_model(messages, PLAN_MODEL, num_ctx=PLAN_NUM_CTX)
        tool_calls = message.get("tool_calls")
        content = message.get("content", "") or ""

        if not tool_calls and content:
            fallback_calls = extract_fallback_tool_call(content)
            if fallback_calls:
                tool_calls = fallback_calls
                message = {"role": "assistant", "content": content, "tool_calls": tool_calls}

        messages.append(message)

        if not tool_calls:
            if looks_like_valid_plan(content):
                if research_calls == 0 or plan_starts_with_reading(content):
                    forced_research_attempts += 1
                    if forced_research_attempts > MAX_FORCED_RESEARCH:
                        print("\n[Plan rejected repeatedly without research — giving up]")
                        return None
                    print(f"\n[Rejected] Plan lacks grounding — forcing research "
                          f"({forced_research_attempts}/{MAX_FORCED_RESEARCH})")
                    messages.append({
                        "role": "user",
                        "content": (
                            "You MUST use the readFile tool BEFORE producing a plan.\n"
                            "1. Call readFile on the instruction file and any source "
                            "files it references.\n"
                            "2. THEN call reportPlanComplete with your numbered plan.\n"
                            "Do not include 'read the file' as a plan step."
                        ),
                    })
                    continue
                print(f"\n[Plan produced via text] (research_calls={research_calls})\n{content}")
                return content

            print("\n[Rejected] Not a valid plan — forcing retry.")
            messages.append({
                "role": "user",
                "content": (
                    "Call reportPlanComplete with your numbered plan. "
                    "No code blocks, no other tool calls."
                ),
            })
            continue

        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = parse_tool_args(call["function"]["arguments"])
            path = tool_args.get("path") if isinstance(tool_args, dict) else None

            if tool_name == "reportPlanComplete":
                plan_text = tool_args.get("plan", "") or ""
                if not looks_like_valid_plan(plan_text):
                    print("\n[Rejected] reportPlanComplete called with invalid plan — retry.")
                    append_tool_result(messages, call, tool_name,
                        "That isn't a valid numbered plan. Call reportPlanComplete "
                        "again with a real numbered plan in the 'plan' argument.")
                    continue
                if research_calls == 0 or plan_starts_with_reading(plan_text):
                    forced_research_attempts += 1
                    if forced_research_attempts > MAX_FORCED_RESEARCH:
                        print("\n[Plan rejected repeatedly without research — giving up]")
                        return None
                    print(f"\n[Rejected] Plan lacks grounding — forcing research "
                          f"({forced_research_attempts}/{MAX_FORCED_RESEARCH})")
                    append_tool_result(messages, call, tool_name,
                        "Your plan isn't grounded in the actual files. Use readFile "
                        "FIRST, then call reportPlanComplete again.")
                    continue
                print(f"\n[Plan complete] (research_calls={research_calls})\n{plan_text}")
                return plan_text

            if tool_name not in PLAN_ALLOWED_TOOLS:
                result = f"Error: '{tool_name}' isn't available in the PLAN stage."
            elif tool_name not in TOOL_REGISTRY:
                result = f"Error: unknown tool '{tool_name}'"
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
                    if tool_name == "readFile" and not is_error_result(result):
                        research_calls += 1
                        print(f"  [research: readFile succeeded — research_calls={research_calls}]")
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"

            result = _enrich_error(result, path, directory)

            print(f"[Plan step {step + 1}] {tool_name}({_short(tool_args)}) -> {str(result)[:120]}")
            append_tool_result(messages, call, tool_name, result)

    print("\n[Plan stage: max steps reached]")
    return None


# ---------------------------------------------------------------------------
# Act stage
# ---------------------------------------------------------------------------

def act_loop(messages, max_steps=ACT_MAX_STEPS, working_dir=None):
    """
    Returns (summary, files_touched) on success via reportStepComplete,
    or (None, files_touched) on failure.
    """
    last_result_was_error = False
    files_touched = set()
    nudges = 0
    calls_since_report = 0
    error_retries = 0
    file_versions = {}
    read_cache = {}   # path -> last content returned for this path this step

    for step in range(max_steps):
        message = call_model(messages, MODEL, num_ctx=NUM_CTX)
        tool_calls = message.get("tool_calls")
        content = message.get("content", "") or ""

        if not tool_calls and content:
            fallback_calls = extract_fallback_tool_call(content)
            if fallback_calls:
                tool_calls = fallback_calls
                message = {"role": "assistant", "content": content, "tool_calls": fallback_calls}

        messages.append(message)

        if not tool_calls:
            if files_touched and nudges >= 2:
                print(f"\n[Accepted text answer after {nudges} nudges]\n{content}")
                return content, files_touched

            if last_result_was_error:
                error_retries += 1
                if error_retries > MAX_ERROR_RETRIES:
                    print(f"\n[Giving up after {error_retries} error-retry attempts]")
                    return None, files_touched
                # Reset so we don't loop on this branch forever
                last_result_was_error = False
                print(f"\n[Rejected] Last tool call errored — forcing retry "
                      f"({error_retries}/{MAX_ERROR_RETRIES}).")
                messages.append({
                    "role": "user",
                    "content": (
                        "Your last tool call returned an error. Read the error "
                        "message carefully and try a different approach, or call "
                        "reportStepComplete if the step is actually done. "
                        "Do not repeat the same call — the error message tells "
                        "you what was wrong."
                    ),
                })
                continue

            nudges += 1
            print(f"\n[Nudge {nudges}] Model stopped without calling reportStepComplete.")
            messages.append({
                "role": "user",
                "content": (
                    "You stopped calling tools but did not call reportStepComplete. "
                    "If this step is complete, call reportStepComplete with a "
                    "one-line summary of what you changed. Otherwise, take the "
                    "next concrete action with a tool."
                ),
            })
            continue

        last_result_was_error = False

        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = parse_tool_args(call["function"]["arguments"])
            path = tool_args.get("path") if isinstance(tool_args, dict) else None

            # reportStepComplete is the only success terminal
            if tool_name == "reportStepComplete":
                summary = tool_args.get("summary", "") or "(no summary provided)"
                print(f"\n[Step complete] {summary}")
                return summary, files_touched

            print(f"\n[Act step {step + 1}] {tool_name}({_short(tool_args)})")
            calls_since_report += 1

            # --- writeFile shrink rejection ---
            if tool_name == "writeFile" and path and is_meaningful_write(tool_args):
                old_size = _safe_filesize(path)
                new_size = len(tool_args.get("content", "") or "")
                if old_size > 200 and new_size < old_size * SHRINK_REJECT_RATIO:
                    print(f"  [writeFile rejected — {old_size} → {new_size} bytes]")
                    append_tool_result(messages, call, tool_name, (
                        f"Error: writeFile would replace a {old_size}-byte file with "
                        f"only {new_size} bytes — a substantial loss of content. "
                        f"If you meant to add to the file, use appendToFile. "
                        f"If you meant to change existing content, use replaceInFile. "
                        f"If you truly intend to replace the whole file, call writeFile "
                        f"again with the full new content."
                    ))
                    continue

            call_succeeded = False
            if tool_name not in TOOL_REGISTRY:
                result = f"Error: unknown tool '{tool_name}'"
                last_result_was_error = True
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
                    print(f"  -> {str(result)[:200]}")
                    if is_error_result(result):
                        last_result_was_error = True
                        result = _enrich_error(result, path, working_dir)
                        # On error, invalidate the read cache for this path so the
                        # model can see the real file content on its next read.
                        if path:
                            read_cache.pop(path, None)
                    else:
                        call_succeeded = True

                        # --- Read dedup ---
                        if tool_name == "readFile" and path:
                            content_str = str(result)
                            if (len(content_str) >= READ_DEDUP_MIN_LEN
                                    and read_cache.get(path) == content_str):
                                print(f"  [readFile returned identical content "
                                      f"— replacing with note]")
                                result = (
                                    f"[unchanged — you already read '{path}' "
                                    f"earlier in this step and it hasn't been "
                                    f"modified since. You have its content. "
                                    f"Use appendToFile or replaceInFile to make "
                                    f"a change, or call reportStepComplete if "
                                    f"the step is done.]"
                                )
                            else:
                                read_cache[path] = content_str

                        if tool_name == "writeFile" and path:
                            content_len = len(tool_args.get("content", ""))
                            if content_len < SMALL_WRITE_NOTE:
                                print(f"  [note: {content_len} chars written]")
                            file_versions[path] = file_versions.get(path, 0) + 1
                            files_touched.add(path)
                        elif tool_name in MUTATING_TOOLS:
                            if path:
                                file_versions[path] = file_versions.get(path, 0) + 1
                                files_touched.add(path)
                except Exception as e:
                    result = f"Error executing {tool_name}: {e}"
                    print(f"  -> ERROR: {e}")
                    last_result_was_error = True
                    if path:
                        read_cache.pop(path, None)

            append_tool_result(messages, call, tool_name, result)

        if calls_since_report >= NUDGE_AFTER_CALLS:
            print(f"\n[Nudge] {calls_since_report} tool calls without reportStepComplete.")
            messages.append({
                "role": "user",
                "content": (
                    f"You've made {calls_since_report} tool calls on this step "
                    f"without calling reportStepComplete. Either:\n"
                    f"  1. Call reportStepComplete now if the step is done, or\n"
                    f"  2. State in plain text what specifically is blocking you "
                    f"from completing it.\n"
                    f"Do not keep reading files that haven't changed."
                ),
            })
            calls_since_report = 0

    print("\n[Stopped: max act steps reached without reportStepComplete]")
    return None, files_touched


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _snapshot_directory(directory):
    try:
        return TOOL_REGISTRY["listDirectory"](path=directory)
    except Exception as e:
        return f"(could not list directory: {e})"


def _format_completed(completed):
    if not completed:
        return None
    lines = []
    for item in completed:
        files = sorted(item.get("files") or [])
        files_str = ", ".join(files) if files else "(no files touched)"
        lines.append(f"  ✓ {item['header'][:100]}  →  {files_str}")
    return "\n".join(lines)


def run_agent():
    directory = input("Enter a directory to run: ")
    set_registry_dir(directory)
    set_config_dir(directory)

    history = []

    while True:
        user_prompt = input("> ")
        history.append({"role": "user", "content": user_prompt})

        plan_messages = [{"role": "system", "content": get_orient_plan_prompt()}] + history
        plan_result = plan(plan_messages, directory=directory)

        if plan_result is None:
            print("\n[Planning failed to converge — aborting this request]")
            continue

        history.append({
            "role": "assistant",
            "content": f"Plan:\n{plan_result}",
            "message_type": "plan",
        })

        steps = extract_top_level_steps(plan_result)
        if not steps:
            print("\n[No executable steps found in plan]")
            continue

        print(f"\n{'='*70}\nExecuting {len(steps)} top-level steps\n{'='*70}")

        completed = []
        failed_at = None

        for i, step in enumerate(steps, 1):
            header = step.splitlines()[0].strip()
            print(f"\n{'-'*70}\n[Step {i}/{len(steps)}] {header}\n{'-'*70}")

            listing = _snapshot_directory(directory)

            act_messages = [
                {"role": "system", "content": get_act_prompt()},
                {"role": "user", "content": f"Overall task: {user_prompt}"},
                {"role": "user", "content": f"Current directory contents:\n{listing}"},
            ]
            completed_block = _format_completed(completed)
            if completed_block:
                act_messages.append({
                    "role": "user",
                    "content": f"Steps already completed (with the files they changed):\n{completed_block}",
                })
            act_messages.append({
                "role": "user",
                "content": (
                    f"Execute ONLY this step now, using your tools. Do not skip ahead. "
                    f"Use the exact file paths shown in the directory listing above — "
                    f"do not invent paths or subdirectories that aren't there. "
                    f"When the step is done, call reportStepComplete with a "
                    f"one-line summary.\n\n"
                    f"Step {i}:\n{step}"
                ),
            })

            act_result, touched = act_loop(
                act_messages,
                max_steps=ACT_MAX_STEPS,
                working_dir=directory,
            )

            if act_result is None:
                print(f"\n[Step {i} failed — stopping execution]")
                failed_at = i
                break

            completed.append({"header": header, "files": touched})
            print(f"\n[Step {i} complete] {act_result[:200]}")

        if failed_at is not None:
            history.append({
                "role": "assistant",
                "content": (
                    f"I completed {len(completed)}/{len(steps)} steps, then got stuck on step {failed_at}. "
                    f"I stopped rather than claim the task was done. What would you like me to try next?"
                ),
            })
        else:
            history.append({
                "role": "assistant",
                "content": f"Completed all {len(steps)} steps.",
            })

        if ENABLE_CONTEXT_SUMMARIZER and estimate_word_count(history) >= MAX_WORD_COUNT:
            print(f"\n[Compressing history: {estimate_word_count(history)} words]")
            history[:] = summarize_context(history)