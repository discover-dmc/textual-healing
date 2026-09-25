# Architecture

Read when: starting an app, structuring state, wiring data feeds, adding screens or modals, handling
shutdown. Verified on Textual 8.2.8.

## 1. Project layout

```
myapp/
  pyproject.toml            # textual>=8.2; dev: pytest, pytest-asyncio, pytest-textual-snapshot, textual-dev
  myapp/
    core/                   # pure logic + data sources. No textual imports.
    app.py                  # App subclass: compose, bindings, wiring
    screens/                # Screen / ModalScreen subclasses (one file each when big)
    widgets/                # reusable widgets (DEFAULT_CSS inside the class)
    app.tcss                # app-level styling (semantic variables only)
    cli.py                  # optional: `--json` mode over the same core
  tests/
```
Rule: `core/` must be importable and testable with no Textual. Then the CLI, TUI and tests share it.

## 2. Depend on a Protocol, inject it

```python
class Source(Protocol):
    async def fetch(self) -> list[Item]: ...

class MyApp(App[None]):
    def __init__(self, source: Source | None = None) -> None:
        super().__init__()
        self._source = source or RealSource()
```
Tests and `tui_shot.py` pass a `FakeSource`. Do not reach for globals or singletons inside widgets.

## 3. Messages up, attributes down

- Parent to child: set attributes/reactives, call methods, or `child.data_bind(Parent.field)`.
- Child to parent: define a `Message` subclass on the widget and `post_message` it. Parents handle it.

```python
class Ticker(Widget):
    class Picked(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def pick(self, key: str) -> None:
        self.post_message(self.Picked(key))

class MyApp(App[None]):
    @on(Ticker.Picked)
    def _picked(self, event: Ticker.Picked) -> None: ...
    # or by naming convention: def on_ticker_picked(self, event: Ticker.Picked) -> None
```
- Handler name = `on_` + snake_case(`WidgetClass.MessageClass`), e.g. `DataTable.RowHighlighted` becomes
  `on_data_table_row_highlighted`. `@on(DataTable.RowHighlighted, "#items")` filters by CSS selector.
- `event.stop()` stops bubbling. `with self.prevent(Input.Changed): ...` suppresses messages you cause.
- `post_message` is thread-safe. Most other widget methods are not.

## 4. Reactive state

```python
class Panel(Widget):
    count = reactive(0)                       # change refreshes the widget
    items = reactive(list, recompose=True)    # avoid on stateful children
    hidden = var(False)                       # reactive but no refresh

    def watch_count(self, old: int, new: int) -> None: ...     # 1 or 2 args
    def validate_count(self, v: int) -> int: return max(0, v)
    def compute_label(self) -> str: return f"{self.count} items"   # order: compute, validate, watch
```
- In `__init__`, use `self.set_reactive(Panel.count, 5)`; plain assignment fires watchers before mount.
- Mutating a list/dict in place does not notify: call `self.mutate_reactive(Panel.items)`.
- Watchers only fire when the value changes; `reactive(..., always_update=True)` forces it.
- `layout=True` when a change alters size; `recompose=True` only for stateless children.
- Prefer `data_bind` over hand-written watchers to sync parent and child.

## 5. Screens, modals, modes

```python
class Confirm(ModalScreen[bool]):
    BINDINGS = [("y", "yes", "Yes"), ("n,escape", "no", "No")]
    def __init__(self, question: str) -> None:
        super().__init__(); self.question = question
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.question)
            with Horizontal():
                yield Button("Yes", id="yes", variant="primary")
                yield Button("No", id="no")
    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None: self.dismiss(True)
    @on(Button.Pressed, "#no")
    def action_no(self) -> None: self.dismiss(False)

# callback style
self.push_screen(Confirm("Delete?"), lambda ok: self.delete() if ok else None)
# await style: only inside a worker
@work
async def ask(self) -> None:
    if await self.push_screen_wait(Confirm("Delete?")):
        ...
```
- Stack ops: `push_screen`, `pop_screen`, `switch_screen`. `ModalScreen` blocks app bindings and dims what is behind.
- `MODES = {"home": HomeScreen, "settings": SettingsScreen}` + `switch_mode("settings")` gives independent
  stacks (dashboard vs settings) that each remember their history. `DEFAULT_MODE` sets the first.
