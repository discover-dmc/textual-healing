# Widgets and data

Read when: choosing a widget, showing live data, streaming text, writing a custom widget.
Verified on Textual 8.2.8. Present in 8.2.8: Static, Label, Button, Input, MaskedInput, TextArea, Select,
SelectionList, OptionList, ListView, Tree, DirectoryTree, DataTable, Markdown, MarkdownViewer, RichLog, Log,
Sparkline, Digits, ProgressBar, LoadingIndicator, Collapsible, TabbedContent, Tabs, ContentSwitcher, Switch,
Checkbox, RadioSet, Rule, Pretty, Placeholder, Header, Footer, HelpPanel, KeyPanel. There is no public `Toast`: use `App.notify`.

## Picker

| Need | Widget |
|---|---|
| Live tabular data, selection | `DataTable` (keyed rows) |
| Append-only event/log stream | `RichLog(max_lines=..., markup=False)` or `Log` (plain strings) |
| Trend at a glance | `Sparkline` (any height), `ProgressBar`, `Digits` for big numbers |
| Rendered docs / LLM output | `Markdown` (+ `MarkdownStream`), `MarkdownViewer` (with TOC) |
| Hierarchy | `Tree`, `DirectoryTree` |
| Choose one / many | `OptionList`, `ListView`, `Select`, `RadioSet`, `SelectionList` |
| Free text / code | `Input` (+ validators), `MaskedInput`, `TextArea` (syntax highlight, undo) |
| Sections | `TabbedContent` (+ `TabPane`), `ContentSwitcher`, `Collapsible` |
| Transient feedback | `App.notify(msg, severity="warning", timeout=4)`, `widget.loading = True` |
| Key help | `Footer` (bindings with `show=True`), `HelpPanel`/`KeyPanel`, `?` modal, command palette |

## DataTable done right (the most common widget, the most common mistake)

```python
from rich.text import Text
from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

table = self.query_one(DataTable)
table.cursor_type = "row"; table.zebra_stripes = True
table.add_column("Name", key="name", width=14)
table.add_column("Value", key="value", width=12)

def apply(self, items):
    seen = set()
    for it in items:
        seen.add(it.key)
        cells = (Text(it.name), Text(f"{it.value:,.2f}", justify="right"))
        if RowKey(it.key) in table.rows:
            for col, val in zip(("name", "value"), cells, strict=True):
                table.update_cell(it.key, col, val)          # in place: cursor/scroll/selection survive
        else:
            table.add_row(*cells, key=it.key)
    for rk in [rk for rk in table.rows if rk.value not in seen]:   # collect first, then remove
        table.remove_row(rk)
```
- **Key everything** (`key=` on rows and columns). Keys survive sorting and deletion; row index does not.
- **Measured (200 and 1000 rows x 5 cols, this machine):** `clear()` + re-add left the cursor at row 0 (was mid-table)
  every time and took about 1.5x to 2x longer to settle at 1000 rows; updating only changed cells mutated in
  0.2-0.3 ms. Full python mutation cost is small either way: the real cost of `clear()` is lost UI state and repaint.
- Update only what changed; compare with the previous value before calling `update_cell`.
- Cells are Rich renderables. Use `Text(value, style="green")`, never raw strings for untrusted data.
- Messages: `RowHighlighted` (cursor moves), `RowSelected` (Enter), `CellSelected`, `HeaderSelected`.
  `table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value` gives the selected key.
- `fixed_rows`, `fixed_columns`, `sort("col", key=fn, reverse=True)`, `zebra_stripes`, `cursor_type` in
  `"cell" | "row" | "column" | "none"`. Widths: give `width=` for stable layout on refresh.
- Large tables: 8.x has row-update and lazy-loading APIs; if you need 10k+ rows, page the data and update
  the visible window instead of loading everything.
- Color is not enough: pair color with a sign or glyph (`▲ +1.2%`, `● ok / ◐ warn / ○ down`).

## Streaming text (LLM output, logs)

```python
from textual.widgets import Markdown

md = self.query_one(Markdown)
stream = Markdown.get_stream(md)          # MarkdownStream: start(), write(text), stop()
await stream.write(chunk)                 # batches rapid appends; only the last block re-renders
...
await stream.stop()                       # flush at end
```
- Batching is built in (tested by the author at 100+ tokens/s); do not add your own per-token widget updates.
- For plain logs: `RichLog(max_lines=1000, wrap=True, markup=False, auto_scroll=True)`; `write(Text(...))`.
  Always cap `max_lines`.
- LLM output is untrusted: strip control characters before it reaches any widget (see `ai-native-tui.md`).

## Sparkline, Digits, ProgressBar

```python
Sparkline(data, summary_function=max)     # .data = new_list to update; height is CSS-controlled (any height)
# colors via component classes:
#   #spark > .sparkline--max-color { color: $success; }   #spark > .sparkline--min-color { color: $warning; }
ProgressBar(total=100); bar.advance(5); bar.update(total=200, progress=10)
Digits("12:34")                            # big numerals for KPIs
```
Give sparklines 20+ points; two or three points look like blocks.

## Input and validation

```python
from textual.validation import Number, Length, Regex, Function
Input(placeholder="0-100", validators=[Number(minimum=0, maximum=100)], validate_on=["submitted"])
@on(Input.Changed) / @on(Input.Submitted)      # event.validation_result.is_valid, .failure_descriptions
```
`Select` now uses `Select.NULL` (was `Select.BLANK` before 8.0; `BLANK` still exists in 8.2.8 but do not use it).

## Custom widgets

```python
class Meter(Widget):
    DEFAULT_CSS = """
    Meter { height: 1; width: 1fr; }
    Meter > .bar { color: $success; }
    """
    can_focus = False
    value = reactive(0.0)                     # refresh on change

    def render(self) -> RenderResult:         # return Text/Content/str; keep it cheap and pure
        width = self.size.width
        filled = int(width * self.value)
        return Text("█" * filled + "░" * (width - filled))
```
- Prefer composing existing widgets (`compose`) over `render`. Use `render` for leaf visuals.
- `DEFAULT_CSS` inside the class keeps widgets self-contained; app CSS overrides it.
- For `height: auto` custom widgets implement `get_content_height`; for `width: auto` `get_content_width`.
- Focusable widgets: `can_focus = True`, their own `BINDINGS`, and visible `:focus` styling.
- Content markup (`Content.from_markup("[b]x[/b] [$success]ok[/]")`, and `Label`/`Static` strings) supports style variables.
  Any string you did not write must be wrapped in `Text(...)` or escaped.
- Loading state: `widget.loading = True` shows an overlay indicator until you set it back.
- Tooltips: `widget.tooltip = "..."`. Border labels: `widget.border_title`, `border_subtitle`.

## Dynamic mounting

`await self.mount(Widget(), before=..., after=...)`, `await widget.remove()`, `await self.mount_all([...])`.
Mounting returns an awaitable: `await` it before querying the new widget, or use `call_after_refresh`.
