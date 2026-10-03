#!/usr/bin/env python3
"""Draw the PWA icons. No image library: numpy coverage plus a PNG writer.

    ../../.venv/bin/python make_icons.py

A hexagon, because the project is named for a honeycomb and every map in it
is drawn on hexagons. Amber on the app's own background.

Maskable icons are cropped by the launcher to any shape inside a circle of
40% radius, so everything that matters stays within that.
"""

import math
import struct
import zlib
from pathlib import Path

import numpy as np

BG = (14, 17, 22)          # --bg
AMBER = (245, 158, 11)     # --accent
HERE = Path(__file__).parent
SS = 4                     # supersampling per axis


def _hex(x, y, cx, cy, r):
    """Inside a pointy-top regular hexagon of circumradius r."""
    dx, dy = np.abs(x - cx), np.abs(y - cy)
    a = r * math.sqrt(3) / 2                      # apothem
    return (dx <= a) & (dy <= r - dx / math.sqrt(3))


def _rounded(x, y, n, rad):
    cx = np.clip(x, rad, n - rad)
    cy = np.clip(y, rad, n - rad)
    return (x - cx) ** 2 + (y - cy) ** 2 <= rad ** 2


def draw(n, corner=0.0, scale=1.0):
    m = n * SS
    y, x = np.mgrid[0:m, 0:m].astype(np.float64) + 0.5
    x, y = x / SS, y / SS
    c = n / 2
    outer = _hex(x, y, c, c, 0.34 * n * scale)
    inner = _hex(x, y, c, c, 0.17 * n * scale)
    core = _hex(x, y, c, c, 0.075 * n * scale)
    bg = _rounded(x, y, n, corner * n) if corner else np.ones_like(outer)

    amber = (outer & ~inner) | core
    img = np.zeros((m, m, 4))
    img[bg] = (*BG, 255)
    img[amber & bg] = (*AMBER, 255)
    # Box-filter the supersamples down to n x n.
    img = img.reshape(n, SS, n, SS, 4).mean(axis=(1, 3))
    return np.round(img).astype(np.uint8)


def write_png(path, rgba):
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[i].tobytes() for i in range(h))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b""))


def svg():
    def pts(r):
        return " ".join(
            f"{32 + r * math.cos(math.radians(90 + 60 * k)):.2f},"
            f"{32 + r * math.sin(math.radians(90 + 60 * k)):.2f}"
            for k in range(6))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="14" fill="rgb{BG}"/>'
        f'<polygon points="{pts(21.8)}" fill="rgb{AMBER}"/>'
        f'<polygon points="{pts(10.9)}" fill="rgb{BG}"/>'
        f'<polygon points="{pts(4.8)}" fill="rgb{AMBER}"/>'
        "</svg>\n")


if __name__ == "__main__":
    write_png(HERE / "icon-192.png", draw(192, corner=0.22))
    write_png(HERE / "icon-512.png", draw(512, corner=0.22))
    # Full bleed, motif inside the 40% safe circle (0.34 * 1.0 < 0.40).
    write_png(HERE / "maskable-512.png", draw(512))
    # iOS rounds the corners itself and dislikes transparency.
    write_png(HERE / "apple-touch-icon.png", draw(180))
    (HERE / "icon.svg").write_text(svg())
    print("ok")
