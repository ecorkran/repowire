"""Tests for hook installer (channel mode cleanup, full mode installation)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from repowire.installers.claude_code import install_hooks


def _with_temp_settings(fn):
    """Run fn with CLAUDE_SETTINGS pointing to a temp file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        tmp = Path(f.name)
    with patch("repowire.installers.claude_code.CLAUDE_SETTINGS", tmp):
        try:
            fn(tmp)
        finally:
            tmp.unlink(missing_ok=True)


def _read_hooks(tmp: Path) -> dict:
    return json.loads(tmp.read_text()).get("hooks", {})


class TestChannelModeCleanup:
    def test_channel_mode_removes_legacy_hooks(self):
        """Installing full mode then channel mode should leave only Stop."""
        def run(tmp: Path):
            install_hooks(channel_mode=False)
            hooks_before = _read_hooks(tmp)
            assert "SessionStart" in hooks_before
            assert "Notification" in hooks_before

            install_hooks(channel_mode=True)
            hooks_after = _read_hooks(tmp)
            assert sorted(hooks_after.keys()) == ["Stop"]

        _with_temp_settings(run)

    def test_channel_mode_idempotent(self):
        """Running channel mode install twice produces identical results."""
        def run(tmp: Path):
            install_hooks(channel_mode=True)
            first = tmp.read_text()

            install_hooks(channel_mode=True)
            second = tmp.read_text()

            assert first == second

        _with_temp_settings(run)

    def test_channel_mode_no_legacy_hooks_present(self):
        """Channel mode on clean settings installs only Stop."""
        def run(tmp: Path):
            install_hooks(channel_mode=True)
            hooks = _read_hooks(tmp)
            assert sorted(hooks.keys()) == ["Stop"]

        _with_temp_settings(run)

    def test_channel_mode_preserves_non_repowire_hooks(self):
        """Non-repowire hooks on legacy events survive channel mode cleanup."""
        def run(tmp: Path):
            # Pre-populate with repowire + non-repowire hooks on SessionStart
            settings = {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "repowire hook session"}]},
                        {"hooks": [{"type": "command", "command": "other-tool hook start"}]},
                    ],
                    "UserPromptSubmit": [
                        {"hooks": [{"type": "command", "command": "repowire hook prompt"}]},
                    ],
                }
            }
            tmp.write_text(json.dumps(settings))

            install_hooks(channel_mode=True)
            hooks = _read_hooks(tmp)

            # SessionStart should keep the non-repowire entry
            assert "SessionStart" in hooks
            assert len(hooks["SessionStart"]) == 1
            assert hooks["SessionStart"][0]["hooks"][0]["command"] == "other-tool hook start"

            # UserPromptSubmit had only repowire → removed entirely
            assert "UserPromptSubmit" not in hooks

            # Stop should be added
            assert "Stop" in hooks

        _with_temp_settings(run)


class TestFullModeInstall:
    def test_full_mode_installs_all_hooks(self):
        """Full mode installs all 5 hook events."""
        def run(tmp: Path):
            install_hooks(channel_mode=False)
            hooks = _read_hooks(tmp)
            expected = {"Notification", "SessionEnd", "SessionStart", "Stop", "UserPromptSubmit"}
            assert set(hooks.keys()) == expected

        _with_temp_settings(run)
