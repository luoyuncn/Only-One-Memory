"""文件系统 refs 存储，保存 offload 原文并防止路径逃逸。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from oom.memory_core.offload.types import OffloadRef


class OffloadRefStore:
    """以 JSON 文件保存被卸载的大块原文。

    数据库只保存 result_ref/node_id 等轻量索引；真正的大文本留在 refs 目录中，按需恢复。
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_ref(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        session_id: str,
        kind: str,
        content: str,
        metadata: dict | None = None,
    ) -> OffloadRef:
        """创建 ref 文件，并记录 hash 便于后续核对内容完整性。"""
        ref = OffloadRef(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            kind=kind,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
            content=content,
        )
        path = self._path_for(ref.id)
        path.write_text(json.dumps(ref.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
        return ref

    def get_ref(self, ref_id: str) -> OffloadRef | None:
        """按 ref_id 读取原文，缺失时返回 None。"""
        path = self._path_for(ref_id)
        if not path.exists():
            return None
        return OffloadRef.model_validate_json(path.read_text(encoding="utf-8"))

    def put_ref(self, ref: OffloadRef) -> OffloadRef:
        path = self._path_for(ref.id)
        path.write_text(json.dumps(ref.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
        return ref

    def export_refs(self, tenant_id: str | None = None) -> list[dict]:
        """导出 refs，可按租户过滤，供 admin export 合并进备份包。"""
        refs: list[dict] = []
        for path in sorted(self.data_dir.glob("*.json")):
            ref = OffloadRef.model_validate_json(path.read_text(encoding="utf-8"))
            if tenant_id is not None and ref.tenant_id != tenant_id:
                continue
            refs.append(ref.model_dump(mode="json"))
        return refs

    def import_refs(self, refs: list[dict], tenant_id: str) -> int:
        """导入 refs 时强制改写 tenant_id，避免备份跨租户污染。"""
        count = 0
        for item in refs:
            ref = OffloadRef.model_validate(item).model_copy(update={"tenant_id": tenant_id})
            self.put_ref(ref)
            count += 1
        return count

    def list_ref_metadata(self, tenant_id: str | None = None) -> list[dict]:
        refs: list[dict] = []
        for path in sorted(self.data_dir.glob("*.json")):
            ref = OffloadRef.model_validate_json(path.read_text(encoding="utf-8"))
            if tenant_id is not None and ref.tenant_id != tenant_id:
                continue
            item = ref.model_dump(mode="json", exclude={"content"})
            refs.append(item)
        return refs

    def delete_refs_for_user(self, tenant_id: str, user_id: str) -> int:
        """删除指定用户的文件型 refs，配合数据库删除服务完成全量清理。"""
        count = 0
        for path in sorted(self.data_dir.glob("*.json")):
            ref = OffloadRef.model_validate_json(path.read_text(encoding="utf-8"))
            if ref.tenant_id == tenant_id and ref.user_id == user_id:
                path.unlink()
                count += 1
        return count

    def _path_for(self, ref_id: str) -> Path:
        """把 ref_id 解析到数据目录内，拒绝任何路径穿越。"""
        self._validate_ref_id(ref_id)
        path = (self.data_dir / f"{ref_id}.json").resolve()
        data_dir = self.data_dir.resolve()
        if path.parent != data_dir:
            raise ValueError("ref_id must not escape data_dir")
        return path

    @staticmethod
    def _validate_ref_id(ref_id: str) -> None:
        if not ref_id or ref_id in {".", ".."} or "/" in ref_id or "\\" in ref_id:
            raise ValueError("ref_id must be a single file-safe identifier")
