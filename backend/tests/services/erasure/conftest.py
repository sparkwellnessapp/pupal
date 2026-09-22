import pytest

from tests.services.erasure.fakes import FakeStorage
from tests.services.erasure.seed import BUCKET, drop_graph, seed_graph


@pytest.fixture
async def graph():
    g = await seed_graph()
    try:
        yield g
    finally:
        await drop_graph(g)


@pytest.fixture
def store(graph) -> FakeStorage:
    """The bucket, holding exactly the graph's objects."""
    return FakeStorage(graph.objects)


def guarded(store: FakeStorage):
    """The purge's view of storage: every call validated first (PRV-11), the
    known-bucket set being the test bucket alone."""
    from app.services.erasure import GuardedStorage

    return GuardedStorage(store, known_buckets=frozenset({BUCKET}))
