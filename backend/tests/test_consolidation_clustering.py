"""DB-less tests for consolidation clustering helpers."""

import pytest

from app.memory.consolidation import _cluster_memories, _cosine_similarity
from types import SimpleNamespace


def _m(name, vec):
    return SimpleNamespace(name=name, embedding=vec)


def test_cosine_similarity():
    assert _cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert _cosine_similarity([0, 0], [1, 0]) == 0.0


def test_clusters_similar_vectors_and_separates_distinct():
    a1, a2, a3 = _m("a1", [1, 0, 0]), _m("a2", [0.99, 0.05, 0]), _m("a3", [1, 0.1, 0])
    b1, b2 = _m("b1", [0, 1, 0]), _m("b2", [0.02, 1, 0])
    c = _m("c", [0, 0, 1])
    clusters = _cluster_memories([a1, b1, a2, c, b2, a3])
    names = sorted(sorted(m.name for m in cl) for cl in clusters)
    assert names == [["a1", "a2", "a3"], ["b1", "b2"], ["c"]]


def test_empty_input():
    assert _cluster_memories([]) == []
