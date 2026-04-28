import pytest

from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.models import RCADraft


SAMPLE_SIMILAR = [
    {
        "id": "INC-0001",
        "title": "Redis OOM causing checkout timeouts",
        "severity": "P1",
        "date": "2024-11-15",
        "root_cause": "Memory limit not set on Redis; cache grew unbounded",
        "resolution": "Increased memory limit and added eviction policy",
        "link": "",
    },
    {
        "id": "INC-0002",
        "title": "Database connection pool exhausted",
        "severity": "P2",
        "date": "2024-10-03",
        "root_cause": "Pool size too small for traffic spike",
        "resolution": "Increased pool size to 50",
        "link": "https://jira.example.com/INC-0002",
    },
]

SAMPLE_DRAFT = RCADraft(
    raw_markdown="## Summary\nService down.\n## Timeline\nTimeline not available — fill in manually.\n## Root Cause (Hypothesis)\nUnknown.\n## Impact\nAll users.\n## Resolution Steps\nRestart service.\n## Prevention / Follow-ups\nAdd monitoring.",
    alert_title="Test alert",
    generated_at="2026-04-28T00:00:00+00:00",
)


def test_format_similar_includes_incident_ids():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "INC-0001" in output
    assert "INC-0002" in output


def test_format_similar_includes_root_cause():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "Memory limit not set on Redis" in output


def test_format_similar_includes_link_when_present():
    output = format_similar_incidents(SAMPLE_SIMILAR, total_searched=10)
    assert "https://jira.example.com/INC-0002" in output


def test_format_similar_empty_returns_seed_hint():
    output = format_similar_incidents([], total_searched=0)
    assert "incident-intel seed" in output
    assert "No similar incidents found" in output


def test_format_report_includes_alert_title():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "Test alert" in output


def test_format_report_includes_rca_sections():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "## Summary" in output
    assert "## Root Cause (Hypothesis)" in output
    assert "## Prevention / Follow-ups" in output


def test_format_report_includes_similar_section():
    output = format_report(SAMPLE_DRAFT, SAMPLE_SIMILAR, total_searched=10)
    assert "## Similar Past Incidents" in output
    assert "INC-0001" in output


def test_format_report_empty_similar_shows_hint():
    output = format_report(SAMPLE_DRAFT, [], total_searched=0)
    assert "incident-intel seed" in output
