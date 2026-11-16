"""DB-less tests for the Celery beat schedule."""

from celery_app import celery_app


def _fields(entry):
    s = entry["schedule"]
    return s.minute, s.hour, s.day_of_week


def test_decay_runs_daily_at_0300():
    entry = celery_app.conf.beat_schedule["decay-memories-daily"]
    assert entry["task"] == "decay_memories_task"
    assert _fields(entry) == ({0}, {3}, set(range(7)))


def test_consolidation_runs_sunday_0400():
    entry = celery_app.conf.beat_schedule["consolidate-memories-weekly"]
    assert entry["task"] == "consolidate_memories_task"
    assert _fields(entry) == ({0}, {4}, {0})
