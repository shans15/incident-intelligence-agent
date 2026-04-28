import json
from pathlib import Path
from typing import List

import chromadb
import structlog

from incident_intel.models import Incident

logger = structlog.get_logger()


def get_collection(persist_dir: str) -> chromadb.Collection:
    """Return the ChromaDB incidents collection, creating it if needed."""
    client = chromadb.PersistentClient(path=persist_dir)
    return client.get_or_create_collection("incidents_v1")


def ingest_incidents(
    incidents: List[Incident], collection: chromadb.Collection
) -> int:
    """Insert incidents into ChromaDB, skipping duplicates.

    Returns the count of newly inserted incidents.
    """
    inserted = 0
    for incident in incidents:
        existing = collection.get(ids=[incident.id])
        if existing["ids"]:
            logger.info("skipping_duplicate", id=incident.id)
            continue

        document = f"{incident.title}\n{incident.summary}\n{incident.root_cause}"
        collection.add(
            ids=[incident.id],
            documents=[document],
            metadatas=[
                {
                    "id": incident.id,
                    "title": incident.title,
                    "severity": incident.severity,
                    "date": incident.date,
                    "root_cause": incident.root_cause,
                    "resolution": incident.resolution,
                    "link": incident.link,
                }
            ],
        )
        logger.info("ingested_incident", id=incident.id, title=incident.title)
        inserted += 1

    return inserted


def load_from_file(file_path: str, collection: chromadb.Collection) -> int:
    """Load incidents from a JSON file and ingest into ChromaDB.

    Skips malformed records and logs errors per record.
    Returns count of newly inserted incidents.
    """
    path = Path(file_path)
    with open(path) as f:
        data = json.load(f)

    incidents = []
    for record in data:
        try:
            incidents.append(Incident(**record))
        except Exception as e:
            logger.error("malformed_record", error=str(e), record=record)

    return ingest_incidents(incidents, collection)
