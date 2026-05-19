from __future__ import annotations

from pathlib import Path


class SceneToolRunner:
    def __init__(self, root: str | Path, readable_files: set[str] | None = None) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.readable_files = readable_files

    async def read_scene(self, filename: str) -> str:
        safe_path = self._safe_scene_path(filename)
        if self.readable_files is not None and filename not in self.readable_files:
            raise ValueError(f"scene file is not readable: {filename}")
        return safe_path.read_text(encoding="utf-8")

    async def write_scene(self, filename: str, content: str) -> None:
        safe_path = self._safe_scene_path(filename)
        safe_path.write_text(content, encoding="utf-8")

    async def edit_scene(self, filename: str, old: str, new: str) -> None:
        safe_path = self._safe_scene_path(filename)
        content = safe_path.read_text(encoding="utf-8")
        if old not in content:
            raise ValueError("old content not found")
        safe_path.write_text(content.replace(old, new, 1), encoding="utf-8")

    async def delete_scene(self, filename: str) -> None:
        safe_path = self._safe_scene_path(filename)
        safe_path.write_text("[DELETED]", encoding="utf-8")

    def _safe_scene_path(self, filename: str) -> Path:
        path = Path(filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("path traversal is not allowed")
        if path.suffix != ".md":
            raise ValueError("scene file must be .md")
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("path traversal is not allowed")
        return resolved
