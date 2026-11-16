"""DB-less tests for forgetting-engine math and SQL shape."""

import math

import pytest

from app.memory import forgetting
from app.memory.forgetting import ARCHIVE_THRESHOLD, decayed_importance


def test_exponential_decay_value():
    assert decayed_importance(1.0, 0.02, 10) == pytest.approx(math.exp(-0.2))


def test_core_never_decays():
    assert decayed_importance(0.8, 0.0, 10_000) == 0.8


def test_no_elapsed_time_no_change_and_negative_clamped():
    assert decayed_importance(0.5, 0.1, 0) == 0.5
    assert decayed_importance(0.5, 0.1, -5) == 0.5


def test_incremental_decay_does_not_compound():
    """Decaying per elapsed slice equals one decay over the total time."""

    stepwise = 1.0
    for _ in range(10):
        stepwise = decayed_importance(stepwise, 0.05, 1)
    assert stepwise == pytest.approx(decayed_importance(1.0, 0.05, 10))


def test_archive_threshold():
    assert ARCHIVE_THRESHOLD == 0.1
    assert decayed_importance(0.5, 0.02, 200) < ARCHIVE_THRESHOLD


def test_decay_sql_uses_last_decayed_at_and_skips_core():
    sql = str(forgetting._DECAY_SQL)
    assert "last_decayed_at" in sql
    assert "COALESCE(last_decayed_at, created_at)" in sql
    assert "type <> 'core'" in sql
    assert "archived = false" in sql
    assert "type <> 'core'" in str(forgetting._ARCHIVE_SQL)
