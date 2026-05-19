from pathlib import Path


def test_tencentdb_attribution_doc_mentions_mit_license():
    text = Path("docs/attribution/tencentdb-agent-memory.md").read_text(encoding="utf-8")

    assert "TencentDB-Agent-Memory" in text
    assert "MIT" in text
