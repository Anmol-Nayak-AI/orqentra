import json

import pytest

from orqentra.execution.provider import ProviderFailure, generate


class Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self, limit: int) -> bytes:
        return json.dumps(self.payload).encode()[:limit]


def test_responses_payload_is_structured_and_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    output = {
        "summary": "Synthetic output",
        "checklist": [],
        "missing_information": ["Provide product details"],
        "draft_reply": "",
    }

    class Opener:
        def open(self, request: object, timeout: int) -> Response:
            payload = json.loads(request.data)
            assert request.full_url == "https://api.openai.com/v1/responses"
            assert payload["store"] is False and payload["max_output_tokens"] == 2000
            assert payload["text"]["format"]["strict"] is True and timeout == 30
            return Response(
                {
                    "status": "completed",
                    "output": [{"content": [{"type": "output_text", "text": json.dumps(output)}]}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                }
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Opener())
    plan, usage = generate(
        "synthetic-test-key", "gpt-4.1-mini", "Test instructions", "Test request", []
    )
    assert plan.missing_information == ["Provide product details"] and usage["input_tokens"] == 10


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "incomplete"},
        {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]},
        {
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": "not json"}]}],
        },
    ],
)
def test_provider_refusal_and_invalid_schema_fail_closed(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    class Opener:
        def open(self, *args: object, **kwargs: object) -> Response:
            return Response(payload)

    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Opener())
    with pytest.raises(ProviderFailure):
        generate("synthetic-test-key", "gpt-4.1-mini", "Test instructions", "Test request", [])