- `ScreenSuspend` / `ScreenResume` messages: pause and resume expensive work per screen.
- `query`/`query_one` search only the **current screen**. Query from the right screen or hold a reference.

## 6. Concurrency: pick the right worker

| Situation | Use | UI access |
|---|---|---|
| Async I/O (httpx, websockets, aiofiles) | `@work(exclusive=True)` on an `async def` | direct (same event loop) |
| Blocking or CPU code (sqlite, requests, parsing) | `@work(thread=True, exclusive=True)` on a plain `def` | `self.call_from_thread(fn, ...)` or `post_message` only |
| Long-lived feed (websocket, tail, agent stream) | async worker with `async for` / `while True: await ...` | direct, or post a `Message` for decoupling |

```python
from textual.worker import get_current_worker

@work(thread=True, exclusive=True)
def scan(self, path: str) -> None:
    worker = get_current_worker()
    for chunk in slow_iter(path):
        if worker.is_cancelled:
            return                                   # threads are not auto-cancelled: check
        self.call_from_thread(self.append, chunk)

@work(exclusive=True, group="feed")                  # push model
async def run_feed(self) -> None:
    async for items in self._source.stream():
        self.post_message(FeedUpdate(items))         # handler applies it on the UI side
```
- `exclusive=True` cancels the previous worker in the same `group`: fixes stale-response races.
- States: PENDING, RUNNING, CANCELLED, ERROR, SUCCESS; observe with `Worker.StateChanged` or `worker.error`.
  `exit_on_error=False` keeps the app alive if a worker raises (then handle `worker.error` yourself).
- Workers are cancelled when their owner widget or screen is removed and when the app exits.
- Pull model (interval tick starts a worker) is simplest. Use push when the source already streams.
- Never `await asyncio.sleep(...)` in a message handler to wait for data: start a worker.

## 7. Lifecycle and shutdown

```python
def main() -> None:
    client = make_client()
    try:
        MyApp(client).run()
    finally:
        client.close()                    # workers are cancelled for you, your resources are not
```
- `self.exit(result=None, return_code=0)`; the value is available as `app.return_value` / `run()` result.
- Run an external program (editor, pager) with the UI paused: `with self.suspend(): subprocess.run([...])`.
- A TUI needs a real TTY. From an agent, run long sessions in the user's terminal panel, or test headless
  (`run_test`). Background jobs (`cmd &`) in non-interactive shells start with SIGINT ignored, so Ctrl-C style
  tests must use `subprocess.Popen` or a real terminal. `uv run` can deliver SIGINT twice: keep cleanup in `finally`.
- `App.run(inline=True)` renders below the prompt instead of full screen (short interactive prompts).
- `App.run(auto_pilot=fn)` runs a scripted callback against a real run (demos, smoke tests).

## 8. Pure reducer for complex or AI-driven UIs

When the UI state is complicated, or an agent/LLM can change it, route everything through one pure function:

```python
def reduce(state: State, event: Event) -> tuple[State, list[Effect]]: ...
```
The app holds `state` in a reactive, calls `reduce` for every key press, message and feed update, applies the
new state to widgets, and executes effects (start a worker, push a screen). Unit test `reduce` with no Textual.
Untrusted or model-produced input becomes an `Event` value, never code or markup.

## 9. Dual product: CLI plus TUI

Ship `mytool --json` (pipeable, scriptable, agent friendly) and `mytool` (interactive) over the same `core/`.
It doubles your test surface for free and gives agents a non-visual path.
