# AI-native TUIs

Read when: building a chat/agent front end, streaming model output, adding approvals, exposing a TUI to agents,
or letting an agent build and verify a TUI. Textual APIs verified on 8.2.8; ecosystem claims come from 2026
articles and are labelled.

## 1. Anatomy of an agent/chat UI in Textual

```
Header
VerticalScroll #chat          messages: user, assistant (Markdown), tool-call blocks (Collapsible)
Static #status                model | tokens | elapsed | state: idle|thinking|running-tool|waiting-approval
TextArea/Input #prompt        multi-line input, history on up/down, Enter/ctrl+enter to send
Footer
```
- **Anchor scrolling** while streaming: `chat.anchor()` keeps the view pinned to the bottom until the user scrolls up
  (`Widget.anchor(anchor=True)`); `chat.scroll_end(animate=False)` after mounting a message.
- **State indicator is data, not decoration**: a widget with a stable id (`#status`) whose text is one of a fixed set of
  states. Humans get feedback and agents/tests get something to wait on.
- **Esc cancels**: the running reply is an exclusive worker; `Esc` calls `worker.cancel()`; the UI shows "cancelled".

```python
@work(exclusive=True, group="reply")
async def reply(self, prompt: str) -> None:
    chat = self.query_one("#chat", VerticalScroll)
    md = Markdown(open_links=False)                    # do not auto-open model-supplied links
    await chat.mount(md)
    chat.anchor()
    stream = Markdown.get_stream(md)                   # batches tokens; only last block re-renders
    self.set_state("thinking")
    try:
        async for event in self._backend.stream(prompt):        # normalized events, see section 4
            if isinstance(event, TextDelta):
                await stream.write(sanitize(event.text))
            elif isinstance(event, ToolCall):
                await self.show_tool_call(event)                # Collapsible block
    except Exception as exc:
        self.notify(f"Backend error: {exc}", severity="error")
    finally:
        await stream.stop()
        self.set_state("idle")
```

## 2. Treat model output as hostile

Model text, tool output, file contents and web content can contain: Textual/Rich markup (`[b]`, `[@click=...]`),
ANSI/OSC escape sequences (cursor moves, clipboard writes, hyperlinks, title changes), homoglyphs and bidi controls,
or instructions aimed at the agent.

```python
import re
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")          # keeps \n (0x0a) and \t (0x09)
_BIDI = re.compile(r"[‪-‮⁦-⁩]")
def sanitize(s: str) -> str:
    return _BIDI.sub("", _CTRL.sub("", s))
```
- Plain display: `Text(sanitize(s))` or `RichLog(markup=False)`. If a `Label`/`Static` must show a string, escape it:
  `from textual.markup import escape; Label(escape(s))`.
- Markdown widget: `open_links=False` and handle link clicks yourself (show the URL, ask before opening).
- Never render model output as Textual markup or CSS, never `eval` it, never let it choose widget ids, key bindings or file paths.
- Show approvals with the **exact** command/diff, not a summary the model wrote. Truncation must never hide the dangerous tail.
- Log every executed action with who approved it. Do not auto-approve based on anything the model said.

## 3. Human-in-the-loop controls

Spectrum from "approve each" to "auto within a sandbox". Implement as a policy object the UI consults:

```python
class Decision(Enum):
    ALLOW_ONCE = 1
    ALLOW_SESSION = 2
    DENY = 3

class Approval(ModalScreen[Decision]):
    BINDINGS = [("y", "allow", "Allow once"), ("a", "always", "Allow this session"), ("n,escape", "deny", "Deny")]
    def __init__(self, title: str, exact: str) -> None: ...
    def action_allow(self) -> None:  self.dismiss(Decision.ALLOW_ONCE)
    def action_always(self) -> None: self.dismiss(Decision.ALLOW_SESSION)
    def action_deny(self) -> None:   self.dismiss(Decision.DENY)

decision = await self.push_screen_wait(Approval("Run command", cmd))   # inside a worker
```
Default to deny on `Esc` and on any error. Persist session-level allows in memory only unless the user opts in.

## 4. Decouple UI from the model backend

