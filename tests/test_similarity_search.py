import pytest

from incident_intel.core.ingestor import ingest_incidents
from incident_intel.core.similarity_search import find_similar_incidents


def test_find_similar_returns_top_k(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    results = find_similar_incidents(
        "Redis memory issue causing service timeout",
        in_memory_collection,
        top_k=2,
    )
    assert len(results) == 2


def test_find_similar_returns_expected_metadata_keys(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    results = find_similar_incidents("Redis OOM", in_memory_collection, top_k=1)
    assert len(results) == 1
    meta = results[0]
    assert "id" in meta
    assert "title" in meta
    assert "severity" in meta
    assert "date" in meta
    assert "root_cause" in meta
    assert "resolution" in meta


def test_find_similar_returns_empty_list_when_collection_empty(in_memory_collection):
    results = find_similar_incidents("any description", in_memory_collection, top_k=3)
    assert results == []


def test_find_similar_clamps_top_k_to_collection_size(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents[:2], in_memory_collection)
    results = find_similar_incidents("memory issue", in_memory_collection, top_k=10)
    assert len(results) == 2
