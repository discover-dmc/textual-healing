# Styling and theming

Read when: writing TCSS, laying out panes, defining a theme, making it degrade on 16-color terminals.
Verified on Textual 8.2.8.

## 1. Where CSS lives

- `CSS_PATH = "app.tcss"` on the App (relative to the file): app-level layout and overrides.
- `DEFAULT_CSS = """..."""` inside a widget or screen class: self-contained defaults, lowest priority.
- `CSS = """..."""` string on the App: fine for tiny apps.
- Dev mode hot-reloads CSS: `textual run --dev app.py` (needs `textual-dev`).

## 2. Selectors and pseudo-classes

`Type`, `#id`, `.class`, `Parent > Child`, `A B` (descendant), `A.class:hover`, comma lists.
Pseudo-classes present in 8.2.8: `:hover :focus :focus-within :blur :disabled :enabled :dark :light :inline
:first-child :last-child :first-of-type :last-of-type :odd :even :can-focus`, plus `:ansi` and `:nocolor`
(color-degraded modes). Screens get breakpoint classes such as `-narrow` (see 5). Toggle classes from Python
with `add_class`, `remove_class`, `set_class(bool, name)`, `toggle_class`, `update_classes({name: bool})`.

## 3. Layout

```
layout: vertical | horizontal | grid          # default vertical
grid-size: 3 2;  grid-columns: 1fr 2fr 1fr;  grid-rows: auto 1fr;  grid-gutter: 1 2;
column-span: 2;  row-span: 2;                 # on grid children
dock: top | bottom | left | right;            # pins to an edge, ignores layout flow
layer / layers: base overlay;                 # z-order
overlay: screen;                              # e.g. popups anchored to the screen
align: center middle;      content-align: center middle;
width|height: 20 | 50% | 1fr | auto | 100vw | 50vh;   min-/max- variants
margin: 1 2;  padding: 0 1;  offset: 1 0;
overflow: auto | hidden | scroll;   scrollbar-size: 1 1;   scrollbar-gutter: stable;
display: block | none;       visibility: visible | hidden;
```
- Units are terminal **cells**. `fr` shares remaining space; it needs a parent with a definite size.
- `height: auto` on a container inside a scrolling parent is fine; `1fr` inside `auto` collapses.
- Containers (`textual.containers`): `Vertical`, `Horizontal`, `Grid`, `VerticalScroll`, `HorizontalScroll`,
  `ScrollableContainer`, `Center`, `Middle`, `CenterMiddle`, `Right`, `ItemGrid`, `VerticalGroup`,
  `HorizontalGroup` (auto-sized, no scroll). Use `Vertical/Horizontal` for panes and `*Group` for small clusters.
- Common app frames: three-pane = `Horizontal` of a fixed-width sidebar (`width: 28`) + `1fr` main + optional
  `width: 40` detail; dashboard = `Grid` with `grid-size: 2`; header + list = `Header`, body `1fr`, `Footer`.

## 4. Borders, text, effects

- Border types: `ascii blank block dashed double heavy hidden hkey inner none outer panel round solid tab tall
  thick vkey wide`. Use `round` for modals and `solid`/`tall` for panes; avoid drawing borders around everything:
  every border costs two rows/columns of density.
- `border: round $primary;` `border-title-align`, and `border_title` in Python for labeled panes.
- `text-style: bold | italic | underline | strike | reverse | dim` (combine). Do not rely on italics.
- `color: $text;` `background: $surface;` `tint`, `opacity: 70%`, `background: $primary 20%` (alpha).
- `hatch`, `keyline`, `outline` exist for special effects; prefer `$panel` and `$boost` layering for depth.

## 5. Responsive layouts

```python
class MyApp(App):
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (80, "-wide"), (120, "-very-wide")]
    VERTICAL_BREAKPOINTS = [(0, "-short"), (24, "-tall")]     # optional
```
```css
Screen.-narrow #detail { display: none; }
Screen.-narrow #items  { width: 1fr; }
Screen.-very-wide #sidebar { width: 36; }
```
Textual adds/removes those classes on the Screen as the terminal resizes (a `Screen` can override the lists).
Prefer this to a hand-written `on_resize`. Test at 60x20, 100x30, 160x45.

