import json
import requests

import CONFIG
from Tools.toolList import TOOL_LIST
from registry import TOOL_REGISTRY, setWorkingDirectory as set_registry_dir
from FallbackParser import extract_fallback_tool_call
from CONFIG import MODEL, URL, ENABLE_CONTEXT_SUMMARIZER, \
    MAX_WORD_COUNT, ENABLE_TRIM_OLD_ARG, get_act_prompt, get_orient_plan_prompt, \
    setWorkingDirectory as set_config_dir
from contextSummarizer import estimate_word_count, summarize_context


def trim_old_tool_args(messages, keep_last=2):
    tool_msg_count = sum(1 for m in messages if m.get("role") == "tool")
    seen = 0
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for call in m["tool_calls"]:
                args = call["function"].get("arguments")
                if isinstance(args, dict) and "content" in args and args["content"] != "[trimmed]":
                    seen += 1
                    if seen <= tool_msg_count - keep_last:
                        note = m.get("content") or "(no note provided)"
                        args["content"] = f"[trimmed — see note: {note}]"
    return messages


def call_model(messages):
    if ENABLE_TRIM_OLD_ARG:
        payload = {
            "model": MODEL,
            "messages": trim_old_tool_args(messages),
            "tools": TOOL_LIST,
            "options": {
                "repeat_penalty": 1.1,
            },
            "stream": False
        }
    else:
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": TOOL_LIST,
            "options": {
                "repeat_penalty": 1.1,
            },
            "stream": False
        }

    response = requests.post(URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]


def act_loop(messages, max_steps=10):
    last_result_was_error = False
    for step in range(max_steps):
        message = call_model(messages)
        #print(f"\n[DEBUG] Raw message: {message}")

        tool_calls = message.get("tool_calls")
        content = message.get("content", "")

        if not tool_calls and content:
            fallback_calls = extract_fallback_tool_call(content)
            if fallback_calls:
                tool_calls = fallback_calls
                message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                }

        messages.append(message)

        if not tool_calls:
            if last_result_was_error:
                print("\n[Rejected] Last tool call errored — forcing retry instead of accepting as final answer.")
                messages.append({
                    "role": "user",
                    "content": (
                        "Your last tool call failed. Do not give up — try a different "
                        "approach or fix the issue before declaring the task complete."
                    )
                })
                continue
            print(f"\n[Final Answer]\n{content}")
            return content

        last_result_was_error = False  # reset each turn a tool call actually happens

        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = call["function"]["arguments"]

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            print(f"\n[Step {step + 1}] Model called: {tool_name}({tool_args})")

            if tool_name not in TOOL_REGISTRY:
                result = f"Error: unknown tool '{tool_name}'"
                last_result_was_error = True
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {str(e)}"
                    last_result_was_error = True

            #print(f"[Result] {str(result)[:50]}")

            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": str(result),
                "tool_call_id": call.get("id")
            })


    print("\n[Stopped: max steps reached]")
    return messages


def plan(messages, max_steps=5):
    last_result_was_error = False

    for step in range(max_steps):
        message = call_model(messages)
        print(f"\n[DEBUG] Raw message: {message}")

        tool_calls = message.get("tool_calls")
        content = message.get("content", "")

        if not tool_calls and content:
            fallback_calls = extract_fallback_tool_call(content)
            if fallback_calls:
                tool_calls = fallback_calls
                message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                }

        messages.append(message)

        if not tool_calls:
            if last_result_was_error:
                print("\n[Rejected] Last tool call errored — forcing retry instead of accepting as plan.")
                messages.append({
                    "role": "user",
                    "content": (
                        "Your last tool call failed. Do not give up — try a different "
                        "approach (e.g. list the directory to find the correct filename) "
                        "before producing a plan."
                    )
                })
                continue
            print(f"\n[Plan produced]\n{content}")
            return content

        last_result_was_error = False

        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = call["function"]["arguments"]

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args = {}

            print(f"\n[Step {step + 1}] Model called: {tool_name}({tool_args})")

            if tool_name not in TOOL_REGISTRY:
                result = f"Error: unknown tool '{tool_name}'"
                last_result_was_error = True
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {str(e)}"
                    last_result_was_error = True

            print(f"[Result] {str(result)[:50]}")

            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": str(result),
                "tool_call_id": call.get("id")
            })

    print("\n[Plan stage: max steps reached]")
    return None


def run_agent():
    directory = input("Enter a directory to run: ")

    set_registry_dir(directory)
    set_config_dir(directory)

    history = []

    while True:
        user_prompt = input("> ")
        history.append({"role": "user", "content": user_prompt})

        plan_messages = [{"role": "system", "content": get_orient_plan_prompt()}] + history
        plan_result = plan(plan_messages, max_steps=5)

        if plan_result is None:
            print("\n[Planning failed to converge — aborting this request]")
            continue

        history.append({"role": "assistant", "content": f"Plan:\n{plan_result}", "message_type": "plan"})

        act_messages = [{"role": "system", "content": CONFIG.get_act_prompt()}] + history + [
            {"role": "user", "content": (
                f"A plan has been prepared for this request. None of it has been executed yet "
                f"— no files have been created or edited. Execute it now, one item at a time, "
                f"starting with item 1:\n\n{plan_result}"
            )}
        ]
        act_result = act_loop(act_messages, max_steps=25)

        if isinstance(act_result, str):
            # risk: wrong claim, act_result is Act's own self-report, not verified
            history.append({"role": "assistant", "content": act_result})

        if ENABLE_CONTEXT_SUMMARIZER:
            if estimate_word_count(history) >= MAX_WORD_COUNT:
                print(f"\n[DEBUG] Word count before compression: {estimate_word_count(history)}")
                history[:] = summarize_context(history)
                print(f"[DEBUG] Word count after compression: {estimate_word_count(history)}")

