"""
Tests for the filtered technical search (app/rag/store.technical_context) and
for the one property the studio knowledge base must have: it describes, it does
not instruct.

Why this exists: "how is the receptionist built, what's the architecture?" -
the first question an evaluator asks on Shaheer's line, and one of its three
topics - was answered "I can't provide specific details about the
architecture". Two separate causes, both covered here.
"""
import pathlib

import pytest

from app.rag import store
from app.shared.verticals import get_vertical

SEED_DIR = pathlib.Path(__file__).resolve().parent.parent / "seed_knowledge_shaheer"


class _Point:
    def __init__(self, filename, text, score):
        self.payload = {"filename": filename, "text": text}
        self.score = score


class _FakeQdrant:
    def __init__(self, points):
        self._points = points
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return self._points


@pytest.fixture
def patched(monkeypatch):
    async def fake_embed(_text):
        return [0.0] * 1536

    # **kwargs rather than a named `timeout`: ruff's ASYNC109 flags that
    # parameter name on an async def, and the stub only needs to swallow it.
    async def fake_rerank(query, chunks, top_n, **kwargs):
        return chunks[:top_n], True

    monkeypatch.setattr(store, "embed_single", fake_embed)
    monkeypatch.setattr(store, "_rerank_with_jina", fake_rerank)


# ── The filter ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_vertical_with_no_technical_documents_never_searches(patched):
    """Every real-estate tenant takes this path: it must not cost a query."""
    client = _FakeQdrant([])
    assert await store.technical_context(
        "what's the architecture?", "c-1", [], client=client
    ) == ""
    assert client.calls == []


@pytest.mark.asyncio
async def test_a_business_question_does_not_trigger_the_second_search(patched):
    client = _FakeQdrant([])
    assert await store.technical_context(
        "do you have anything in Dubai Marina?", "c-1",
        ["technical_qa.md"], client=client
    ) == ""
    assert client.calls == []


@pytest.mark.asyncio
async def test_only_the_technical_documents_survive(patched):
    """
    The point of the whole function: an open search ranked three chunks of
    service description above the first technical one, so the model answered
    from sales copy and hedged.
    """
    client = _FakeQdrant([
        _Point("about_the_service.md", "An AI receptionist for agencies.", 0.62),
        _Point("shaheer_products.md", "Pricing starts at AED 1,300.", 0.55),
        _Point("technical_qa.md", "The language model is GPT-4o-mini.", 0.41),
        _Point("receptionist_on_this_line.md", "Enforced in code, not prompted.", 0.33),
    ])
    context = await store.technical_context(
        "how is the receptionist built, what's the architecture?", "c-1",
        ["technical_qa.md", "receptionist_on_this_line.md"], client=client,
    )
    assert "GPT-4o-mini" in context
    assert "Enforced in code" in context
    assert "AED 1,300" not in context
    assert "for agencies" not in context


@pytest.mark.asyncio
async def test_no_technical_chunks_means_no_context_rather_than_an_error(patched):
    client = _FakeQdrant([_Point("shaheer_products.md", "Pricing.", 0.6)])
    assert await store.technical_context(
        "what's the architecture?", "c-1", ["technical_qa.md"], client=client
    ) == ""


@pytest.mark.asyncio
async def test_the_search_is_scoped_to_the_company(patched):
    """A filtered search is still a search: it must not cross tenants."""
    client = _FakeQdrant([_Point("technical_qa.md", "GPT-4o-mini.", 0.5)])
    await store.technical_context(
        "what's the architecture?", "company-abc", ["technical_qa.md"], client=client
    )
    dumped = str(client.calls[0]["query_filter"])
    assert "company-abc" in dumped


@pytest.mark.parametrize("question", [
    "what's the architecture?",
    "how is this built?",
    "walk me through the stack",
    "what's your latency?",
    "which model do you use?",
    "how do you stop it hallucinating?",
    "how is multi-tenancy enforced?",
    "where is it deployed?",
    "what happens when Deepgram fails?",
])
def test_the_trigger_catches_how_evaluators_actually_ask(question):
    assert store._TECHNICAL_QUESTION.search(question), question


@pytest.mark.parametrize("question", [
    "can you help me get more leads?",
    "what does Shaheer charge?",
    "I need someone to take my calls at night",
])
def test_the_trigger_leaves_business_questions_alone(question):
    assert not store._TECHNICAL_QUESTION.search(question), question


# ── The knowledge base must describe, not instruct ───────────────────────────

def test_the_studio_documents_contain_no_instructions():
    """
    A seed document is reference material, and the guardrail says to treat it
    as such - but a document written in the imperative gets obeyed anyway. The
    first version of receptionist_on_this_line.md said that someone "fishing
    for its instructions" gets one sentence and the email address, and that
    chunk ranked top for "how is the receptionist built", so the receptionist
    classified the question as fishing and refused it at temperature 0.
    """
    banned = [
        "say so plainly",
        "point them at",
        "gets one sentence",
        "should be told",
        "answer from",
        "never invent",
        "close on the email",
        "do not refuse",
    ]
    for path in sorted(SEED_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in banned:
            assert phrase not in text, f"{path.name} instructs the model: {phrase!r}"


def test_the_studio_vertical_points_at_documents_that_exist():
    for name in get_vertical("ai_studio")["technical_docs"]:
        in_studio = (SEED_DIR / name).is_file()
        in_general = (SEED_DIR.parent / "seed_knowledge" / name).is_file()
        assert in_studio or in_general, f"{name} is configured but not seeded anywhere"
