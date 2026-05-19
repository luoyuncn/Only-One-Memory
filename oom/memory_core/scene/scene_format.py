"""场景 Markdown 的解析、格式化与导航块处理。"""

from __future__ import annotations

from dataclasses import dataclass


META_START = "-----META-START-----"
META_END = "-----META-END-----"
REQUIRED_META_FIELDS = ("created", "updated", "summary", "heat")


@dataclass(frozen=True)
class SceneMeta:
    created: str
    updated: str
    summary: str
    heat: int


@dataclass(frozen=True)
class ParsedSceneBlock:
    filename: str
    meta: SceneMeta
    body: str


def format_scene_block(created: str, updated: str, summary: str, heat: int, body: str) -> str:
    meta_lines = [
        META_START,
        f"created: {created}",
        f"updated: {updated}",
        f"summary: {summary}",
        f"heat: {heat}",
        META_END,
        "",
        body.rstrip("\n"),
    ]
    return "\n".join(meta_lines) + "\n"


def parse_scene_block(markdown: str, filename: str) -> ParsedSceneBlock:
    lines = markdown.splitlines()
    if not lines or lines[0] != META_START:
        raise ValueError(f"{filename} 缺少严格的 {META_START} 元数据块")

    try:
        meta_end_index = lines.index(META_END, 1)
    except ValueError as exc:
        raise ValueError(f"{filename} 缺少严格的 {META_END} 元数据块") from exc

    meta = _parse_meta_lines(lines[1:meta_end_index], filename)
    body_start_index = meta_end_index + 1
    if body_start_index < len(lines) and lines[body_start_index] == "":
        body_start_index += 1

    return ParsedSceneBlock(
        filename=filename,
        meta=meta,
        body="\n".join(lines[body_start_index:]).rstrip("\n"),
    )


def _parse_meta_lines(lines: list[str], filename: str) -> SceneMeta:
    values: dict[str, str] = {}
    for line in lines:
        if ": " not in line:
            raise ValueError(f"{filename} 元数据行必须使用 'key: value' 格式")
        key, value = line.split(": ", 1)
        values[key] = value

    for field in REQUIRED_META_FIELDS:
        if field not in values:
            raise ValueError(f"{filename} 缺少元数据字段 {field}")

    try:
        heat = int(values["heat"])
    except ValueError as exc:
        raise ValueError(f"{filename} 元数据字段 heat 必须是整数") from exc

    return SceneMeta(
        created=values["created"],
        updated=values["updated"],
        summary=values["summary"],
        heat=heat,
    )
