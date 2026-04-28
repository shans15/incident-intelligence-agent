from mcp.server.fastmcp import FastMCP

from incident_intel.config import get_config
from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.core.ingestor import get_collection
from incident_intel.core.rca_generator import generate_rca
from incident_intel.core.similarity_search import find_similar_incidents

mcp = FastMCP("incident-intel")


@mcp.tool()
def triage_incident(alert: str) -> str:
    """Full incident triage: generates a structured RCA draft and finds the top 3
    similar past incidents from the knowledge base. Returns unified markdown
    ready to paste into Jira or Slack.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """
    config = get_config()
    collection = get_collection(config.chroma_persist_dir)
    draft = generate_rca(alert, config.api_key, config.model)
    similar = find_similar_incidents(alert, collection)
    return format_report(draft, similar, total_searched=collection.count())


@mcp.tool()
def analyze_incident(alert: str) -> str:
    """Generate a structured RCA draft from an incident alert using Claude.
    Does not search the knowledge base.

    Args:
        alert: Raw PagerDuty webhook JSON string or plain text incident description.
    """
    config = get_config()
    draft = generate_rca(alert, config.api_key, config.model)
    return (
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
        f"{draft.raw_markdown}"
    )


@mcp.tool()
def find_similar(description: str, top_k: int = 3) -> str:
    """Search the local incident knowledge base for similar past incidents.
    Returns top-k results with title, severity, date, root cause, and link.

    Args:
        description: Plain text description of the incident.
        top_k: Number of similar incidents to return (default: 3).
    """
    config = get_config()
    collection = get_collection(config.chroma_persist_dir)
    similar = find_similar_incidents(description, collection, top_k)
    return format_similar_incidents(similar, total_searched=collection.count())


if __name__ == "__main__":
    mcp.run()
