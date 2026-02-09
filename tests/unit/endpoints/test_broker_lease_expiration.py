"""Tests for broker lease expiration functionality."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import broker
from app.models.broker import SubmissionAttempt, SubmissionEvent
from app.models.experiment import ExperimentSubmission
from app.models.organism import Organism
from app.models.project import ProjectSubmission
from app.models.read import ReadSubmission
from app.models.sample import Sample, SampleSubmission


class FakeQuery:
    def __init__(self, items, filters=None):
        self.items = list(items)
        self.filters = filters or []

    def filter(self, *conditions, **__):
        # Apply basic filtering for expired leases
        filtered = []
        now = datetime.now(timezone.utc)

        for item in self.items:
            should_include = True

            # Convert conditions to strings for pattern matching
            cond_strs = [str(c) for c in conditions]

            # Check status filter - must match if specified
            has_status_filter = any("status" in s and "==" in s for s in cond_strs)
            if has_status_filter and hasattr(item, "status"):
                status_match = False
                for cond_str in cond_strs:
                    if "status" in cond_str and "==" in cond_str:
                        if "submitting" in cond_str and item.status == "submitting":
                            status_match = True
                        elif "draft" in cond_str and item.status == "draft":
                            status_match = True
                        elif "processing" in cond_str and item.status == "processing":
                            status_match = True
                if not status_match:
                    should_include = False

            # Check lock_expires_at IS NOT NULL filter
            has_isnot_null = any(
                "lock_expires_at" in s and "IS NOT" in s.upper() for s in cond_strs
            )
            if has_isnot_null and hasattr(item, "lock_expires_at"):
                if item.lock_expires_at is None:
                    should_include = False

            # Check lock_expires_at <= now filter (for expiration)
            has_expiry_filter = any("lock_expires_at" in s and "<=" in s for s in cond_strs)
            if has_expiry_filter and should_include and hasattr(item, "lock_expires_at"):
                if item.lock_expires_at is None or item.lock_expires_at > now:
                    should_include = False

            if should_include:
                filtered.append(item)

        return FakeQuery(filtered, self.filters + list(conditions))

    def with_for_update(self, *_, **__):
        return self

    def join(self, *_, **__):
        return self

    def all(self):
        return list(self.items)

    def first(self):
        return self.items[0] if self.items else None

    def limit(self, *_):
        return self

    def offset(self, *_):
        return self

    def order_by(self, *_):
        return self

    def count(self):
        return len(self.items)

    def group_by(self, *_):
        return self

    def isnot(self, *_):
        # Return self to continue chaining, filtering happens in filter()
        return self

    def distinct(self):
        return self

    def subquery(self):
        return self


class FakeSession:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.added = []
        self.deleted = []
        self.executed = []
        self.committed = False
        self.flushed = False

    def query(self, *models):
        # Handle both single model and multiple arguments (for complex queries)
        if len(models) == 1:
            model = models[0]
            return FakeQuery(self.mapping.get(model, []))
        else:
            # For complex queries with multiple columns, return empty query
            return FakeQuery([])

    def add(self, obj):
        # Ensure IDs exist for rows that expect them
        if getattr(obj, "id", None) is None:
            try:
                obj.id = uuid4()
            except Exception:
                pass
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def execute(self, stmt):
        self.executed.append(stmt)


def test_expire_stale_leases_resets_expired_samples():
    """Test that expire_stale_leases resets expired sample submissions to draft."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)
    att_id = uuid4()

    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )
    s2 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=now,
        lock_expires_at=now + timedelta(minutes=10),  # Not expired
    )

    db = FakeSession({SampleSubmission: [s1, s2]})

    result = broker.expire_stale_leases(db)

    # Only s1 should be expired
    assert result["samples"] == 1
    assert s1.status == "draft"
    assert s1.attempt_id is None
    assert s1.lock_acquired_at is None
    assert s1.lock_expires_at is None

    # s2 should remain unchanged
    assert s2.status == "submitting"
    assert s2.attempt_id == att_id

    # Should have added a SubmissionEvent
    events = [obj for obj in db.added if isinstance(obj, SubmissionEvent)]
    assert len(events) == 1
    assert events[0].action == "expired"
    assert events[0].entity_type == "sample"


