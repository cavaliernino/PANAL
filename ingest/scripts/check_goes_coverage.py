#!/usr/bin/env python3
"""Does GOES-East actually see all of Chile, at every hour?

    python scripts/check_goes_coverage.py --hours 24

Coverage was measured once, at 18:00 local, and came back 100% usable from
Arica to Magallanes. That was one scan. The glint block-out is a solar-angle
effect, so it varies through the day and the claim cannot be trusted until
it has been checked across a full diurnal cycle.

Anything built on GOES has to know where and when its own blind spots are.
A blocked pixel reports no fire for the same reason a closed eye does.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panal_ingest import goes  # noqa: E402

BANDS = [
    ("Arica–Antofagasta", -24, -18),
    ("Atacama–Coquimbo", -32, -24),
    ("Valparaíso–Maule", -36, -32),
    ("Ñuble–Araucanía", -39, -36),
    ("Los Ríos–Lagos", -44, -39),
    ("Aysén", -49, -44),
    ("Magallanes", -56, -49),
]
LON = (-76, -66)
UTC_OFFSET = -3


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hours", type=int, default=24)
    a = p.parse_args()

    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0,
                                                   microsecond=0)
    rows = []
    for back in range(a.hours, 0, -1):
        when = now - dt.timedelta(hours=back)
        try:
            scans = goes.list_scans(when)
            if not scans:
                continue
            scan = scans[0]
            with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
                path = goes.download(scan.url, tmp.name)
        except Exception as exc:                        # noqa: BLE001
            print(f"  ! {when:%H:%M} UTC: {str(exc)[:60]}", file=sys.stderr)
            continue

        try:
            per_band = []
            for name, lo, hi in BANDS:
                r = goes.blocked_fraction(path, lo, hi, *LON)
                pct = 100 * r["usable"] / r["total"] if r["total"] else float("nan")
                per_band.append(pct)
        finally:
            Path(path).unlink(missing_ok=True)

        rows.append((scan.start, per_band))
        local = scan.start + dt.timedelta(hours=UTC_OFFSET)
        print(f"  {scan.start:%H:%M} UTC / {local:%H:%M} local  "
              + "  ".join(f"{v:5.1f}" for v in per_band), file=sys.stderr)

    if not rows:
        sys.exit("sin barridos")

    print(f"\n{'franja':<20}{'mín':>8}{'media':>8}{'peor hora (local)':>20}")
    print("-" * 56)
    worst_overall = 100.0
    for i, (name, _, _) in enumerate(BANDS):
        vals = [(r[1][i], r[0]) for r in rows]
        lo, when = min(vals)
        avg = sum(v for v, _ in vals) / len(vals)
        worst_overall = min(worst_overall, lo)
        local = when + dt.timedelta(hours=UTC_OFFSET)
        print(f"{name:<20}{lo:>7.1f}%{avg:>7.1f}%{local:%H:%M}".ljust(48))

    print(f"\n{len(rows)} barridos muestreados, uno por hora.")
    if worst_overall >= 99.9:
        print("Cobertura completa en todo Chile, a toda hora. "
              "La salvedad del ciclo diurno queda cerrada.")
    else:
        print(f"Peor cobertura observada: {worst_overall:.1f}%. "
              "Esos huecos deben mostrarse como 'sin observación', "
              "nunca como ausencia de fuego.")


if __name__ == "__main__":
    main()
