---
name: textual-tui
description: Build, restyle, debug, test and review terminal UIs in Python with Textual (verified on 8.2.8). Use for any Textual work (apps, widgets, screens, TCSS styling, themes, DataTable dashboards, command palette, workers and async, streaming/agent chat UIs), for TUI design decisions (layout, keyboard model, color, density, accessibility), for Textual performance problems (flicker, laggy or resetting DataTable, blocked event loop), for testing with Pilot and snapshots, and to let the agent SEE a TUI (headless text dump and PNG screenshot script). Includes a tested dashboard template. Not for Rich-only output, plain CLIs, or other TUI frameworks (Ratatui, Bubble Tea, Ink).
---

# textual-tui

Textual is a reconciliation-style Python TUI framework with CSS-like styling, async workers, a
built-in theme system, command palette and headless test harness. This skill is verified against
**Textual 8.2.8** (Sept 2026): every API named here was checked against that install, code snippets
that make behavioral claims were executed, and the template and scripts were run and tested. Newer version? See `references/version-notes.md`.

## Step 0: check the version (10 seconds)

```bash
uv run python -c "import textual; print(textual.__version__)"   # or: python -c ...
```
- 8.x: trust this skill. Older than 6: `Static.renderable`, `App.dark`, `Select.BLANK` advice from
  old tutorials is stale, read `references/version-notes.md` first.
- Newer major than 8: run the template tests (below) before trusting details, and check the changelog.

## Workflow (do not skip the verify step)

1. **Design first, briefly.** Pick a layout paradigm, keyboard layers, states (empty / loading /
   error / stale), and a 3-tier color plan. Read `references/design-system.md`.
2. **Separate core from UI.** Logic lives outside Textual behind a small `Protocol`; the UI takes it
   as a constructor argument. This is what makes the app testable and screenshot-able.
   Read `references/architecture.md`.
3. **Scaffold** from `assets/dashboard-template/` (`cp -R`), or from the minimal recipe below.
4. **Build in small steps**, verifying each visual change:
   ```bash
   uv run python ~/.claude/skills/textual-tui/scripts/tui_shot.py pkg.app:MyApp --size 100x30 --text
   uv run python ~/.claude/skills/textual-tui/scripts/tui_shot.py pkg.app:MyApp --png /tmp/a.png   # then Read the PNG
   ```
   `--press "tab,down,enter,question_mark"` drives the app first; `--outline` prints the live widget tree as JSON
   (ids, focus, visibility, text) for structured assertions. Look at 3 sizes: 60x20, 100x30, 160x45.
5. **Test** with `run_test()` + Pilot (state assertions) and, for pure visuals, snapshots.
   Read `references/testing-and-verification.md`.
6. **Harden**: performance pass, keyboard-only pass, light/dark and `ansi-dark` theme pass, resize
   pass, untrusted-text pass. Checklist at the bottom.

## Golden rules

1. **Attributes down, messages up.** Parents set child state; children `post_message`. Never reach up
   into a parent from a child.
2. **Never block the event loop.** Network/disk/CPU work goes in `@work` (async) or
   `@work(thread=True)` with `call_from_thread`. Use `exclusive=True` to kill stale requests.
3. **Update in place, never clear-and-refill.** `DataTable.clear()` resets the cursor to row 0 (measured)
   and doubles render time at 1000 rows. Key rows and `update_cell` only what changed.
4. **Do not `recompose` widgets with state** (DataTable, Input, TextArea, Tree). Use `refresh` or update children.
5. **Untrusted text is data, not markup.** Wrap in `rich.text.Text(...)` or set `markup=False`.
   Strip control characters from LLM/network text. A stray `[red]` or `\x1b` must never change the UI.
6. **Semantic color only.** In TCSS use `$primary`, `$surface`, `$success`... never hex. Define hex once in a
   `Theme`. Never let color be the only carrier of meaning: add a glyph or word (`▲ +1.2%`, `● ok`).