Normalize every backend (API, subprocess, ACP agent) to a small event stream, then render events:

```python
@dataclass(frozen=True)
class TextDelta:
    text: str

@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict

@dataclass(frozen=True)
class ToolResult:
    id: str
    ok: bool
    output: str

@dataclass(frozen=True)
class Done:
    reason: str

@dataclass(frozen=True)
class Failed:
    message: str
```
This is the architecture Toad uses (Textual front end plus a back-end subprocess speaking the Agent Client Protocol)
[2026 article]. It lets you swap providers, replay recorded sessions in tests, and screenshot any state with a fake backend.

## 5. Pure-reducer UI state

`(state, event) -> (state, effects)` for chat state (messages, running run, pending approval). Unit test the reducer with
recorded event lists; the widgets only render `state`. Makes AI-driven UIs auditable and replayable (`architecture.md` section 8).

## 6. Generative / adaptive UI (be conservative)

If a model may decide what to show, let it emit **data** (a validated spec) that maps onto a whitelist of trusted components:

```python
class Spec(BaseModel):                       # pydantic: validate and cap sizes
    type: Literal["text", "table", "progress"]
    title: str = Field(max_length=80)
    rows: list[list[str]] = Field(default_factory=list, max_length=200)

BUILDERS = {"text": build_text, "table": build_table, "progress": build_progress}
def render(spec: Spec) -> Widget:
    return BUILDERS[spec.type](spec)         # unknown type is a validation error, not a fallback
```
Cap depth, rows, string lengths; sanitize every string; no user-controlled ids or classes; no code paths that execute spec content.
Related research and protocols (2026): A2UI / AG-UI generative UI specs, "just-in-time interfaces" papers. Nothing terminal
specific has matured; the whitelist-renderer pattern is the safe subset.

## 7. Make your TUI agent-testable

Agents (and CI) prefer structured state over pixels:
- Stable ids on every meaningful widget; a `#status`/mode widget with a closed set of values.
- A `--json` (or plain) CLI over the same core: agents should call the core, not drive the UI, whenever they can.
- In-process tests with `run_test` (Textual is its own DOM). For an agent looking at a running app, use
  `scripts/tui_shot.py --outline` (widget tree as JSON: type, id, classes, focus, visibility, region, text) and `--text` / `--png`.
- `TEXTUAL_PRESS="down,enter"` presses keys at startup; `App.run(auto_pilot=fn)` scripts a real run.
- For non-Textual TUIs, use PTY tools (agent-tui, tui-use, ghostty-automator, tmux) and follow observe, act, verify:
  wait for an observable condition, never sleep. The 2026 research argument (C1, "Terminal apps need a DOM"): expose
  durable named regions (`@app.status[value=idle]`) instead of screenshots and ANSI scraping. Textual already has that DOM.

## 8. Agent workflow for building a TUI (the closed loop)

1. Write the design in 10 lines: paradigm, panes, keys, states, colors (`design-system.md`).
2. Scaffold from `assets/dashboard-template/`; put data behind a `Source` protocol with a `FakeSource`.
3. Implement one pane; run `tui_shot.py --text` at 3 sizes; fix; run `--png` and look.
4. Write Pilot tests for behavior; snapshot only stable screens.
5. Review with the checklist in `SKILL.md`; use a fresh look at the PNG against the anti-pattern list.
   An LLM-as-judge pass on the PNG is useful for taste (hierarchy, density, alignment), not for correctness: correctness is tests.

## 9. Frontier notes (verify before relying on them)

- Streaming Markdown in Textual (v5.0+, built for Toad) is production-grade; use `MarkdownStream`.
- Terminal capabilities are improving (Kitty keyboard protocol in Textual 8.2.7+, synchronized output in other
  frameworks). Do not assume them: degrade gracefully.
- Agent-terminal automation (ghostty-automator, agent-tui, tui-use) is young; prefer in-process Textual tests, use PTY tools for end-to-end only.
- Ideas worth prototyping: an `--outline` endpoint that a supervising agent polls; replayable sessions (record events, replay to a screenshot);
  approval UIs that show a real diff; a "why did it do that" panel driven by the event log.
