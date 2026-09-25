# Version notes

Read when: the installed Textual is not 8.x, code copied from a tutorial fails, or you are upgrading.
Source: Textual CHANGELOG (fetched 2026-09-25) plus checks against 8.2.8.

## Check first

```bash
uv run python -c "import textual, importlib.metadata as m; print(textual.__version__, m.metadata('textual')['Requires-Python'])"
```
8.2.8 requires Python `>=3.9,<4.0` (verified). Latest known release: 8.2.8 (2026-06-30). Releases are frequent and mostly fixes.
If the installed version is newer than 8.2.8: skim the changelog for the range, run the template tests, and re-run any
snapshot tests deliberately (`--snapshot-update` only after viewing diffs).
Changelog: https://raw.githubusercontent.com/Textualize/textual/main/CHANGELOG.md

## Breaking changes that bite (newest first)

| Version | Change | Do this instead |
|---|---|---|
| 8.0.0 | `Select.BLANK` renamed `Select.NULL` | use `Select.NULL` (`BLANK` still exists in 8.2.8 but is the old name) |
| 7.1.0 | `Widget.BLANK` added (optimization for widgets that render nothing) | opt in for empty widgets |
| 7.0.0 | `Node.update_node_styles` gained an `animate` argument | pass `animate=False` where needed |
| 6.0.0 | `Static.renderable` renamed `content`; `Label(renderable=)` renamed `Label(content=)`; `HeaderTitle` restructured; backgrounds no longer auto-applied to blank segments | `widget.content`, `Label("text")`; recheck custom Header CSS and blank-area backgrounds |
| 5.0.0 | `Markdown.code_dark_theme / code_light_theme / code_indent_guides` removed; Markdown component classes moved to `MarkdownBlock`; `Visual.render_strips` signature changed; tree-sitter needs Python 3.10+ | style code blocks via theme/CSS; `MarkdownStream` added (`Markdown.get_stream`) |
| 4.0.0 | `Widget.anchor` semantics changed | use `widget.anchor()` (default `anchor=True`) for stick-to-bottom scrolling |
| 3.7.0 | `query_one` / `query_exactly_one` search breadth-first | do not rely on depth-first match order; use unique ids |
| 3.0.0 | `App.query` queries the default screen only; Buttons use Textual markup; tree-sitter languages load lazily | query from the active `self.screen` |
| 2.0.0 | `OptionList` separators are `None`; `wrap`/`tooltip` args removed; text selection added | pass `None` for separators |
| 1.0.0 | default quit is `ctrl+q`; command palette auto-selects top item | rebind `ctrl+c`/`q` deliberately |
| 0.89.0 | `Input.view_position`, `cursor_position` reactive attrs removed | use `cursor_position` property |
| 0.88.0 | `ListView.pop` / `remove_items` return `AwaitComplete` | await them |
| 0.86.0 | `App.dark` removed; default widget CSS changed a lot | `self.theme = "textual-dark" / "textual-light"`; re-test styling |
| 0.82.0 | `Widget.set_loading` no longer returns an awaitable | use `widget.loading = True` |
| 0.79.0 | `DOMNode.query_one` no longer raises `TooManyMatches` | ensure ids are unique |
| 0.77.0 | `ClassicFooter` removed; `App.get_key_display` needs a `Binding` | use `Footer` |

## Old to new (common tutorial breakage)

| Old tutorial code | Current |
|---|---|
| `self.dark = True` / `App.dark` | `self.theme = "textual-dark"`; toggling: `action_toggle_dark` still exists |
| `Static.renderable`, `Label(renderable=...)` | `Static.content`, `Label(content=...)` / positional |
| `widget.set_loading(True)` await | `widget.loading = True` |
| `from textual.widgets import Toast` | `self.notify(...)` |
| `DataTable.clear()` + re-add on a timer | keyed `update_cell` |
| `on_resize` with manual `set_class` | `HORIZONTAL_BREAKPOINTS` |
| Manual thread + `asyncio.run` inside handlers | `@work(thread=True)` + `call_from_thread` |
| `app.push_screen("name")` for screens not in `SCREENS` | register in `SCREENS`/`MODES` or pass an instance |
| Markdown streaming by `update()` per token | `Markdown.get_stream(md)` |

## Things that are stable and safe to rely on

App/Screen/Widget lifecycle (`compose`, `on_mount`), reactive system, messages and `@on`, CSS selectors and core properties,
DataTable keyed API, workers (`@work`, `exclusive`, `thread`), `run_test` and Pilot, command palette `Provider`,
`Theme` registration, `ModalScreen[T]` with `dismiss`.

## Upgrade routine

1. Read the changelog between old and new (breaking sections first).
2. `uv lock --upgrade-package textual` on a branch.
3. Run tests; then `tui_shot.py --text` on key screens at 3 sizes and compare by eye.
4. Update snapshots only after inspecting the SVG diffs.
5. Update this file's "verified on" line if you re-verified the skill.