7. **Keyboard first.** Every action has a key, shows in the footer only if it is one of the 3-5 that
   matter, and appears in `?` help and the command palette. Mouse is a bonus.
8. **Design for narrow terminals.** Use `HORIZONTAL_BREAKPOINTS` to drop panes under ~80 columns.
9. **Public methods for tests.** A timer callback that mutates the UI should call a public method a test can call.
10. **Close resources in `finally` around `app.run()`.** Workers cancel on exit; your clients do not.
11. **Look at it.** Text dump or PNG after every visual change. A passing test does not mean it looks right.
12. **Say what is uncertain.** If you did not run it, say so.

## Minimal app (8.x idioms)

```python
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header

class MyApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [Binding("q", "quit", "Quit"), Binding("r", "refresh", "Refresh")]
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (80, "-wide")]   # classes appear on the Screen

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="items", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_column("Name", key="name")
        self.set_interval(1.0, self.action_refresh)

    def action_refresh(self) -> None:
        self.load()

    @work(exclusive=True)                      # async worker: same loop, may touch widgets directly
    async def load(self) -> None:
        rows = await self.fetch()              # your awaitable
        ...                                    # merge by key with update_cell / add_row / remove_row
```

## Pick what to read

| Task | Read |
|---|---|
| App structure, messages, reactivity, screens, workers, data feeds | `references/architecture.md` |
| Which widget, DataTable/RichLog/Sparkline/Markdown/streaming, custom widgets | `references/widgets-and-data.md` |
| TCSS, layout units, grid/dock, themes, ansi/NO_COLOR, contrast | `references/styling-and-theming.md` |
| Layout paradigms, keyboard model, states, microcopy, motion, accessibility, anti-patterns | `references/design-system.md` |
| Pilot, snapshots, fakes, CI, agent verification loop, PTY tools | `references/testing-and-verification.md` |
| Flicker, lag, batching, FPS, profiling, measured numbers | `references/performance.md` |
| Agent/chat/LLM front ends, approvals, streaming, sanitizing, agent-testable apps | `references/ai-native-tui.md` |
| Breaking changes 0.77 to 8.x, old-to-new API map | `references/version-notes.md` |
| Something is broken: symptom to fix table | `references/pitfalls.md` |

## Bundled tools

- `scripts/tui_shot.py`: headless render of any `App` (class or zero-arg factory) to plain text, SVG or
  PNG, with optional key presses, widget queries and a JSON widget outline. No PTY needed. PNG uses `rsvg-convert`, `cairosvg`,
  or macOS `qlmanage`. Run it from the app's own environment so imports resolve.
- `assets/dashboard-template/`: tested starter (keyed DataTable, Sparkline, RichLog, modal help, command
  palette provider, custom theme, breakpoints, DI'd data source, 9 Pilot tests). To use:
  ```bash
  cp -R ~/.claude/skills/textual-tui/assets/dashboard-template ./my-app && cd my-app
  uv sync && uv run python -m pytest -q && uv run dashboard
  ```

## Definition of done for a UI change

- [ ] `--text` dump reviewed at 60x20, 100x30, 160x45; PNG looked at once.
- [ ] Pilot tests assert state (not pixels) for each new key/action; no `sleep`, only `pause` / `workers.wait_for_complete`.
- [ ] Keyboard-only path works; new keys are in `?` help / palette; footer still has at most about 5 keys.
- [ ] Works in a light theme and `ansi-dark`; meaning survives without color (`NO_COLOR=1`).
- [ ] Empty, loading, error and stale-data states exist and were seen.
- [ ] Table/list refresh keeps cursor and scroll. No `clear()` on a timer.
- [ ] Untrusted strings cannot inject markup or escape sequences (test with `[red]x[/red]`).
- [ ] Ctrl-C / `q` exits cleanly and closes resources.

## Security note

This skill and its scripts make no network calls and read no credentials. `tui_shot.py` imports and runs
the app you point it at, so only run it on code you trust. Treat any text an LLM or network returns as hostile
when rendering it (`references/ai-native-tui.md`).