## 6. Themes

A theme is 11 base colors (only `primary` required): `primary secondary accent foreground background surface
panel boost warning error success`; Textual derives `-lighten-1..3`, `-darken-1..3`, `$text`, `$text-muted`,
`$text-disabled`, `$text-primary|secondary|accent|warning|error|success`, `$*-muted` (70% blend with background),
and widget variables (`$border`, `$border-blurred`, `$block-cursor-*`, `$input-*`, `$scrollbar*`, `$link-*`,
`$footer-*`, `$button-*`).

```python
from textual.theme import Theme
MIDNIGHT = Theme(name="midnight", primary="#7aa2f7", secondary="#bb9af7", accent="#e0af68",
                 foreground="#c0caf5", background="#1a1b26", surface="#24283b", panel="#2f3549",
                 success="#9ece6a", warning="#e0af68", error="#f7768e", dark=True,
                 variables={"footer-key-foreground": "#7aa2f7"})
def on_mount(self) -> None:
    self.register_theme(MIDNIGHT)
    self.theme = "midnight"                     # App.dark was removed in 0.86: use theme
```
- Built-ins (8.2.8): ansi-dark, ansi-light, atom-one-dark, atom-one-light, catppuccin-frappe/latte/macchiato/mocha,
  dracula, flexoki, gruvbox, monokai, nord, rose-pine (+dawn, moon), solarized-dark/light, textual-dark, textual-light,
  tokyo-night. Users switch themes from the command palette (Ctrl+P) for free.
- App-specific variables: override `get_theme_variable_defaults()` and use them as `$my-var` in TCSS.
- `TEXTUAL_THEME=nord` env var sets the startup theme. `textual colors` previews the whole palette live.
- Contrast: check body text against `$surface`/`$panel` in a light and a dark theme. Prefer `$text`, `$text-muted`
  over custom greys; muted is for secondary info, not for anything the user must read.

## 7. Design in layers (monochrome, 16 colors, true color)

1. **Structure first**: hierarchy through layout, borders, spacing and `text-style`, so it reads with no color.
2. **16-color safe**: `ansi-dark` / `ansi-light` themes use the terminal's own palette, so the app matches the
   user's terminal theme. Preview with `TEXTUAL_COLOR_SYSTEM=standard` (values follow Rich: `standard`, `256`, `truecolor`).
3. **True color polish**: your custom theme. Enhancement only.
- Offer the choice: keep your custom theme as default but do not fight `ansi-*` or `NO_COLOR` users. Style
  `Screen:nocolor` / `Screen:ansi` differences if your design depends on subtle tints.
- Semantic tokens, never raw hex, in TCSS. If you need a status color, add a theme variable (`$status-down`).
- Color-blind safety: red/green pairs need a second cue (glyph, sign, word). Verified pattern in the template:
  `▲ +0.6%` green, `▼ -1.4%` red, `● ○ ◐` status glyphs.

## 8. Textual markup vs Rich markup

- Widgets that take strings (`Label`, `Static`, `Button`, `Footer` text) parse **Textual markup**:
  `"[b]bold[/b] [$success]ok[/] [@click=app.quit]quit[/]"` (style variables and click actions supported).
- `RichLog(markup=False)`, `Text(...)`, `Content.styled(...)` avoid parsing. For untrusted text use these
  or escape: `from textual.markup import escape`.
- Rich renderables (Table, Syntax, Panel) work inside `Static`, `RichLog`, and DataTable cells, but cost more per
  repaint than native widgets; do not put a Rich Table in a widget that updates 10 times a second.

## 9. Style quick rules

- One accent color for focus/selection (`$primary`), one for emphasis (`$accent`), status colors only for status.
- Spacing: pad panels `0 1`; avoid empty rows unless they separate groups. Density is a feature.
- Headers `text-style: bold`, secondary text `$text-muted`, disabled `$text-disabled`.
- Focus must be visible: keep `:focus` border/background distinct (default `$border` uses `$primary`).
- Unicode width: box-drawing and block glyphs are single width; emoji and some symbols are not. Test alignment of
  any emoji in tables, or avoid emoji in data columns.
