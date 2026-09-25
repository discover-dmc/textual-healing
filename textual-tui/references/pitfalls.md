# Pitfalls: symptom to cause to fix

Read when: something is broken or behaves oddly. Sources: Textual docs, community threads (GitHub discussions
on `NoMatches`, DataTable updates, blocking APIs), and issues hit in real projects.

## Rendering and layout

| Symptom | Likely cause | Fix |
|---|---|---|
| Table flickers; cursor jumps to row 0 every refresh | `clear()` + re-add on a timer | keyed rows, `update_cell` only for changed cells (`widgets-and-data.md`) |
| Widget is invisible or 0 high | `height: 1fr` under an `auto`-height parent, or no size on parent | give the parent a definite size or use `height: auto` consistently |
| `1fr`/`%` widths ignored | parent has `width: auto` | set parent width or use `Horizontal` with explicit widths |
| CSS rule "does nothing" | specificity/order: widget `DEFAULT_CSS` vs app CSS; wrong selector (`#id` on a class) | check with `--dev` hot reload and `tui_shot.py --query "#id"`; use `Screen.-narrow #x` style selectors |
| Pane should hide when narrow, does not | using `on_resize` and forgetting the initial event, or class typo | `HORIZONTAL_BREAKPOINTS` and `Screen.-narrow` selector |
| Text overflows / wraps oddly | no width, wide glyphs (emoji) | set widths; avoid emoji in aligned columns; `text-overflow`/ellipsis in custom render |
| Colors look wrong or flat | 16-color terminal, `ansi-*` theme, `NO_COLOR` | design in layers; preview with `TEXTUAL_COLOR_SYSTEM=standard` |
| Footer shows too many or no keys | only `show=True` bindings appear; focused widget's bindings included | curate 3-5; rest in `?` and palette |
| Modal shows but keys still hit the app | a `priority=True` app binding | scope it or drop priority; `ModalScreen` blocks normal app bindings |

## State, reactivity, DOM

| Symptom | Cause | Fix |
|---|---|---|
| `NoMatches` from `query_one` | query before mount; wrong screen; widget already removed; screen switched quickly | query in/after `on_mount`; query from the active screen; `call_after_refresh`; guard with `query(...)` and check emptiness |
| Watcher crashes in `__init__` | assigning a reactive before mount fires watchers | `self.set_reactive(Cls.attr, value)` |
| List/dict reactive did not update the UI | in-place mutation | `self.mutate_reactive(Cls.attr)` or assign a new object |
| Widget state (input text, scroll, cursor) resets | `recompose=True` or remount | avoid recompose on stateful widgets; update children |
| Watcher not called | value equal to old | `always_update=True` if intended |
| `push_screen_wait` raises | called outside a worker | wrap the caller in `@work` |
| Handler never fires | wrong handler name for nested message class | use `@on(Widget.Message)` |
| Same message handled twice | bubbling to parent and grandparent | `event.stop()` |
| Action does nothing | binding refers to a missing `action_<name>`; or a widget captured the key first | define the method; use `priority=True` for global keys when an Input has focus |
| Rebound key scrolls but the cursor does not move (DataTable) | used `scroll_home`/`scroll_end` (viewport only) | use `scroll_top`/`scroll_bottom` to move the cursor; check each widget's actions by running them |

## Async and threads

| Symptom | Cause | Fix |
|---|---|---|
| UI freezes during a request | blocking call in handler | `@work` async, or `@work(thread=True)` |
| Old response overwrites new | overlapping workers | `@work(exclusive=True)` |
| Crash or corruption updating a widget from a thread | UI touched off-thread | `self.call_from_thread(fn, ...)` or `post_message` |
| Thread worker keeps running after cancel | threads are not auto-cancelled | check `get_current_worker().is_cancelled` in the loop |
| App exits but client/socket leaks | workers cancel, your resources do not | `try/finally` around `app.run()`; close in `on_unmount` |
| A worker error kills the app | default `exit_on_error=True` | `exit_on_error=False` and handle `worker.error` |

## Testing

| Symptom | Cause | Fix |
|---|---|---|
| `async def` tests "pass" without running | no pytest-asyncio / `asyncio_mode` | install plugin and set `asyncio_mode = "auto"`; check the test count |
| Flaky assertion right after key press | messages not processed | `await pilot.pause()`; after workers `await app.workers.wait_for_complete()` |
| pytest-socket blocks the Textual test | asyncio self-pipe is a UNIX socket | `addopts = "--disable-socket --allow-unix-socket"` (verified) |
| Snapshot tests flake | time, randomness, animations, unsized terminal | fake source with seed, fixed `terminal_size`, `TEXTUAL_ANIMATIONS=none` |
| Test calls `app._refresh()` | timer callback is private | make the method public; call it |
| Can't test Ctrl-C shutdown from a background shell | jobs started with `&` in non-interactive shells inherit SIGINT ignored | use `subprocess.Popen` or a real terminal; `uv run` may signal twice |
| TUI misbehaves when run by an agent in the background | no TTY | test headless with `run_test`; long sessions go in the user's terminal panel |

## Data and safety

| Symptom | Cause | Fix |
|---|---|---|
| A name like `[red]x[/red]` colors text or vanishes | string parsed as markup | wrap in `Text(...)` / `markup=False` / `escape(...)` |
| Terminal title/cursor/clipboard changes from data | escape sequences in rendered text | `sanitize()` (`ai-native-tui.md`) |
| Clicking a rendered link opens something unexpected | Markdown auto-opens links | `Markdown(open_links=False)` and confirm |
| Secrets appear in logs/screenshots | data rendered verbatim | redact at the core layer; never render tokens |

## Tooling

| Symptom | Cause | Fix |
|---|---|---|
| `textual` command not found | `textual-dev` not installed | `uv add --dev textual-dev` |
| `print()` corrupts the screen | stdout is the display | `self.log(...)` or `textual console` |
| mypy complains subclassing Textual | old config override | in 8.x no override is needed (verified with `--strict`); remove it |
| PNG export unavailable | no rasterizer | install `rsvg-convert` or `cairosvg`; macOS has `qlmanage`; else use `--svg`/`--text` |
| Long-running collector dies when the session ends | backgrounded child of the agent shell | run in the user's terminal tab (with `caffeinate` on macOS if it must stay awake) |
