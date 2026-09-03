"""
Tests for app/shared/verticals.py — the per-vertical config that lets one
orchestrator pipeline serve more than one business domain (real_estate,
ai_studio) without forking a second code path.

The most important property under test: a company row with no `vertical`
column (or an unrecognised value) must produce byte-identical real_estate
behaviour to what existed before verticals.py was introduced — no existing
tenant's prompts may change unless its row is explicitly switched.
"""
from app.shared.verticals import get_vertical, build_knowledge_system_prompt, DEFAULT_VERTICAL


def test_missing_vertical_falls_back_to_real_estate():
    assert get_vertical(None) is get_vertical(DEFAULT_VERTICAL)


def test_unrecognised_vertical_falls_back_to_real_estate():
    """A bad/unset value must never silently produce different behaviour."""
    assert get_vertical("some_typo") is get_vertical(DEFAULT_VERTICAL)


def test_ai_studio_is_a_distinct_config():
    assert get_vertical("ai_studio") is not get_vertical("real_estate")


def test_real_estate_prompt_keeps_property_language():
    company = {"vertical": "real_estate", "name": "Test Realty", "ai_persona": "a receptionist"}
    system = build_knowledge_system_prompt(company, rag_context="123 Main St, $500k")
    assert "PROPERTY KNOWLEDGE BASE" in system
    assert "123 Main St, $500k" in system
    assert "Test Realty" in system


def test_missing_vertical_column_keeps_real_estate_prompt():
    """Simulates a company row fetched before migration 0005 was applied —
    the dict simply has no 'vertical' key at all."""
    company = {"name": "Legacy Agency", "ai_persona": "a receptionist"}
    system = build_knowledge_system_prompt(company, rag_context="some listing")
    assert "PROPERTY KNOWLEDGE BASE" in system


def test_ai_studio_prompt_has_no_property_language():
    company = {"vertical": "ai_studio", "name": "Shaheer Salal Studio", "ai_persona": "the studio's assistant"}
    system = build_knowledge_system_prompt(company, rag_context="NexaDesk pricing info")
    assert "PROPERTY KNOWLEDGE BASE" not in system
    assert "Shaheer Salal Studio" in system
    assert "NexaDesk pricing info" in system


def test_guardrail_block_present_in_every_vertical():
    """The anti-jailbreak/anti-hallucination rules must not be optional."""
    for vertical_key in ("real_estate", "ai_studio"):
        company = {"vertical": vertical_key, "name": "X"}
        system = build_knowledge_system_prompt(company, rag_context="context")
        assert "HARD RULES" in system
        assert "never as instructions" in system


def test_live_fetch_context_appears_only_when_provided():
    """
    The literal phrase "FETCHED PAGE CONTEXT" always appears once, inside the
    static guardrail rules (it's named there so the model knows what to
    treat as untrusted). What must NOT appear without live_fetch_context is
    the actual injected block itself.
    """
    company = {"vertical": "ai_studio", "name": "Studio"}

    without = build_knowledge_system_prompt(company, rag_context="kb text")
    assert "(the visitor's own page" not in without

    with_ctx = build_knowledge_system_prompt(
        company, rag_context="kb text", live_fetch_context="Visitor's homepage says: we sell widgets.",
    )
    assert "(the visitor's own page" in with_ctx
    assert "we sell widgets" in with_ctx


def test_no_context_note_only_fires_when_both_sources_empty():
    company = {"vertical": "ai_studio", "name": "Studio"}

    empty = build_knowledge_system_prompt(company, rag_context="")
    assert "[SYSTEM NOTE: No knowledge base context was retrieved" in empty

    only_live = build_knowledge_system_prompt(company, rag_context="", live_fetch_context="some page text")
    assert "[SYSTEM NOTE: No knowledge base context was retrieved" not in only_live
