"""Explainability narration. Without an API key (the test environment) it must fall back
to the faithful template; with a key the LLM output is faithfulness-gated before return."""

from __future__ import annotations

from credsight.agents.narrate import generate_explanation, llm_available
from credsight.governance.faithfulness import is_faithful
from credsight.scoring.schema import ScoreResult, ShapDriver


def _score() -> ScoreResult:
    return ScoreResult(
        app_id="APP1", model_version="v0",
        dimensions={}, composite=718, confidence=0.62,
        shap=[
            ShapDriver(feature="gst_filing_punctuality", value=0.96, shap_value=1.2, direction="positive"),
            ShapDriver(feature="balance_volatility_norm", value=0.6, shap_value=-0.9, direction="negative"),
        ],
    )


def test_fallback_is_faithful_without_key():
    score = _score()
    text = generate_explanation(score)
    assert text  # non-empty
    assert is_faithful(text, score.shap, clause_refs=[])


def test_low_confidence_note_present():
    # confidence 0.62 < default floor 0.70? floor default is 0.5; force a clearly-low case.
    score = _score()
    score = score.model_copy(update={"confidence": 0.2})
    text = generate_explanation(score)
    assert "moderate" in text.lower() or "thin" in text.lower()


def test_llm_available_false_in_test_env():
    # No ANTHROPIC_API_KEY in CI/tests -> deterministic template path.
    assert llm_available() is False
