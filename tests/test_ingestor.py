import json
import tempfile
from pathlib import Path

import pytest

from incident_intel.core.ingestor import ingest_incidents, load_from_file
from incident_intel.models import Incident


def test_ingest_adds_incidents(in_memory_collection, sample_incidents):
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 3
    assert in_memory_collection.count() == 3


def test_ingest_is_idempotent(in_memory_collection, sample_incidents):
    ingest_incidents(sample_incidents, in_memory_collection)
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 0  # no new insertions
    assert in_memory_collection.count() == 3  # same total


def test_ingest_partial_duplicates(in_memory_collection, sample_incidents):
    ingest_incidents([sample_incidents[0]], in_memory_collection)
    count = ingest_incidents(sample_incidents, in_memory_collection)
    assert count == 2  # only 2 new


def test_load_from_file(in_memory_collection):
    incidents = [
        {
            "id": "INC-TEST-1",
            "title": "Test incident",
            "severity": "P2",
            "date": "2024-01-01",
            "root_cause": "Test root cause",
            "resolution": "Test resolution",
        }
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(incidents, f)
        tmp_path = f.name

    count = load_from_file(tmp_path, in_memory_collection)
    assert count == 1
    assert in_memory_collection.count() == 1


def test_load_from_file_skips_malformed_records(in_memory_collection):
    incidents = [
        {"id": "INC-GOOD-1", "title": "Good", "severity": "P1", "date": "2024-01-01",
         "root_cause": "cause", "resolution": "fix"},
        {"bad": "record_missing_required_fields"},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(incidents, f)
        tmp_path = f.name

    count = load_from_file(tmp_path, in_memory_collection)
    assert count == 1  # only the good record
