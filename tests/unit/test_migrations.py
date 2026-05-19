from pathlib import Path


def test_alembic_baseline_migration_exists():
    migration = Path("migrations/versions/20260519_0001_baseline.py")
    text = migration.read_text(encoding="utf-8")

    assert Path("alembic.ini").exists()
    assert Path("migrations/env.py").exists()
    assert "conversation_events" in text
    assert "offload_entries" in text
    assert "audit_logs" in text
    assert "run_after TIMESTAMPTZ NOT NULL" in text
    assert "payload JSONB NOT NULL" in text
    assert "idx_pipeline_jobs_claim" in text
    assert "payload_json" not in text
