from oom.memory_core.pipeline.checkpoint import CheckpointStore, PipelineSessionState
from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore


async def test_checkpoint_round_trip(tmp_path):
    store = CheckpointStore(path=tmp_path / "pipeline.json")
    await store.save({"s1": PipelineSessionState.new("s1", enable_warmup=True)})

    restored = await store.load()

    assert restored["s1"].session_key == "s1"


async def test_memory_core_restores_pipeline_checkpoint(tmp_path):
    checkpoint_path = tmp_path / "pipeline.json"
    config = AppConfig.model_validate(
        {
            "store": {"sqlite": {"path": str(tmp_path / "memory.db")}},
            "pipeline": {"checkpoint_path": str(checkpoint_path)},
        }
    )
    first = MemoryCore(config)
    await first.initialize()
    first.pipeline.load_states({"s1": PipelineSessionState.new("s1", enable_warmup=True)})
    await first.close()

    second = MemoryCore(config)
    await second.initialize()

    assert second.pipeline.state_for("s1") is not None
    await second.close()
