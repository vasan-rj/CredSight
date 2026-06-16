"""Explainability narration (ref-doc 03 §5, ref-doc 04 §Explainability).

Turns the model's actual top SHAP drivers into a plain-language, MSME-facing explanation.
This is the one place an LLM touches the credit story — and it is fenced in hard:

  1. The prompt is given ONLY the real top SHAP drivers + the score band + confidence, and
     is told to reference nothing else and to promise nothing.
  2. The output is run through governance.faithfulness.is_faithful BEFORE it is returned.
  3. On any failure (no API key, library missing, network error, or an unfaithful answer)
     it FAILS CLOSED to faithfulness.safe_template — a deterministic, faithful-by-
     construction explanation. The credit decision never waits on the LLM.

The LLM never computes or alters the score; it only phrases the explanation.
"""

from __future__ import annotations

import os

from ..config import config
from ..governance.faithfulness import is_faithful, safe_template
from ..scoring.schema import ScoreResult

_MAX_DRIVERS = 5


def llm_available() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import langchain_anthropic  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _band(composite: int) -> str:
    if composite >= 750:
        return "strong"
    if composite >= 680:
        return "good"
    if composite >= 600:
        return "fair"
    return "below the lending threshold"


def _confidence_note(score: ScoreResult) -> str:
    if score.confidence < config.hitl.confidence_floor:
        return (f" Confidence is moderate ({score.confidence:.0%}) — the data is thin, so "
                f"a human underwriter reviews this case.")
    return ""


def _llm_narrative(score: ScoreResult) -> str:
    """Generate a 2-3 sentence MSME-facing explanation, constrained to the real drivers."""
    from langchain_anthropic import ChatAnthropic

    drivers = score.shap[:_MAX_DRIVERS]
    allowed = "\n".join(
        f"- {d.feature.replace('_', ' ')} ({'supports' if d.direction == 'positive' else 'weakens'} the score)"
        for d in drivers
    )
    system = (
        "You are CredSight's explainability function for a bank assessing a micro/small "
        "business. Write 2-3 short, plain-language sentences for the business owner about "
        "their credit health score. STRICT RULES: reference ONLY the factors listed below, "
        "using their given names; do NOT invent any other factor, statistic, or number; do "
        "NOT promise or deny a loan; describe the score band qualitatively. Be warm, clear, "
        "and concrete."
    )
    human = (
        f"Score band: {_band(score.composite)} ({score.composite}/900). "
        f"Confidence: {score.confidence:.0%}.\nFactors (the only ones you may mention):\n{allowed}"
    )
    model_id = config.model_reasoning.split(":", 1)[-1]
    llm = ChatAnthropic(model=model_id, temperature=0, max_tokens=300)
    resp = llm.invoke([("system", system), ("human", human)])
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return text.strip()


def generate_explanation(score: ScoreResult) -> str:
    """MSME-facing explanation. LLM-narrated when available + faithful, else the template."""
    base = safe_template(score.shap)
    if llm_available():
        try:
            narrative = _llm_narrative(score)
            if is_faithful(narrative, score.shap, clause_refs=[]):
                return narrative + _confidence_note(score)
        except Exception:
            pass  # fail closed to the template below
    return base + _confidence_note(score)
