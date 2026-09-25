#!/usr/bin/env python3
"""Run a Textual app headless, optionally press keys, then dump what it looks like.

Gives an agent eyes on a TUI with no PTY, no tmux and no screenshots of a real terminal.

Usage (from the app's project, so its imports resolve):
    uv run python tui_shot.py app.py:MyApp --size 100x30 --text
    uv run python tui_shot.py pkg.module:make_app --press "down,down,enter" --svg out.svg
    uv run python tui_shot.py app.py:MyApp --png out.png      # SVG -> PNG if a rasterizer exists

Target is `path/to/file.py:Name` or `dotted.module:Name`. `Name` is an App subclass or a
zero-argument callable returning an App instance (use the callable to inject fakes).

Flags:
    --size WxH      terminal size in cells (default 100x30)
    --press KEYS    comma separated Textual key names, e.g. "tab,down,ctrl+p,escape,question_mark"
    --wait SECS     extra settle time before capture (default 0.3)
    --text          print a plain-text render to stdout (cheap, greppable, no color)
    --svg PATH      write an SVG screenshot
    --png PATH      write a PNG (needs macOS qlmanage, rsvg-convert, or the cairosvg package)
    --query SEL     also print `#id` / CSS matches: type, id, classes, display, region

NOTE: the text dump uses App.screen._compositor, a private API that mirrors what
App.export_screenshot does internally. If a future Textual major breaks it, fall back
to --svg (public export_screenshot).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console
from textual.app import App


def load_target(spec: str) -> Any:
    ref, _, name = spec.rpartition(":")
    if not ref or not name:
        sys.exit(f"target must look like path/to/file.py:Name or pkg.module:Name, got {spec!r}")
    if ref.endswith(".py") or "/" in ref:
        path = Path(ref).resolve()
        sys.path.insert(0, str(path.parent))
        mod_spec = importlib.util.spec_from_file_location(path.stem, path)
        if mod_spec is None or mod_spec.loader is None:
            sys.exit(f"cannot import {path}")
        module = importlib.util.module_from_spec(mod_spec)
        sys.modules[path.stem] = module
        mod_spec.loader.exec_module(module)
    else:
        sys.path.insert(0, str(Path.cwd()))
        module = importlib.import_module(ref)
    return getattr(module, name)


def make_app(target: Any) -> App[Any]:
    app = target() if callable(target) else target
    if not isinstance(app, App):
        sys.exit(f"{target!r} did not produce a Textual App instance")
    return app


def render_text(app: App[Any]) -> str:
    width, height = app.size
    console = Console(
        width=width,
        height=height,
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        record=True,
        legacy_windows=False,
        safe_box=False,
    )
    console.print(
        app.screen._compositor.render_update(
            full=True, screen_stack=app.app._background_screens, simplify=False
        )
    )
    return console.export_text()


def _text_of(w: Any) -> str | None:
    for attr in ("label", "content", "value"):
        v = getattr(w, attr, None)
        if v is None or callable(v):
            continue
        plain = getattr(v, "plain", None)
        if isinstance(plain, str):
            return plain
        if isinstance(v, str):
            return v
    return None


def outline(w: Any) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": type(w).__name__,
        "id": w.id,
        "classes": sorted(w.classes),
        "focused": w.has_focus,
        "visible": w.display and w.region.area > 0,
        "region": f"{w.region.x},{w.region.y} {w.region.width}x{w.region.height}",
    }
    text = _text_of(w)
    if text:
        node["text"] = text[:80]
    kids = [outline(c) for c in w.children]
    if kids:
        node["children"] = kids
    return node


def svg_to_png(svg: Path, png: Path) -> str | None:
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-o", str(png), str(svg)], check=True)
        return "rsvg-convert"
    try:
        import cairosvg  # type: ignore[import-not-found]

        cairosvg.svg2png(url=str(svg), write_to=str(png))
        return "cairosvg"
    except ImportError:
        pass
    if shutil.which("qlmanage"):  # macOS Quick Look thumbnailer
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["qlmanage", "-t", "-s", "1600", "-o", tmp, str(svg)],
                check=True,
                capture_output=True,
            )
            made = next(Path(tmp).glob("*.png"), None)
            if made is not None:
                shutil.move(str(made), png)
                return "qlmanage"
    return None


async def run(args: argparse.Namespace) -> int:
    width, height = (int(x) for x in args.size.lower().split("x"))
    app = make_app(load_target(args.target))
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        await app.workers.wait_for_complete()
        for key in [k for k in args.press.split(",") if k]:
            await pilot.press(key)
            await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause(args.wait)
        if args.text:
            print(render_text(app))
        if args.outline:
            print(json.dumps(outline(app.screen), indent=1))
        if args.query:
            for w in app.screen.query(args.query):
                print(
                    f"{type(w).__name__} id={w.id!r} classes={sorted(w.classes)} "
                    f"display={w.display} region={w.region}"
                )
        if args.svg or args.png:
            svg_text = app.export_screenshot()
            svg_path = Path(args.svg) if args.svg else Path(tempfile.mkdtemp()) / "shot.svg"
            svg_path.write_text(svg_text)
            if args.svg:
                print(f"wrote {svg_path}", file=sys.stderr)
            if args.png:
                used = svg_to_png(svg_path, Path(args.png))
                if used:
                    print(f"wrote {args.png} via {used}", file=sys.stderr)
                else:
                    print(
                        "no SVG rasterizer found (install rsvg-convert or cairosvg); "
                        "use --svg and open it in a browser",
                        file=sys.stderr,
                    )
                    return 2
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("target")
    p.add_argument("--size", default="100x30")
    p.add_argument("--press", default="")
    p.add_argument("--wait", type=float, default=0.3)
    p.add_argument("--text", action="store_true")
    p.add_argument("--svg")
    p.add_argument("--png")
    p.add_argument("--query")
    p.add_argument("--outline", action="store_true")
    args = p.parse_args()
    if not (args.text or args.svg or args.png or args.query or args.outline):
        args.text = True
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
