"""Tests for ghost eviction: circle-agnostic deduplication."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repowire.config.models import AgentType, Config
from repowire.daemon.peer_registry import PeerRegistry
from repowire.protocol.peers import Peer, PeerStatus


def _make_peer(
    peer_id: str = "repow-dev-abc12345",
    display_name: str = "myproject",
    status: PeerStatus = PeerStatus.ONLINE,
    backend: AgentType = AgentType.CLAUDE_CODE,
    circle: str = "dev",
) -> Peer:
    return Peer(
        peer_id=peer_id,
        display_name=display_name,
        path="/tmp/test",
        machine="test",
        backend=backend,
        circle=circle,
        status=status,
    )


def _make_manager() -> PeerRegistry:
    config = Config()
    router = MagicMock()
    return PeerRegistry(
        config=config,
        message_router=router,
        query_tracker=MagicMock(),
        transport=MagicMock(),
    )


class TestGhostEvictionCrossCircle:
    @pytest.fixture
    def manager(self):
        return _make_manager()

    async def test_evict_ghost_cross_circle(self, manager):
        """Registering same (display_name, backend) with different circle evicts the old peer."""
        # Register via "tmux-session" circle (simulating hook transport)
        peer_id_1 = await manager.allocate_and_register(
            display_name="agent1",
            circle="tmux-session",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        # Register same name via "default" circle (simulating channel transport)
        peer_id_2 = await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        # Should be only 1 peer
        peers = await manager.get_all_peers()
        agent1_peers = [p for p in peers if p.display_name == "agent1"]
        assert len(agent1_peers) == 1
        assert agent1_peers[0].circle == "default"

        # Old peer should be gone
        old = await manager.get_peer(peer_id_1)
        assert old is None or old.peer_id == peer_id_2

    async def test_evict_ghost_same_circle(self, manager):
        """Same-circle duplicate still produces exactly 1 peer (existing behavior)."""
        await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )
        await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        peers = await manager.get_all_peers()
        agent1_peers = [p for p in peers if p.display_name == "agent1"]
        assert len(agent1_peers) == 1

    async def test_evict_ghost_cleans_mapping(self, manager):
        """Cross-circle re-registration reuses mapping and updates circle."""
        peer_id_1 = await manager.allocate_and_register(
            display_name="agent1",
            circle="old-circle",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )
        assert peer_id_1 in manager._mappings

        peer_id_2 = await manager.allocate_and_register(
            display_name="agent1",
            circle="new-circle",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        # Mapping is reused (same session_id), circle updated in place
        assert peer_id_1 == peer_id_2
        assert peer_id_1 in manager._mappings
        assert manager._mappings[peer_id_1].circle == "new-circle"
        assert len(manager._mappings) == 1

    async def test_mapping_reused_across_circles(self, manager):
        """Same (display_name, backend) reuses session_id even with different circle."""
        peer_id_1 = await manager.allocate_and_register(
            display_name="agent1",
            circle="old-circle",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        peer_id_2 = await manager.allocate_and_register(
            display_name="agent1",
            circle="new-circle",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )

        # With relaxed mapping lookup, the second registration finds the
        # existing mapping by (display_name, backend) — but ghost eviction
        # deletes the old mapping and peer. The new peer gets a fresh mapping.
        # The key assertion: only 1 peer exists with the new circle.
        peers = await manager.get_all_peers()
        agent1_peers = [p for p in peers if p.display_name == "agent1"]
        assert len(agent1_peers) == 1
        assert agent1_peers[0].circle == "new-circle"

    async def test_mapping_different_backend_not_reused(self, manager):
        """Different backends get separate session_ids even with same display_name."""
        peer_id_1 = await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )
        peer_id_2 = await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.OPENCODE,
            path="/tmp/project",
        )

        assert peer_id_1 != peer_id_2
        assert peer_id_1 in manager._mappings
        assert peer_id_2 in manager._mappings

    async def test_different_backend_not_evicted(self, manager):
        """Peers with same name but different backend are not evicted."""
        await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.CLAUDE_CODE,
            path="/tmp/project",
        )
        await manager.allocate_and_register(
            display_name="agent1",
            circle="default",
            backend=AgentType.OPENCODE,
            path="/tmp/project",
        )

        peers = await manager.get_all_peers()
        agent1_peers = [p for p in peers if p.display_name == "agent1"]
        assert len(agent1_peers) == 2
