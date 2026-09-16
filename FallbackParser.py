import json
import re
from json_repair import repair_json


def _try_parse_tool_call(candidate: str):
    """Attempt to parse a candidate string as a {"name":..., "arguments":...} object."""
    try:
        data = json.loads(candidate)
    except Exception:
        try:
            repaired_str = repair_json(candidate, return_objects=False)
            data = json.loads(repaired_str)
        except Exception:
            return None

    if isinstance(data, dict) and "name" in data and "arguments" in data:
        return [{
            "function": {
                "name": data["name"],
                "arguments": data["arguments"]
            }
        }]
    return None


def _normalize_over_escaping(text: str) -> str:
    """
    Collapse doubled backslashes before common escape characters
    (e.g. '\\\\n' -> '\\n', '\\\\"' -> '\\"') without touching legitimate
    single backslashes. Repeats until stable to catch triple/quadruple
    escaping from repeated model mistakes.
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'\\\\([ntr"\\])', r'\\\1', text)
    return text


def _extract_balanced(content: str, start: int):
    """Return the substring of the first balanced {...} block starting at index `start`."""
    depth = 0
    for i in range(start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start:i + 1]
    return None


def extract_fallback_tool_call(content: str):
    if not content or not content.strip():
        return None

    candidates = []

    # 1. Prefer explicit ```json fenced blocks — most unambiguous signal
    candidates.extend(
        block.strip() for block in re.findall(r"```json\s*(.*?)```", content, re.DOTALL)
    )

    # 2. Fall back to scanning every '{' position, not just the first —
    #    skips over unrelated balanced braces (e.g. CSS/JS/Python code blocks)
    idx = content.find("{")
    while idx != -1:
        candidate = _extract_balanced(content, idx)
        if candidate:
            candidates.append(candidate)
        idx = content.find("{", idx + 1)

    # Try each candidate as-is first, then with over-escaping normalized
    for candidate in candidates:
        result = _try_parse_tool_call(candidate)
        if result:
            return result

    for candidate in candidates:
        normalized = _normalize_over_escaping(candidate)
        if normalized != candidate:
            result = _try_parse_tool_call(normalized)
            if result:
                return result

    return None