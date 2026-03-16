"""Tests for QueryTracker — correlation ID tracking and query lifecycle."""

import asyncio

import pytest

from repowire.daemon.query_tracker import QueryTracker
from repowire.protocol.errors import PeerDisconnectedError


@pytest.fixture
def tracker():
    return QueryTracker()


class TestRegisterAndResolve:
    def test_register_returns_correlation_id(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        assert isinstance(cid, str)
        assert len(cid) > 0

    def test_register_custom_id(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?", correlation_id="custom-123")
        assert cid == "custom-123"

    def test_get_future(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        future = tracker.get_future(cid)
        assert future is not None
        assert not future.done()

    def test_get_future_unknown(self, tracker):
        assert tracker.get_future("nonexistent") is None

    async def test_resolve_query(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        future = tracker.get_future(cid)
        assert tracker.resolve_query(cid, "hi!")
        assert future.result() == "hi!"

    def test_resolve_unknown(self, tracker):
        assert not tracker.resolve_query("nonexistent", "response")

    async def test_resolve_already_done(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        tracker.resolve_query(cid, "first")
        assert not tracker.resolve_query(cid, "second")

    def test_pending_count(self, tracker):
        assert tracker.get_pending_count() == 0
        tracker.register_query("a", "sid-b", "b", "q1")
        tracker.register_query("a", "sid-b", "b", "q2")
        assert tracker.get_pending_count() == 2

    def test_pending_to_peer(self, tracker):
        tracker.register_query("a", "sid-b", "b", "q1")
        tracker.register_query("a", "sid-c", "c", "q2")
        assert tracker.get_pending_to_peer("sid-b") == 1
        assert tracker.get_pending_to_peer("sid-c") == 1
        assert tracker.get_pending_to_peer("sid-x") == 0


class TestResolveOldest:
    async def test_resolves_oldest(self, tracker):
        cid1 = tracker.register_query("a", "sid-b", "b", "first")
        cid2 = tracker.register_query("a", "sid-b", "b", "second")
        f1 = tracker.get_future(cid1)
        f2 = tracker.get_future(cid2)

        assert tracker.resolve_oldest_query("sid-b", "response")
        assert f1.result() == "response"
        assert not f2.done()

    def test_no_pending(self, tracker):
        assert not tracker.resolve_oldest_query("sid-b", "response")


class TestResolveError:
    async def test_resolve_with_error(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        future = tracker.get_future(cid)
        err = ValueError("something broke")
        assert tracker.resolve_query_error(cid, err)
        with pytest.raises(ValueError, match="something broke"):
            future.result()

    def test_resolve_error_unknown(self, tracker):
        assert not tracker.resolve_query_error("nonexistent", ValueError("x"))


class TestCancelQueries:
    async def test_cancel_all_for_peer(self, tracker):
        cid1 = tracker.register_query("a", "sid-b", "b", "q1")
        cid2 = tracker.register_query("a", "sid-b", "b", "q2")
        f1 = tracker.get_future(cid1)
        f2 = tracker.get_future(cid2)

        cancelled = tracker.cancel_queries_to_peer("sid-b")
        assert cancelled == 2
        with pytest.raises(PeerDisconnectedError):
            f1.result()
        with pytest.raises(PeerDisconnectedError):
            f2.result()

    def test_cancel_no_queries(self, tracker):
        assert tracker.cancel_queries_to_peer("sid-x") == 0

    async def test_cancel_only_target_peer(self, tracker):
        tracker.register_query("a", "sid-b", "b", "q1")
        cid2 = tracker.register_query("a", "sid-c", "c", "q2")
        f2 = tracker.get_future(cid2)

        tracker.cancel_queries_to_peer("sid-b")
        assert not f2.done()  # sid-c queries unaffected


class TestCleanup:
    def test_cleanup_removes_query(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        assert tracker.get_pending_count() == 1
        tracker.cleanup_query(cid)
        assert tracker.get_pending_count() == 0
        assert tracker.get_future(cid) is None

    def test_cleanup_unknown(self, tracker):
        tracker.cleanup_query("nonexistent")  # no error

    async def test_resolve_cleans_up(self, tracker):
        cid = tracker.register_query("a", "sid-b", "b", "hello?")
        tracker.resolve_query(cid, "hi!")
        assert tracker.get_pending_count() == 0
        assert tracker.get_pending_to_peer("sid-b") == 0
