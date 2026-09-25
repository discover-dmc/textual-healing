# Testing and verification

Read when: writing tests for a Textual app, debugging flaky async tests, snapshotting visuals, or letting an
agent verify a TUI. Verified on Textual 8.2.8 with pytest 9, pytest-socket 0.8, pytest-asyncio.

## 1. Setup

```toml
[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "pytest-textual-snapshot>=1.0", "textual-dev>=1.7"]

[tool.pytest.ini_options]
asyncio_mode = "auto"          # no @pytest.mark.asyncio on every test
testpaths = ["tests"]
# Using pytest-socket? Textual's headless run needs the asyncio self-pipe, which is a UNIX socket:
# addopts = "--disable-socket --allow-unix-socket"      (verified: run_test then needs no enable_socket marker)
```
Without pytest-asyncio you can still test: `asyncio.run(go())` inside a plain test (used successfully in real
projects). `async def` tests without the plugin are silently skipped: always confirm the tests actually ran.

## 2. The core pattern

```python
async def test_refresh_keeps_cursor() -> None:
    app = MyApp(FakeSource(), interval=3600)          # inject fakes; disable timers you do not test
    async with app.run_test(size=(100, 30)) as pilot:  # headless, deterministic size
        await app.workers.wait_for_complete()          # let the initial worker finish
        table = app.query_one("#items", DataTable)
        await pilot.press("down", "down")
        await pilot.press("r")
        await app.workers.wait_for_complete()
        await pilot.pause()                            # drain pending messages
        assert table.cursor_row == 2                   # assert STATE, not pixels
```
**Pilot methods (8.2.8):** `press(*keys)`, `click(selector | widget, offset=, times=, control=/shift=/meta=)`,
`double_click`, `triple_click`, `hover`, `mouse_down`, `mouse_up`, `pause(delay=None)`, `resize_terminal(w, h)`,
`wait_for_animation`, `wait_for_scheduled_animations`, `exit(result)`.
Key names: `"enter"`, `"escape"`, `"tab"`, `"down"`, `"ctrl+p"`, `"question_mark"`, `"slash"`, `"space"`, printable letters as themselves.

**Waiting rules (the source of most flakiness):**
1. Never `time.sleep` / `asyncio.sleep` to wait for the UI.
2. After input: `await pilot.pause()`.
3. After starting a worker: `await app.workers.wait_for_complete()`.
4. After animations: `await pilot.wait_for_animation()`; or set `TEXTUAL_ANIMATIONS=none` for the whole run.
5. For timers: build the app with a tiny interval and `await pilot.pause(0.3)`, or better, call the public method the timer calls.
6. Do not call private methods (`_refresh`). If a test needs one, make it public (`apply`, `refresh_data`).

## 3. What to test (checklist)

- Initial render: row counts, focused widget, titles.
- Each key binding and action changes state (`app.paused`, `table.cursor_row`, `app.screen` type).
- Modals: open with a key, `dismiss` result reaches the caller, `escape` closes.
- Data merge: add / update / remove rows by key; cursor and scroll kept.
- Responsive: `run_test(size=(60, 20))` vs `(120, 30)` toggles breakpoint classes (`app.screen.has_class("-narrow")`) and `display`.
- Untrusted input: `[red]boom[/red]` and an ANSI escape render literally (`cell.plain == "[red]boom[/red]"`).
- Errors: a source that raises leaves the UI alive and shows the error state.
- Command palette: `ctrl+p` opens `CommandPalette`; your provider's `search`/`discover` yield hits (test the provider directly with a fake app for speed).
- Shutdown: `q` exits; resources closed (assert on the fake).

Mutation-check your tests: temporarily break the behavior (e.g. pass a raw `str` instead of `Text`) and confirm the test fails.

## 4. Fakes and injection

