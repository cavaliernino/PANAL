#!/usr/bin/env python3
"""Draw the PWA icons from the ACHEZ isotipo.

    python3 make_icons.py

The favicon (icon.svg) is the flame alone on a transparent ground, so it
sits on whatever the browser tab is. The PWA icons put it at 80% of a
#1F2D3D tile with rounded corners, the canvas's "favicon oscuro": launchers
need an opaque, full shape, and iOS dislikes transparency.
achez.svg is used as-is — no recolouring, no reshaping — and only scaled and
centred here.

The PNGs are rasterised by headless Chrome, since nothing else on hand
renders SVG gradients; set CHROME to another binary if it lives elsewhere.

Maskable icons are cropped by the launcher to any shape inside a circle of
40% radius, so the flame's bounding box stays within that.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BG = "#1F2D3D"            # the favicon tile in the canvas
CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

ISO_W, ISO_H = 138, 166   # achez.svg's viewBox


def isotipo():
    """achez.svg's drawing, without its outer <svg> or comment."""
    src = (HERE / "achez.svg").read_text()
    body = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    return re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()


def svg(n=64, corner=112 / 512, height=0.80, tile=True):
    """A square of side n with the flame `height` of it tall, centred, on a
    #1F2D3D tile unless `tile` is false."""
    s = height * n / ISO_H
    tx, ty = (n - ISO_W * s) / 2, (n - ISO_H * s) / 2
    rx = f' rx="{corner * n:g}"' if corner else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}">'
        + (f'<rect width="{n}" height="{n}"{rx} fill="{BG}"/>' if tile else "") +
        f'<g transform="translate({tx:.3f} {ty:.3f}) scale({s:.5f})">'
        f"{isotipo()}</g></svg>\n")


def png(path, n, **kw):
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text(
            "<!doctype html><style>html,body{margin:0;background:transparent}"
            f"svg{{display:block;width:{n}px;height:{n}px}}</style>"
            + svg(n, **kw))
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             f"--user-data-dir={tmp}/profile",
             "--force-device-scale-factor=1",
             "--default-background-color=00000000",
             f"--window-size={n},{n}", f"--screenshot={path.resolve()}",
             page.as_uri()],
            check=True, capture_output=True, timeout=60)


if __name__ == "__main__":
    # Favicon: transparent, the flame as tall as the square allows.
    (HERE / "icon.svg").write_text(svg(tile=False, height=1.0))
    png(HERE / "icon-192.png", 192)
    png(HERE / "icon-512.png", 512)
    # Full bleed; the flame's half-diagonal is 0.36 n, inside the 0.40 circle.
    png(HERE / "maskable-512.png", 512, corner=0, height=0.55)
    # iOS rounds the corners itself and dislikes transparency.
    png(HERE / "apple-touch-icon.png", 180, corner=0)
    print("ok")
