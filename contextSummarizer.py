import requests
from CONFIG import URL, PLAN_MODEL

SUMMARY_SYSTEM_PROMPT = (
    "You are a summarization assistant. You will be given a conversation transcript "
    "between a user, an AI coding agent, and tool results. Summarize it concisely, "
    "preserving: \n"
    "1. What the user originally asked for.\n"
    "2. What files were created/modified and their current purpose.\n"
    "3. Any bugs reported by the user and whether they were fixed.\n"
    "4. Any explicit user preferences or corrections (e.g. 'use brown not green').\n"
    "Do not include tool call syntax or raw code — describe outcomes, not mechanics."
)


def estimate_word_count(messages):
    return sum(len(str(m.get("content", "")).split()) for m in messages)


def is_plan_message(m):
    # Prefer a structural tag if present; fall back to content-prefix matching
    # for plan messages that predate the tag.
    if m.get("message_type") == "plan":
        return True
    return m.get("role") == "assistant" and str(m.get("content", "")).startswith("Plan:")


def _summarize_raw(messages):
    """Call the model to summarize a batch of non-plan messages. Returns a string."""
    if not messages:
        return ""
    transcript = "\n".join(
        f"{m['role']}: {str(m.get('content',''))[:500]}" for m in messages
    )
    summary_messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": transcript}
    ]
    response = requests.post(URL, json={
        "model": PLAN_MODEL,
        "messages": summary_messages,
        "options": {"temperature": 0.0},
        "stream": False
    }, timeout=120)
    response.raise_for_status()
    return response.json()["message"]["content"]


def summarize_context(messages, protected_head=1):

    head = messages[:protected_head]
    body = messages[protected_head:]

    result = []
    buffer = []

    def flush_buffer():
        if buffer:
            summary_text = _summarize_raw(buffer)
            if summary_text:
                result.append({"role": "assistant", "content": f"[Summary]\n{summary_text}"})
            buffer.clear()

    for m in body:
        if is_plan_message(m):
            flush_buffer()
            result.append(m)
        else:
            buffer.append(m)
    flush_buffer()

    return head + result