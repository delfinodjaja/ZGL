import json
import requests
from Tools.toolList import TOOL_LIST
from registry import TOOL_REGISTRY, setWorkingDirectory
from FallbackParser import extract_fallback_tool_call
from CONFIG import MODEL, URL, ENABLE_CONTEXT_SUMMARIZER, MAX_WORD_COUNT, ENABLE_TRIM_OLD_ARG
from contextSummarizer import  estimate_word_count, summarize_context



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
    if(ENABLE_TRIM_OLD_ARG):
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
                "temperature": 0.0
            },
            "stream": False
        }

    response = requests.post(URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]

def manager_review(messages, window=6):
    """Every N steps, a manager reviews recent work and gives feedback,
    like a check-in during a work session."""
    recent = messages[-window*2:]

    review_messages = [
        {
            "role": "system",
            "content": (
                "You are a manager doing a periodic check-in on an agent's work. "
                "Review what it has actually done in the recent steps below — not "
                "what it claims to have done. Give a short, direct review: what's "
                "going well, what's not working, and what it should focus on next. "
                "If it has been repeating the same action or claim without any "
                "actual change in results, say so plainly and tell it to stop and "
                "try something else. Keep it to 3-5 sentences, like a real manager "
                "giving feedback, not a formal report."
            )
        },
        {
            "role": "user",
            "content": f"Recent steps:\n{json.dumps(recent, default=str)[:4000]}"
        }
    ]

    response = call_model(review_messages)
    return response.get("content", "")
#TODO implement manager
def agent_loop(messages, max_steps=10, review_every=4):
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
            print(f"\n[Final Answer]\n{content}")
            return content

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
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_args)
                except Exception as e:
                    result = f"Error executing {tool_name}: {str(e)}"

            print(f"[Result] {str(result)[:50]}")

            messages.append({
                "role": "tool",
                "name": tool_name,
                "content": str(result),
                "tool_call_id": call.get("id")
            })

            if ENABLE_CONTEXT_SUMMARIZER:
                if estimate_word_count(messages) >= MAX_WORD_COUNT:
                    print(f"\n[DEBUG] Word count before compression: {estimate_word_count(messages)}")
                    messages[:] = summarize_context(
                        messages)
                    print(f"[DEBUG] Word count after compression: {estimate_word_count(messages)}")


    print("\n[Stopped: max steps reached]")
    return messages

def run_agent():
    directory = input("Enter a directory to run: ")

    SYSTEM_PROMPT = (
            "You are an agent with access to local tools.\n"
            "RULES:\n"
            "1. Perform tasks ONE step at a time.\n"
            "2. NEVER output pseudocode, multi-tool plans, or dynamic placeholders.\n"
            "3. Output strictly valid JSON. Do not use non-standard escapes like \\' inside JSON strings.\n"
            "4. Call EXACTLY ONE tool at a time.\n"
            "5. Once all files are written and tasks completed, answer directly in plain text without calling tools.\n"
            "6. Before writing or editing any file, output a short \"Think:\" block (4-6 sentences) covering:\n"
            "   - What the user is actually asking for, in your own words.\n"
            "   - What you have already done in this conversation toward this request — check your recent "
            "tool calls and their results before deciding your next action, so you don't repeat a call "
            "you already made or re-plan a change you already wrote.\n"
            "   - If you are editing a file you've already written before, state exactly what is different "
            "this time. If nothing would actually change, do not write it again — say so and ask the user "
            "a clarifying question instead.\n"
            "   - The specific decisions you will make (structure, values, naming, logic) and why they satisfy the request.\n"
            "   - Whether anything already in the file should be preserved rather than overwritten.\n"
            "   Then output exactly one tool call as JSON. Do not skip the Think block.\n"
            "7. Never claim something works, is fixed, or is running unless a tool result you actually "
            "received proves it. If you haven't verified it, say so plainly instead of asserting it.\n"
            "8. Your working directory is " + directory
    )

    setWorkingDirectory(directory)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        prompt = input("> ")
        messages.append({"role": "user", "content": prompt})
        agent_loop(messages, max_steps=25)