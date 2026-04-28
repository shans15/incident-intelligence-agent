from unittest.mock import MagicMock, patch

import pytest

from incident_intel.config import TriageError
from incident_intel.core.rca_generator import generate_rca, _parse_alert


FULL_MARKDOWN = (
    "## Summary\nService unavailable.\n"
    "## Timeline\nTimeline not available — fill in manually.\n"
    "## Root Cause (Hypothesis)\nMemory leak.\n"
    "## Impact\nAll checkout users.\n"
    "## Resolution Steps\nRestart pod.\n"
    "## Prevention / Follow-ups\nAdd memory limits."
)

PAGERDUTY_JSON = '{"title": "Redis OOM", "service": "checkout", "severity": "P1", "triggered_at": "2026-04-28T10:00:00Z", "description": "Redis is OOM"}'


def _make_mock_client(response_text: str):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_parse_alert_extracts_pagerduty_fields():
    alert_text, title = _parse_alert(PAGERDUTY_JSON)
    assert "Redis OOM" in alert_text
    assert title == "Redis OOM"
    assert "checkout" in alert_text


def test_parse_alert_falls_back_to_plain_text():
    plain = "Database is down, all queries failing"
    alert_text, title = _parse_alert(plain)
    assert alert_text == plain
    assert "Database is down" in title


def test_generate_rca_returns_draft_with_all_sections():
    with patch("incident_intel.core.rca_generator.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_client(FULL_MARKDOWN)
        draft = generate_rca(PAGERDUTY_JSON, api_key="test-key", model="claude-sonnet-4-6")

    assert "## Summary" in draft.raw_markdown
    assert "## Root Cause (Hypothesis)" in draft.raw_markdown
    assert "## Prevention / Follow-ups" in draft.raw_markdown
    assert draft.alert_title == "Redis OOM"
    assert draft.generated_at != ""


def test_generate_rca_passes_correct_model_to_api():
    with patch("incident_intel.core.rca_generator.Anthropic") as mock_cls:
        mock_client = _make_mock_client(FULL_MARKDOWN)
        mock_cls.return_value = mock_client
        generate_rca("plain text alert", api_key="test-key", model="claude-opus-4-6")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-6"


def test_generate_rca_raises_triage_error_on_api_failure():
    with patch("incident_intel.core.rca_generator._call_claude") as mock_call:
        mock_call.side_effect = Exception("API error")
        with pytest.raises(TriageError, match="Claude API failed"):
            generate_rca("some alert", api_key="test-key", model="claude-sonnet-4-6")
