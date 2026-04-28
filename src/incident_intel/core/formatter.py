from typing import Any, Dict, List

from incident_intel.models import RCADraft


def format_similar_incidents(
    similar: List[Dict[str, Any]], total_searched: int
) -> str:
    """Format similar incidents as a markdown section.

    Returns a seed hint if the list is empty.
    """
    if not similar:
        return "> No similar incidents found — run `incident-intel seed` to load demo data.\n"

    lines = ["## Similar Past Incidents\n"]
    for i, meta in enumerate(similar, 1):
        link_part = (
            f" · [{meta['id']}]({meta['link']})" if meta.get("link") else ""
        )
        lines.append(
            f"{i}. **[{meta['id']}] {meta['title']}**"
            f" — {meta['severity']} · {meta['date']}{link_part}"
        )
        lines.append(f"   Root cause: {meta['root_cause']}")
        lines.append(f"   Resolution: {meta['resolution']}\n")

    lines.append(f"> Searched {total_searched} past incidents · Top {len(similar)} shown")
    return "\n".join(lines)


def format_report(
    draft: RCADraft,
    similar: List[Dict[str, Any]],
    total_searched: int,
) -> str:
    """Assemble the full triage report: header + RCA + similar incidents."""
    header = (
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
    )
    similar_section = format_similar_incidents(similar, total_searched)
    return f"{header}{draft.raw_markdown}\n\n---\n\n{similar_section}"
