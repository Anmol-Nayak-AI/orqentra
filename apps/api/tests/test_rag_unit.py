import math

import pytest

from orqentra.execution.provider import ProviderFailure
from orqentra.rag.provider import embed
from orqentra.rag.service import chunks


def test_chunk_boundaries_preserve_tail_and_overlap() -> None:
    text = "".join(f"{i:05d} " for i in range(4000))
    pieces = chunks(text)
    assert len(pieces) <= 20 and all(0 < len(p) <= 1500 for p in pieces)
    assert pieces[0][-150:] == pieces[1][:150] and pieces[-1].endswith(text[-100:])
    assert chunks("   ") == []


@pytest.mark.parametrize("vector", [[1.0] * 3, [math.nan] * 1536, [0.0] * 1536])
def test_invalid_embeddings_are_rejected(
    monkeypatch: pytest.MonkeyPatch, vector: list[float]
) -> None:
    monkeypatch.setattr(
        "orqentra.rag.provider.request_json",
        lambda *args: {"data": [{"index": 0, "embedding": vector}]},
    )
    with pytest.raises(ProviderFailure):
        embed("synthetic-key", ["Test source"])


def test_citation_choices_preserve_unicode_and_bind_quotes_to_their_source() -> None:
    from orqentra.rag.provider import citation_schema

    sources = [
        {
            "chunk_id": "source-a",
            "content": "Support runs 09:00–17:00 UTC. Quotes must stay exact.",
        },
        {
            "chunk_id": "source-b",
            "content": "A separate source with a different statement. " + "x" * 1600,
        },
    ]
    schema = citation_schema(sources)
    branches = schema["properties"]["citations"]["items"]["anyOf"]
    for branch in branches:
        ids = branch["properties"]["chunk_id"]["enum"]
        assert len(ids) == 1
        source = next(s for s in sources if s["chunk_id"] == ids[0])
        assert all(
            10 <= len(quote) <= 800 and quote in source["content"]
            for quote in branch["properties"]["quote"]["enum"]
        )
    assert "Support runs 09:00–17:00 UTC." in branches[0]["properties"]["quote"]["enum"]
