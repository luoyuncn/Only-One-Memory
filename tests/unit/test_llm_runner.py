from oom.memory_core.llm.openai_compatible import OpenAICompatibleLlmRunner


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self):
        return b'{"choices":[{"message":{"content":"ok"}}]}'


async def test_openai_compatible_llm_runner_returns_message_content(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    runner = OpenAICompatibleLlmRunner(
        base_url="https://example.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=3,
    )

    result = await runner.complete("system", "user")

    assert result == "ok"
    assert requests[0][1] == 3
