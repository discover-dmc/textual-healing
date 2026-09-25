# TUI design system, expressed in Textual

Read when: deciding layout, keys, states, color, motion; reviewing a UI; fixing "it works but feels bad".
Synthesised from 2026 TUI design writing (lazygit, k9s, btop, yazi, harlequin, posting and the Terminal
Renaissance study of 23 apps) and checked against what Textual actually provides.

## 1. Principles (in priority order)

1. **Spatial consistency.** Panes stay where they are. Users build location memory in the first minute.
   Do not rearrange on data change. Never move the focused element under the cursor.
2. **Keyboard first, mouse optional.** Every feature has a key. Mouse enhances (click rows, scroll) but never replaces.
3. **Progressive disclosure in 3 tiers:** footer (3-5 keys) then `?` overlay (all keys, by context) then docs.
4. **Semantic color, never color alone.** Green/red carry meaning, plus a glyph, sign or word.
5. **Async everything.** The UI never freezes; long work shows progress and can be cancelled with `Esc`.
6. **Contextual intelligence.** Bindings and help reflect the focused panel; the footer changes with focus.
7. **Design in layers:** works monochrome, reads at 16 colors, sings at true color.
8. **Density with rhythm.** Every cell earns its place; group with spacing, not decoration.

## 2. Pick a layout paradigm, then map it

| App type | Paradigm | Textual skeleton |
|---|---|---|
| Git, DevOps, multi-resource | Persistent multi-panel (lazygit) | `Horizontal` of `Vertical`s; focus moves between panes with Tab / number keys |
| Monitor, dashboard | Widget grid (btop) | `Grid` (`grid-size: 2 3`), each cell an independent widget with its own refresh |
| File / tree browsing | Miller columns (yazi) | `Horizontal` of 3 `ListView`/`Tree`: parent, current, preview |
| Deep hierarchies (k8s) | Drill-down stack (k9s) | `push_screen` per level, breadcrumb in `Header.sub_title`, `Esc` pops |
| SQL / HTTP client | IDE three-panel (harlequin) | sidebar (`width: 28`) + main + results; `TabbedContent` for results |
| Transient tool | Overlay (fzf, atuin) | `ModalScreen` or `run(inline=True)` |
| Log / event viewer | Header stats + scrollable list (htop, tig) | `Header`, stats `Static`, `DataTable`/`RichLog` at `1fr`, `Footer` |
| Chat / agent | Conversation + input | `VerticalScroll` of message widgets + bottom `Input`/`TextArea` (see `ai-native-tui.md`) |

## 3. Keyboard model (four layers)

