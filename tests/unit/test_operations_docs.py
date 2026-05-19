from pathlib import Path


def test_operations_doc_mentions_required_services():
    text = Path("docs/operations.md").read_text(encoding="utf-8")

    assert "Postgres" in text
    assert "pgvector" in text
    assert "ONLY_ONE_MEMORY_API_KEY" in text
