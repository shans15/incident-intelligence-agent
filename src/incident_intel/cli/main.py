import sys
from pathlib import Path

import click
import structlog

from incident_intel.config import TriageError, get_config
from incident_intel.core.formatter import format_report, format_similar_incidents
from incident_intel.core.ingestor import get_collection, load_from_file
from incident_intel.core.rca_generator import generate_rca
from incident_intel.core.similarity_search import find_similar_incidents

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(20)  # INFO
)
logger = structlog.get_logger()


@click.group()
def cli():
    """Incident Intelligence Agent — triage incidents and generate RCA drafts."""
    pass


@cli.command()
@click.option("--alert", default=None, help="Raw alert text or PagerDuty JSON string")
@click.option(
    "--alert-file",
    default=None,
    type=click.Path(exists=True),
    help="Path to alert JSON file",
)
def triage(alert, alert_file):
    """Generate RCA draft + find similar past incidents."""
    alert_text = _resolve_alert(alert, alert_file)
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    draft = generate_rca(alert_text, config.api_key, config.model)
    similar = find_similar_incidents(alert_text, collection)
    click.echo(format_report(draft, similar, total_searched=collection.count()))


@cli.command()
@click.option("--alert", required=True, help="Raw alert text or PagerDuty JSON string")
def analyze(alert):
    """Generate a structured RCA draft only (no similarity search)."""
    config = _load_config()
    draft = generate_rca(alert, config.api_key, config.model)
    click.echo(
        f"# Incident Triage Report\n\n"
        f"**Alert:** {draft.alert_title}\n"
        f"**Generated:** {draft.generated_at}\n\n"
        f"---\n\n"
        f"{draft.raw_markdown}"
    )


@cli.command("find-similar")
@click.option("--description", required=True, help="Incident description to search for")
@click.option("--top-k", default=3, show_default=True, help="Number of results to return")
def find_similar(description, top_k):
    """Search the knowledge base for similar past incidents."""
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    similar = find_similar_incidents(description, collection, top_k)
    click.echo(format_similar_incidents(similar, total_searched=collection.count()))


@cli.command()
def seed():
    """Load the bundled demo incidents into the knowledge base."""
    config = _load_config()
    # data/ is at the project root: src/incident_intel/cli/main.py is 4 levels deep
    data_path = Path(__file__).parent.parent.parent.parent / "data" / "demo_incidents.json"
    if not data_path.exists():
        click.echo(f"Demo data not found at {data_path}", err=True)
        sys.exit(1)
    collection = get_collection(config.chroma_persist_dir)
    count = load_from_file(str(data_path), collection)
    click.echo(f"Seeded {count} new incidents. Knowledge base now has {collection.count()} total.")


@cli.command()
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True),
    help="Path to a JSON file of incidents to ingest",
)
def ingest(file_path):
    """Ingest incidents from a JSON file into the knowledge base."""
    config = _load_config()
    collection = get_collection(config.chroma_persist_dir)
    count = load_from_file(file_path, collection)
    click.echo(f"Ingested {count} new incidents. Knowledge base now has {collection.count()} total.")


def _load_config():
    try:
        return get_config()
    except TriageError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)


def _resolve_alert(alert, alert_file):
    if alert_file:
        with open(alert_file) as f:
            return f.read()
    if alert:
        return alert
    click.echo("Error: provide --alert TEXT or --alert-file PATH", err=True)
    sys.exit(1)
