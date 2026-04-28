import pytest
import chromadb
from incident_intel.models import Incident


@pytest.fixture
def sample_incidents():
    return [
        Incident(
            id="INC-0001",
            title="Redis OOM causing checkout timeouts",
            severity="P1",
            date="2024-11-15",
            root_cause="Memory limit not set on Redis; cache grew unbounded",
            resolution="Increased memory limit and added eviction policy",
            summary="Redis ran out of memory, causing checkout service to timeout",
        ),
        Incident(
            id="INC-0002",
            title="Database connection pool exhausted on orders service",
            severity="P1",
            date="2024-10-03",
            root_cause="Connection pool size too small for traffic spike",
            resolution="Increased pool size to 50; optimized two slow queries",
            summary="Orders service returned 503s after DB connection pool ran out",
        ),
        Incident(
            id="INC-0003",
            title="Memory leak in user-service causing OOM kills",
            severity="P2",
            date="2024-09-18",
            root_cause="Goroutine leak in session refresh loop",
            resolution="Rolled back offending PR; fixed goroutine leak",
            summary="user-service pods repeatedly OOM-killed by Kubernetes",
        ),
    ]


@pytest.fixture
def in_memory_collection():
    import uuid
    client = chromadb.EphemeralClient()
    name = f"incidents_{uuid.uuid4().hex}"
    collection = client.get_or_create_collection(name)
    yield collection
    client.delete_collection(name)