- **L0 universal:** arrows, Enter, Esc (back/cancel), `q` or `ctrl+q` quit (`ctrl+q` is Textual's default quit), Tab/Shift+Tab focus.
- **L1 navigation:** `j/k/h/l`, `g/G`, `/` search, `?` help, `:` or `ctrl+p` command palette.
- **L2 actions:** mnemonic single keys (`r` refresh, `d` delete, `s` sort, `p` pause).
- **L3 power:** chords and macros, documented only in the help overlay.

```python
BINDINGS = [
    Binding("q", "quit", "Quit"),                       # shown in footer
    Binding("question_mark", "help", "Help"),
    Binding("slash", "search", "Search", show=False),   # in ? help, not in footer
    Binding("ctrl+q", "quit", "Quit", show=False, priority=True),   # priority: fires even if a widget has focus
]
# Vim motions for a table: subclass and rebind to the widget's own actions (executed and verified in 8.2.8).
# DataTable: cursor_down/up move the cursor; scroll_top/scroll_bottom jump the cursor to first/last row.
# (scroll_home/scroll_end only scroll the viewport and leave the cursor where it is.)
class VimTable(DataTable):
    BINDINGS = [Binding("j", "cursor_down", show=False), Binding("k", "cursor_up", show=False),
                Binding("g", "scroll_top", show=False), Binding("G", "scroll_bottom", show=False)]
```
- `Binding(key, action, description, show, key_display, priority, tooltip, id, system, group)`. Comma-separate
  alternative keys in one string: `"escape,question_mark"`. Actions are `action_<name>` methods; namespaced actions
  `app.` / `screen.` route explicitly.
- Footer shows only `show=True` bindings for the **focused** widget's chain: keep it to 3-5. Everything else lives in `?` and the palette.
- A focused `Input` swallows printable keys. Use `priority=True` bindings (or `ctrl+` combos) for global actions.
- Built-in help: `HelpPanel` / `KeyPanel` widgets and `action_show_help_panel`; or your own `ModalScreen` listing keys per context.
- Add a **command palette provider** for actions that have no free key (`references/architecture.md`, template `providers.py`).
- Never bind a single key to a destructive action without a confirm modal.

## 4. States: every screen has five

| State | Rule |
|---|---|
| Empty | Say what the list is and how to fill it ("No signals yet. Waiting for the next scan.") |
| Loading | `widget.loading = True` or a `ProgressBar`; keep old data visible while refreshing |
| Error | What failed, why (short), what to do next, and a key to retry. Never a raw traceback in the UI |
| Stale | Show data age ("updated 34 s ago"); dim or badge stale rows; never show old data as live |
| Offline / degraded | A persistent status-line indicator, not a toast that vanishes |

Toasts (`App.notify`) are for transient confirmations, not for errors the user must act on.

## 5. Visual vocabulary

- **Glyph set (single width, monospace safe):** `● ○ ◐ ◉` status, `▲ ▼ ─` change, `✓ ✗ !` result, `▏▎▍▌▋▊▉█` sub-cell bars,
  `▁▂▃▄▅▆▇█` sparklines, `│ ─ ┌ ┐ └ ┘ ├ ┤ ╭ ╮ ╰ ╯` box drawing. Avoid emoji in aligned data: width is unreliable.
- **Hierarchy tools, in order:** position, size (fr/width), `text-style: bold`, `$text` vs `$text-muted`, then color.
- **Borders:** panes get one (`solid`/`tall`), modals `round`. Do not nest borders. Use `border_title` for labels.
- **Selection:** one clear cursor style (`$block-cursor-*`), zebra stripes for wide tables.
- **Numbers:** right-align, fixed decimals, thousands separators, sign on deltas, units in the header not every cell.
- **Truncation:** ellipsize the middle for paths/ids, the end for prose. Never wrap table cells silently.
- **Sub-cell precision:** bars with fractional blocks beat integer-width bars in narrow columns.

## 6. Motion

- Default to none. When used: under 200 ms, `animate()` with `easing`, and cancel on any keypress.
- `TEXTUAL_ANIMATIONS=none|basic|full` controls the global level (set `none` in tests and CI for determinism).
- Never animate data that updates faster than 2 Hz. Cap dashboards at 10-30 FPS of visible change (`TEXTUAL_FPS`, default 60 max).
- Spinner only when a wait exceeds about 300 ms.

## 7. Microcopy

- Verbs for actions ("Refresh", "Pause"), nouns for panes. Lowercase key names in help (`ctrl+p`), one key per line.
- Footer descriptions are 1 word. Titles are static; state goes in `sub_title` or a status line.
- Errors: `Could not reach api.example.com (timeout after 10s). Press r to retry.`

## 8. Accessibility and degradation

- Meaning survives without color, without mouse, and at 60 columns.
- Test `NO_COLOR=1`, `TEXTUAL_COLOR_SYSTEM=standard`, and `ansi-dark`/`ansi-light` themes.
- Keep contrast: prefer theme variables over hand-picked greys; check in a light theme.
- Respect SSH: no per-frame full-screen redraws, no assumption of true color or a GPU terminal.
- Screen readers cannot read TUIs well; offer a `--json`/plain mode for the same data (dual product).

## 9. Anti-patterns (review checklist)

- Clear-and-refill lists on a timer (cursor jumps, flicker).
- More than 5 footer keys; keys that only work in one pane but show everywhere.
- Colour-only status; red/green pairs with nothing else.
- Every widget bordered; nested borders; empty padding rows between everything.
- Modal for non-blocking info; toast for errors that need action.
- Layout shifts when data length changes (set widths; right-align numbers).
- Spinners with no cancel; long operations that block input.
- Hex colors in TCSS; theme-specific hacks.
- Rendering untrusted text as markup.
- No `?` help, no palette, no way to quit that is obvious.
- Designing at one terminal size only.
