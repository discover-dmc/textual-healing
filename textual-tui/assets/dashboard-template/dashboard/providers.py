"""Command palette provider. Ctrl+P also switches themes for free (built in)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.command import DiscoveryHit, Hit, Hits, Provider

if TYPE_CHECKING:
    from dashboard.app import DashboardApp


class DashboardCommands(Provider):
    def _commands(self) -> list[tuple[str, object, str]]:
        app: DashboardApp = self.app  # type: ignore[assignment]
        return [
            ("Toggle pause", app.action_toggle_pause, "Pause or resume auto refresh"),
            ("Refresh now", app.action_refresh, "Fetch data immediately"),
            ("Clear log", app.action_clear_log, "Empty the event log"),
        ]

    async def discover(self) -> Hits:
        for name, callback, help_text in self._commands():
            yield DiscoveryHit(name, callback, help=help_text)  # type: ignore[arg-type]

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback, help_text in self._commands():
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), callback, help=help_text)  # type: ignore[arg-type]
