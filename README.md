# textual-healing

A [Claude Code](https://claude.com/claude-code) skill for building, testing and visually verifying terminal UIs with [Textual](https://textual.textualize.io/) (Python).

Verified against **Textual 8.2.8** (September 2026). The skill checks the installed version first and points to a version-drift table when it differs.

## Why

Existing TUI skills are either framework-agnostic design notes with no Textual APIs, or Textual tutorials written for old versions (for example `Static.renderable`, `App.dark` and `Select.BLANK` were all removed or renamed). None of them ship code that has been run, and none lets the agent actually see the interface it is building.

This skill aims to fix that:

- Current Textual 8.x APIs, with a break history from 0.77 to 8.x and an old-to-new map.
- A design system expressed in Textual terms: layout paradigms, keyboard layers, states, color in three tiers, motion, accessibility, anti-patterns.
- A performance playbook with measured numbers, not folklore.
- A tested dashboard template.
- A headless screenshot tool so the agent can look at its own work.

## Install

Copy the skill folder into your Claude Code skills directory:

```bash
git clone https://github.com/discover-dmc/textual-healing.git
cp -R textual-healing/textual-tui ~/.claude/skills/
```

It activates on Textual and TUI work. No configuration needed.

## What is inside

```
textual-tui/
  SKILL.md                     workflow, golden rules, checklist, index
  references/
    architecture.md            structure, messages, reactivity, screens, workers, data feeds, shutdown
    widgets-and-data.md        widget picker, keyed DataTable, streaming Markdown, custom widgets
    styling-and-theming.md     TCSS, layout, breakpoints, themes, ansi and NO_COLOR degradation
    design-system.md           layout paradigms, keys, states, microcopy, motion, accessibility
    testing-and-verification.md  Pilot, snapshots, fakes, CI, the agent verification loop
    performance.md             flicker and lag rules, profiling, benchmark you can rerun
    ai-native-tui.md           chat and agent UIs, streaming, approvals, sanitizing model output
    version-notes.md           breaking changes and upgrade routine
    pitfalls.md                symptom, cause, fix
  scripts/tui_shot.py          headless render to text, SVG, PNG, or a JSON widget tree
  assets/dashboard-template/   starter app with 9 Pilot tests
```

`SKILL.md` is short and loads references on demand to keep token cost low.

## The screenshot tool

`tui_shot.py` runs any Textual app headless (no terminal, no tmux) and reports what it looks like:

```bash
S=~/.claude/skills/textual-tui/scripts/tui_shot.py
uv run python $S pkg.app:MyApp --size 100x30 --text                        # plain text render
uv run python $S pkg.app:MyApp --size 60x20 --press "question_mark" --text # after key presses
uv run python $S pkg.app:MyApp --png /tmp/ui.png                           # image the agent can view
uv run python $S pkg.app:MyApp --outline                                   # widget tree as JSON
```

Run it from the app's own environment so imports resolve. PNG export uses `rsvg-convert`, the `cairosvg` package, or macOS `qlmanage`. The text mode calls a private compositor method that mirrors Textual's `export_screenshot`; if a future release breaks it, `--svg` uses the public API.

## The template

```bash
cp -R textual-tui/assets/dashboard-template ./my-app && cd my-app
uv sync && uv run python -m pytest -q && uv run dashboard
```

It shows the patterns the skill teaches: an injected data source, in-place keyed DataTable updates that preserve the cursor, an exclusive worker for refresh, untrusted text kept out of markup, a custom theme with a non-color cue for status, modal help, a command palette provider, and responsive breakpoints.

## How it was verified

- Every API name in the docs was checked against an installed Textual 8.2.8.
- Doc snippets that make behavioral claims were executed. This caught a real error in the draft: on `DataTable`, `scroll_home` and `scroll_end` only scroll the viewport, while `scroll_top` and `scroll_bottom` move the cursor.
- The template passes 9 of 9 tests from a clean `uv sync`, and a mutation check confirmed the untrusted-text test fails when the guard is removed.
- Measured on Apple silicon, headless, 5 columns: `DataTable.clear()` plus re-add reset the cursor to row 0 every time and settled 1.5x to 2x slower at 1000 rows, while updating only changed cells cost about 0.3 ms.

## Known limits

- Not verified: whether Textual emits DEC synchronized output (mode 2026), and what triggers the `:nocolor` pseudo-class.
- Statements about other tools (Toad, ghostty-automator, agent-tui) come from secondary sources.
- Textual releases often. Behavior on versions newer than 8.2.8 is unverified, and the skill tells the agent to check.

## Security

The skill and its scripts make no network calls and read no credentials. `tui_shot.py` imports and runs the app you point it at, so only run it on code you trust.

## License

[MIT](LICENSE)
