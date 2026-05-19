"""LLM JSON 解析工具，容忍模型返回 markdown fence 或前后缀文本。"""

from __future__ import annotations

import json
import re
from typing import Any


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def parse_json_array(raw: str) -> list[Any]:
    """从 LLM 输出中提取第一个 JSON 数组。"""
    cleaned = _clean_control_chars(_FENCE_RE.sub("", raw).strip())
    start = cleaned.find("[")
    if start < 0:
        raise ValueError("No JSON array found")

    end = _find_array_end(cleaned, start)
    if end < 0:
        raise ValueError("JSON array is not closed")

    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, list):
        raise ValueError("JSON value is not an array")
    return value


def _clean_control_chars(value: str) -> str:
    """移除 JSON 不允许的控制字符，保留常见空白。"""
    return "".join(char for char in value if char in "\r\n\t" or ord(char) >= 32)


def _find_array_end(value: str, start: int) -> int:
    """按括号深度定位数组结束位置，避免被字符串里的 ] 干扰。"""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    return -1