Write one `FakeSource` (deterministic seed, no I/O) and reuse it in tests, `tui_shot.py` and demos. For time,
inject a clock (`Callable[[], float]`) instead of patching `time`. For network, fake the Protocol, not `httpx`.
Thread workers: assert on the message or state produced, and use `worker.wait()` (`await worker.wait()`) if you hold the handle.

## 5. Snapshot tests (visual regression)

```bash
uv add --dev pytest-textual-snapshot
uv run pytest --snapshot-update          # first run, then review the SVGs it writes
```
```python
def test_dashboard_visual(snap_compare):
    assert snap_compare("dashboard/app.py", terminal_size=(100, 30), press=["down", "question_mark"])

def test_after_setup(snap_compare):
    async def run_before(pilot) -> None:
        await pilot.hover("#items")
    assert snap_compare("dashboard/app.py", run_before=run_before)
```
- Snapshots are SVG screenshots stored beside the tests; the test fails when the rendering changes.
- Make the app deterministic first: fake source with a seed, fixed size, no clock, animations off. Otherwise snapshots flake.
- Snapshot only stable, meaningful screens (default, one modal, narrow). Too many snapshots turns every style tweak into churn.
- Review diffs by eye; do not blind `--snapshot-update`.

## 6. Letting the agent SEE the UI (verification loop)

Textual needs no PTY for this. Headless `run_test` plus `export_screenshot` renders exactly what a terminal would.

```bash
S=~/.claude/skills/textual-tui/scripts/tui_shot.py
uv run python $S pkg.app:MyApp --size 100x30 --text                       # plain text: cheap, greppable
uv run python $S pkg.app:MyApp --size 60x20 --press "question_mark" --text # after key presses
uv run python $S pkg.app:MyApp --size 100x30 --png /tmp/ui.png            # then view the PNG with the Read tool
uv run python $S pkg.app:MyApp --query "#detail"                          # type, id, classes, display, region
uv run python $S pkg.app:MyApp --outline                                  # whole widget tree as JSON (id, focus, visible, region, text)
uv run python $S mymodule:make_app --svg /tmp/ui.svg                      # factory that injects a FakeSource
```
Loop: design, build, **look**, fix. Use `--text` for quick structure checks and one PNG per milestone for polish
(spacing, color, hierarchy). PNG needs `rsvg-convert`, `cairosvg` (`uv pip install cairosvg`), or macOS `qlmanage` (built in).
The script imports and runs the target app: run only code you trust. The text mode uses a private compositor call
that mirrors `export_screenshot`; if a future Textual breaks it, `--svg` (public API) still works.

Review with the design checklist: focus visible, no truncation surprises, alignment stable, status not colour-only.

## 7. Real-terminal and non-Textual TUIs (PTY level)

When you must test a real process in a terminal (a non-Textual TUI, or end-to-end shell behavior):
- **tmux** (`new-session -d`, `send-keys`, `capture-pane -p`): works everywhere, no "done" signal, so poll for an expected string with a timeout; never fixed sleeps.
- **PTY daemons for agents:** [agent-tui](https://github.com/pproenca/agent-tui) (outline with stable refs, `wait` for state), [tui-use](https://github.com/onesuper/tui-use) (headless xterm, waits for the screen to settle), ghostty-automator (emulator-level IPC). Observe, act, then wait for an *observable* condition; never guess timing.
- Make your app agent-friendly: stable ids, an explicit mode/status indicator, and a `--json` path (see `ai-native-tui.md`).
- `textual run --screenshot 5 app.py` (env `TEXTUAL_SCREENSHOT=5`) saves an SVG after 5 seconds in a real run; `TEXTUAL_PRESS="down,enter"` presses keys on startup.

## 8. CI

- Headless by default with `run_test`; no display needed.
- Set `TEXTUAL_ANIMATIONS=none` and a fixed `size`.
- Pin `textual` in the lockfile; a new Textual release can change snapshots. Update deliberately and review diffs.
- Run `ruff` and `mypy --strict` on the app (Textual ships types; subclassing Textual classes needs no override in 8.x, verify with your mypy config).
