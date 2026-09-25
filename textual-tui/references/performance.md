# Performance

Read when: the UI flickers, lags, uses CPU when idle, resets the cursor, or handles fast data.
Numbers below were measured on the machine that verified this skill (Apple silicon laptop, Textual 8.2.8,
headless). Treat them as ratios and rules of thumb, not guarantees. Re-measure for your case with the snippet at the end.

## 1. Mental model

Textual is reconciliation-based: widgets are objects, changes mark regions dirty, a compositor repaints diffs,
capped at `TEXTUAL_FPS` (default 60 max). Cost comes from (a) how many widgets you mount/unmount, (b) how much you
force to re-render, (c) how long your handlers hold the event loop. Python work in handlers is usually small;
repaint and lost state are what you feel.

## 2. Rules, in order of payoff

1. **Do not block the loop.** Any handler taking more than about 50 ms freezes input. Move work to workers.
   Textual logs slow message handlers above `TEXTUAL_SLOW_THRESHOLD` ms (default 500, min 100): lower it in dev.
2. **Update in place.** Keyed `DataTable.update_cell` for changed cells only. Measured (5 columns):

   | rows | `clear()` + re-add: python / settle | update all cells: python / settle | update 5 changed rows: python |
   |---|---|---|---|
   | 200 | 1.7 ms / 44 ms | 3.4 ms / 34 ms | 0.2 ms |
   | 1000 | 6.7 ms / 67 ms | 14.4 ms / 31 ms | 0.3 ms |

   ("settle" includes a fixed floor of about 30 ms from `pilot.pause`.) The decisive difference is behavior: after `clear()` the
   cursor was back at row 0 in every run, and settle time doubled at 1000 rows. Compare old vs new value and skip unchanged cells.
3. **Batch fast streams.** If events arrive faster than about 20 per second, buffer them in the worker and flush on a
   timer: keep a list, `set_interval(0.1, self.flush)`, apply once per flush. One repaint per tick beats one per event.
   For Markdown use `MarkdownStream` (it batches and re-renders only the last block).
4. **Avoid `recompose`** and `recompose=True` reactives except for small stateless subtrees. Recompose unmounts and remounts children.
5. **Cap unbounded widgets.** `RichLog(max_lines=1000)`, `Log(max_lines=...)`. Keep sparkline data to about 60-120 points.
6. **Keep `render` pure and cheap.** No I/O, no sorting large data, no Rich Tables re-built every frame.
7. **Refresh narrowly.** `refresh()` a widget, not the screen; `DataTable.refresh_row/column/coordinate` for targeted repaint.
8. **Fewer, smarter timers.** One `set_interval` that fans out beats many. Pause timers when a screen is suspended
   (`ScreenSuspend` / `ScreenResume`) or when the app is paused.
9. **Lazy mount heavy panes.** `textual.lazy.Lazy(Widget())` and `TabbedContent` panes defer expensive children until shown.
10. **Prefer native widgets** to Rich renderables for frequently changing content.
11. **Disable what you do not need:** `TEXTUAL_ANIMATIONS=none` in CI and low-power targets; `TEXTUAL_SMOOTH_SCROLL=0` on slow SSH.

## 3. Idle should be idle

- A dashboard with a 1 Hz timer should use near-zero CPU between ticks. If it does not, look for a `set_interval` with a tiny period,
  a watcher that mutates its own reactive, or a worker loop without `await`.
- Only mutate reactives when the value changed; watchers fire on change but assignments of equal values are free, while
  `always_update=True` reactives are not.

## 4. Startup time

Python import time dominates. Import heavy modules lazily inside actions, avoid importing pandas/numpy at module top,
and build big widgets in `on_mount` workers with `loading = True`. Measure: `python -X importtime app.py 2> imports.txt`.

## 5. Network and slow terminals

- SSH and tmux limit throughput: fewer full repaints, no per-frame color gradients, avoid constant scrolling logs.
- Synchronized-output-capable terminals avoid tearing; Textual handles terminal quirks, but design updates as small diffs.
- The Kitty keyboard protocol (Textual 8.2.7+) improves key handling; `TEXTUAL_DISABLE_KITTY_KEY=1` disables it if a terminal misbehaves.

## 6. Profiling recipes

```bash
textual console -x EVENT -x DEBUG              # terminal 1: quiet console
textual run --dev app.py                        # terminal 2: logs appear in the console
TEXTUAL_SLOW_THRESHOLD=100 textual run --dev app.py    # warn on handlers slower than 100 ms
python -X importtime -c "import myapp.app" 2> imports.txt
```
In code: `self.log("msg", x=1)`, `self.log(self.tree)` (DOM tree), `from textual import log`.
Stdlib logging: `logging.basicConfig(handlers=[TextualHandler()])` from `textual.logging`.

## 7. Micro-benchmark you can re-run (measures your table, not mine)

```python
import asyncio, time
from textual.app import App
from textual.widgets import DataTable

class A(App):
    def compose(self): yield DataTable(cursor_type="row")

async def main(nrows=1000):
    app = A()
    async with app.run_test(size=(120, 40)) as pilot:
        t = app.query_one(DataTable); cols = [f"c{i}" for i in range(5)]
        for c in cols: t.add_column(c, key=c)
        rows = [[f"r{r}c{c}" for c in range(5)] for r in range(nrows)]
        for r, cells in enumerate(rows): t.add_row(*cells, key=f"r{r}")
        await pilot.pause(); t.move_cursor(row=nrows // 2); await pilot.pause()
        t0 = time.perf_counter(); t.clear()
        for r, cells in enumerate(rows): t.add_row(*cells, key=f"r{r}")
        await pilot.pause(); print("clear+re-add", (time.perf_counter() - t0) * 1000, "ms; cursor row ->", t.cursor_row)
asyncio.run(main())
```
