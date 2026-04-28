from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from incident_intel.config import TriageError
from incident_intel.models import PagerDutyAlert, RCADraft

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer specializing in incident triage and root cause analysis.

Your job is to take a raw incident alert and produce a concise, structured RCA draft in markdown.

Always output exactly these sections in this order, using these exact headers:
## Summary
## Timeline
## Root Cause (Hypothesis)
## Impact
## Resolution Steps
## Prevention / Follow-ups

Rules:
- If timeline information is not available, write: "Timeline not available — fill in manually."
- If a field cannot be determined from the alert, mark it with [UNKNOWN] and move on.
- Each section should be 2-5 bullet points or sentences. Do not pad.
- Do not include any text outside these six sections.
- Output only markdown. No preamble, no sign-off."""


def _parse_alert(alert: str) -> tuple[str, str]:
    """Parse alert input. Returns (alert_text_for_prompt, alert_title).

    Tries PagerDuty JSON first; falls back to plain text.
    """
    try:
        data = json.loads(alert)
        pd = PagerDutyAlert(**data)
        text = (
            f"Title: {pd.title}\n"
            f"Service: {pd.service}\n"
            f"Severity: {pd.severity}\n"
            f"Triggered at: {pd.triggered_at}\n"
            f"Description: {pd.description}"
        )
        return text, pd.title
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("alert_not_pagerduty_json", preview=alert[:80])
        return alert, alert[:80]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _call_claude(client: Anthropic, model: str, alert_text: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze this incident alert and produce a structured RCA draft:\n\n"
                    f"{alert_text}"
                ),
            }
        ],
    )
    return response.content[0].text


def generate_rca(alert: str, api_key: str, model: str) -> RCADraft:
    """Generate a structured RCA draft from a raw alert string.

    Raises TriageError if Claude API fails after 3 retries.
    """
    alert_text, alert_title = _parse_alert(alert)
    client = Anthropic(api_key=api_key)
    logger.info("generating_rca", alert_title=alert_title, model=model)

    try:
        raw_markdown = _call_claude(client, model, alert_text)
    except Exception as e:
        raise TriageError(f"Claude API failed after 3 retries: {e}") from e

    return RCADraft(
        raw_markdown=raw_markdown,
        alert_title=alert_title,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
