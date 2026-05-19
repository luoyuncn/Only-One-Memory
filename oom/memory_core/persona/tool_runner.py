"""Persona 相关工具沙箱，限制可访问的 profile 操作。"""

from __future__ import annotations

from pathlib import Path


class PersonaToolRunner:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def write_file(self, filename: str, content: str) -> None:
        if filename != "persona.md":
            raise ValueError("persona tools only allow persona.md")
        await self.write_persona(content)

    async def write_persona(self, content: str) -> None:
        self._persona_path().write_text(content, encoding="utf-8")

    async def edit_persona(self, old: str, new: str) -> None:
        path = self._persona_path()
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if old not in content:
            raise ValueError("old content not found")
        path.write_text(content.replace(old, new, 1), encoding="utf-8")

    def read_persona(self) -> str:
        path = self._persona_path()
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _persona_path(self) -> Path:
        return self.root / "persona.md"
