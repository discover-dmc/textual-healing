"""Dashboard starter. Patterns worth copying:

- UI depends on a Source Protocol (dependency injection), so tests use FakeSource.
- DataTable rows are keyed and updated in place (no clear-and-refill): the cursor,
  scroll position and selection survive every refresh.
- Fetching runs in an exclusive worker: overlapping refreshes cancel the stale one.
- Untrusted text goes through rich.text.Text, never markup strings.
- Semantic theme variables in CSS, a custom Theme, and a non-color cue (glyph + sign).
- Modal help, command palette provider, HORIZONTAL_BREAKPOINTS, public methods for tests.
"""

from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import DataTable, Footer, Header, RichLog, Sparkline, Static
from textual.widgets.data_table import RowKey

from dashboard.providers import DashboardCommands
from dashboard.source import FakeSource, Item, Source

MIDNIGHT = Theme(
    name="midnight",
    primary="#7aa2f7",
    secondary="#bb9af7",
    accent="#e0af68",
    foreground="#c0caf5",
    background="#1a1b26",
    surface="#24283b",
    panel="#2f3549",
    success="#9ece6a",
    warning="#e0af68",
    error="#f7768e",
    dark=True,
)
THEME_CYCLE = ["midnight", "nord", "gruvbox", "tokyo-night", "textual-light"]
STATUS_GLYPH = {"ok": ("●", "green"), "warn": ("◐", "yellow"), "down": ("○", "red")}
COLUMNS = ("name", "value", "change", "status")


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,question_mark", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static("Keys", classes="title")
            yield Static(
                "up/down  move\nr  refresh now\np  pause or resume\nt  next theme\n"
                "ctrl+p  command palette\n?  this help\nq  quit"
            )


class DashboardApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("t", "next_theme", "Theme"),
        Binding("question_mark", "help", "Help"),
    ]
    COMMANDS = App.COMMANDS | {DashboardCommands}
    # Responsive layout: Textual toggles these classes on the Screen as the width changes.
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (80, "-wide")]

    paused = reactive(False)

    def __init__(self, source: Source | None = None, interval: float = 1.0) -> None:
        super().__init__()
        self._source: Source = source or FakeSource()
        self._interval = interval
        self._status: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="items", cursor_type="row", zebra_stripes=True)
            with Vertical(id="detail"):
                yield Static("", id="detail-title")
                yield Sparkline([], id="spark")
                yield RichLog(id="log", max_lines=500, wrap=True, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(MIDNIGHT)
        self.theme = "midnight"
        table = self.query_one("#items", DataTable)
        table.add_column("Name", key="name", width=14)
        table.add_column("Value", key="value", width=12)
        table.add_column("Change", key="change", width=12)
        table.add_column("St", key="status", width=3)
        table.focus()
        self.set_interval(self._interval, self._tick)
        self.action_refresh()

    # ---- data flow -----------------------------------------------------------------

    def _tick(self) -> None:
        if not self.paused:
            self.action_refresh()

    def action_refresh(self) -> None:
        self.load()

    @work(exclusive=True)
    async def load(self) -> None:
        self.apply(await self._source.fetch())

    def apply(self, items: list[Item]) -> None:
        """Merge items into the table by key. Public so tests can call it directly."""
        table = self.query_one("#items", DataTable)
        log = self.query_one("#log", RichLog)
        seen: set[str] = set()
        for it in items:
            seen.add(it.key)
            cells = (
                Text(it.name),  # Text, not str: markup in untrusted names stays literal
                Text(f"{it.value:,.2f}", justify="right"),
                Text(
                    f"{'▲' if it.change_pct >= 0 else '▼'} {it.change_pct:+.2f}%",
                    style="green" if it.change_pct >= 0 else "red",
                    justify="right",
                ),
                Text(*STATUS_GLYPH[it.status]),
            )
            if RowKey(it.key) in table.rows:
                for column, value in zip(COLUMNS, cells, strict=True):
                    table.update_cell(it.key, column, value)
            else:
                table.add_row(*cells, key=it.key)
            if it.status == "down" and self._status.get(it.key) != "down":
                log.write(Text(f"{it.name} went down ({it.change_pct:+.2f}%)"))
            self._status[it.key] = it.status
        for row_key in [rk for rk in table.rows if rk.value not in seen]:
            table.remove_row(row_key)
        self._show_detail()

    def _selected_key(self) -> str | None:
        table = self.query_one("#items", DataTable)
        if table.row_count == 0:
            return None
        return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value

    def _show_detail(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        self.query_one("#detail-title", Static).update(Text(key))
        self.query_one("#spark", Sparkline).data = self._source.history(key)

    @on(DataTable.RowHighlighted)
    def _row_highlighted(self) -> None:
        self._show_detail()

    # ---- actions -------------------------------------------------------------------

    def watch_paused(self, paused: bool) -> None:
        self.sub_title = "paused" if paused else ""

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_next_theme(self) -> None:
        i = THEME_CYCLE.index(self.theme) if self.theme in THEME_CYCLE else -1
        self.theme = THEME_CYCLE[(i + 1) % len(THEME_CYCLE)]

    def action_help(self) -> None:
        self.push_screen(HelpScreen())


def main() -> None:
    DashboardApp().run()


if __name__ == "__main__":
    main()
