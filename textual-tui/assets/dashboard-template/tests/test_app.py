from __future__ import annotations

from textual.widgets import DataTable

from dashboard.app import DashboardApp, HelpScreen
from dashboard.source import FakeSource, Item

SLOW = 3600.0  # disable the timer; tests drive refresh explicitly


class StaticSource:
    def __init__(self, items: list[Item]) -> None:
        self._items = items

    async def fetch(self) -> list[Item]:
        return self._items

    def history(self, key: str) -> list[float]:
        return [1.0, 2.0, 3.0]


async def test_table_fills_and_first_row_is_selected() -> None:
    app = DashboardApp(FakeSource(n=5), interval=SLOW)
    async with app.run_test(size=(100, 30)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        table = app.query_one("#items", DataTable)
        assert table.row_count == 5
        assert table.cursor_row == 0


async def test_refresh_updates_in_place_and_keeps_cursor() -> None:
    app = DashboardApp(FakeSource(n=5), interval=SLOW)
    async with app.run_test(size=(100, 30)) as pilot:
        await app.workers.wait_for_complete()
        table = app.query_one("#items", DataTable)
        await pilot.press("down", "down")
        before_value = table.get_cell("svc-00", "value").plain
        await pilot.press("r")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert table.cursor_row == 2
        assert table.row_count == 5
        assert table.get_cell("svc-00", "value").plain != before_value


async def test_rows_that_disappear_are_removed() -> None:
    items = [Item("a", "a", 1.0, 0.0, "ok"), Item("b", "b", 2.0, 0.0, "ok")]
    app = DashboardApp(StaticSource(items), interval=SLOW)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        app.apply(items[:1])
        await pilot.pause()
        assert app.query_one("#items", DataTable).row_count == 1


async def test_help_modal_opens_and_closes_with_keys() -> None:
    app = DashboardApp(FakeSource(), interval=SLOW)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        assert not isinstance(app.screen, HelpScreen)


async def test_pause_stops_the_timer_refresh() -> None:
    app = DashboardApp(FakeSource(n=2), interval=0.05)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        table = app.query_one("#items", DataTable)
        await pilot.press("p")
        assert app.paused and app.sub_title == "paused"
        frozen = table.get_cell("svc-00", "value").plain
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        assert table.get_cell("svc-00", "value").plain == frozen
        await pilot.press("p")
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        assert table.get_cell("svc-00", "value").plain != frozen


async def test_narrow_terminal_hides_the_detail_pane() -> None:
    app = DashboardApp(FakeSource(), interval=SLOW)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.query_one("#detail").display is False
    async with DashboardApp(FakeSource(), interval=SLOW).run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert pilot.app.query_one("#detail").display is True


async def test_untrusted_names_are_rendered_literally() -> None:
    evil = Item("x", "[red]boom[/red]", 1.0, 0.0, "ok")
    app = DashboardApp(StaticSource([evil]), interval=SLOW)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.query_one("#items", DataTable).get_cell("x", "name").plain == "[red]boom[/red]"


async def test_theme_key_cycles_theme() -> None:
    app = DashboardApp(FakeSource(), interval=SLOW)
    async with app.run_test() as pilot:
        assert app.theme == "midnight"
        await pilot.press("t")
        assert app.theme != "midnight"


async def test_command_palette_lists_app_commands() -> None:
    app = DashboardApp(FakeSource(), interval=SLOW)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        assert type(app.screen).__name__ == "CommandPalette"
