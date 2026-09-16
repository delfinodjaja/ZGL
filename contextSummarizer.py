import requests
from CONFIG import MODEL, URL

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

def summarize_context(messages, protected_head=1):
    """Summarize everything except the protected system prompt (and optionally
    a pinned plan/spec, if you add that later)."""
    transcript = "\n".join(
        f"{m['role']}: {str(m.get('content',''))[:500]}" for m in messages[protected_head:]
    )
    summary_messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": transcript}
    ]
    response = requests.post(URL, json={
        "model": MODEL,
        "messages": summary_messages,
        "options": {"temperature": 0.0},
        "stream": False
    }, timeout=120)
    response.raise_for_status()
    return response.json()["message"]["content"]