def test_expire_stale_leases_resets_all_entity_types():
    """Test that expire_stale_leases handles all entity types."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)
    att_id = uuid4()

    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )
    e1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )
    r1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )
    p1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    db = FakeSession(
        {
            SampleSubmission: [s1],
            ExperimentSubmission: [e1],
            ReadSubmission: [r1],
            ProjectSubmission: [p1],
        }
    )

    result = broker.expire_stale_leases(db)

    assert result["samples"] == 1
    assert result["experiments"] == 1
    assert result["reads"] == 1
    assert result["projects"] == 1

    for item in [s1, e1, r1, p1]:
        assert item.status == "draft"
        assert item.attempt_id is None


def test_expire_stale_leases_updates_attempt_status():
    """Test that expire_stale_leases updates SubmissionAttempt status to expired."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    att1 = SimpleNamespace(
        id=uuid4(),
        status="processing",
        lock_expires_at=past,
    )
    att2 = SimpleNamespace(
        id=uuid4(),
        status="processing",
        lock_expires_at=now + timedelta(minutes=10),  # Not expired
    )

    db = FakeSession({SubmissionAttempt: [att1, att2]})

    broker.expire_stale_leases(db)

    # att1 should be marked as expired
    assert att1.status == "expired"

    # att2 should remain processing
    assert att2.status == "processing"


def test_expire_stale_leases_no_expired_items():
    """Test that expire_stale_leases handles case with no expired items."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(minutes=10)

    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=uuid4(),
        lock_acquired_at=now,
        lock_expires_at=future,
    )

    db = FakeSession({SampleSubmission: [s1]})

    result = broker.expire_stale_leases(db)

    assert result["samples"] == 0
    assert result["experiments"] == 0
    assert result["reads"] == 0
    assert result["projects"] == 0

    # s1 should remain unchanged
    assert s1.status == "submitting"


def test_expire_leases_endpoint():
    """Test the POST /leases/expire endpoint."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=uuid4(),
        lock_acquired_at=past,
        lock_expires_at=past,
    )
    e1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=uuid4(),
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    db = FakeSession(
        {
            SampleSubmission: [s1],
            ExperimentSubmission: [e1],
        }
    )

    result = broker.expire_leases(db=db)

    assert result["expired_counts"]["samples"] == 1
    assert result["expired_counts"]["experiments"] == 1
    assert result["total_expired"] == 2
    assert "Expired 2 stale leases" in result["message"]


def test_expire_stale_leases_called_with_mixed_statuses():
    """Test that expire_stale_leases only affects submitting items with expired leases."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)
    att_id = uuid4()

    # Expired submitting item - should be reset
    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att_id,
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    # Draft item - should not be affected
    s2 = SimpleNamespace(
        id=uuid4(),
        status="draft",
        attempt_id=None,
        lock_acquired_at=None,
        lock_expires_at=None,
    )

    db = FakeSession({SampleSubmission: [s1, s2]})

    result = broker.expire_stale_leases(db)

    # Only s1 should be expired
    assert result["samples"] == 1
    assert s1.status == "draft"
    assert s1.attempt_id is None
    assert s2.status == "draft"  # unchanged


def test_expire_stale_leases_with_null_lock_expires_at():
    """Test that expire_stale_leases ignores items with null lock_expires_at."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    # Item with null lock_expires_at should not be expired
    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=uuid4(),
        lock_acquired_at=None,
        lock_expires_at=None,  # Null expiry
    )

    # Item with expired lock should be expired
    s2 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=uuid4(),
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    db = FakeSession({SampleSubmission: [s1, s2]})

    result = broker.expire_stale_leases(db)

    # Only s2 should be expired (has expired lock_expires_at)
    assert result["samples"] == 1
    assert s1.status == "submitting"  # s1 unchanged
    assert s2.status == "draft"  # s2 expired


def test_expire_stale_leases_multiple_attempts():
    """Test that expire_stale_leases handles multiple expired attempts correctly."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=5)

    att1 = uuid4()
    att2 = uuid4()

    # Items from different attempts, all expired
    s1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att1,
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    s2 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att2,
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    e1 = SimpleNamespace(
        id=uuid4(),
        status="submitting",
        attempt_id=att1,
        lock_acquired_at=past,
        lock_expires_at=past,
    )

    db = FakeSession(
        {
            SampleSubmission: [s1, s2],
            ExperimentSubmission: [e1],
        }
    )

    result = broker.expire_stale_leases(db)

    # All items should be expired
    assert result["samples"] == 2
    assert result["experiments"] == 1

    # Verify all items were reset
    for item in [s1, s2, e1]:
        assert item.status == "draft"
        assert item.attempt_id is None
        assert item.lock_acquired_at is None
        assert item.lock_expires_at is None
