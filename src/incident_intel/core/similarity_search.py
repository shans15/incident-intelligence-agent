from typing import Any, Dict, List

import chromadb
import structlog

logger = structlog.get_logger()


def find_similar_incidents(
    description: str,
    collection: chromadb.Collection,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Query ChromaDB for incidents similar to the given description.

    Returns a list of metadata dicts. Returns empty list if collection is empty.
    """
    count = collection.count()
    if count == 0:
        logger.info("knowledge_base_empty")
        return []

    results = collection.query(
        query_texts=[description],
        n_results=min(top_k, count),
        include=["metadatas", "distances"],
    )

    metadatas = results["metadatas"][0] if results["metadatas"] else []
    logger.info("similarity_search_complete", found=len(metadatas), top_k=top_k)
    return metadatas
