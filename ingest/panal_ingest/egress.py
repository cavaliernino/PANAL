"""Egress — whether people can get out, from OpenStreetMap.

People died in Viña del Mar in narrow dead-end hillside streets. That
geometry does not change between fire seasons, which makes it the most
actionable thing in the whole exposure map: knowing it in October is worth
more than watching the jam happen in February.

It also needs nobody's permission. Live traffic requires TomTom or the Waze
for Cities partnership; road *structure* is in OSM today.

## What is measured

Per H3 cell, from the road graph:

* **link-node ratio** — links divided by nodes, the standard urban-planning
  connectivity measure. A gridded street network runs about 1.4 or higher; a
  cul-de-sac suburb sits near 1.0 or below. Low means few ways out.
* **dead ends** — degree-1 nodes that are not just the edge of the extract.
* **best road class** — whether anything larger than a service lane touches
  the cell. A neighbourhood whose only link is a `residential` is in a
  different category from one on a `secondary`.
* **road length** by class, so density can be normalised.

## The gap was measured, and it is smaller than feared

OSM is volunteered, so the worry was that coverage would be thinnest
exactly where danger is highest — the passages of *tomas* and informal
hillside settlements. Measured over Valparaíso, that is mostly not what
happens:

    weighted by population                     95.7%
    cells with >= 10 dwellings                 95.2%
    those on slopes above 25 degrees           86.1%
    raw cell count                             44.2%

The raw figure is the misleading one and should never be quoted alone: it
counts a cell holding 1.3 dwellings the same as one holding 156. The
unmapped cells are nearly empty — 24,601 of them hold 79,945 people
between them, against 1,786,955 in the mapped ones.

What stays true is that the few steep, genuinely populated cells that are
unmapped are exactly the ones that matter. `egress_deficit` returns None
for them rather than a score: an unmapped *toma* is the most dangerous case
there is, and scoring it as well-connected would be the worst failure mode
this project could have.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "osm"
PBF = CACHE / "chile-latest.osm.pbf"
SOURCE = "https://download.geofabrik.de/south-america/chile-latest.osm.pbf"

# Ranked by how much traffic they can actually carry out of a neighbourhood.
ROAD_RANK = {
    "motorway": 9, "motorway_link": 8,
    "trunk": 8, "trunk_link": 7,
    "primary": 7, "primary_link": 6,
    "secondary": 6, "secondary_link": 5,
    "tertiary": 5, "tertiary_link": 4,
    "unclassified": 3,
    "residential": 3,
    "living_street": 2,
    "service": 2,
    "track": 1,
    "path": 0, "footway": 0, "pedestrian": 0, "steps": 0,
}

# Anything a vehicle could leave by. Footways are excluded from the graph
# because an evacuation on foot up a burning ravine is not egress.
DRIVABLE = {k for k, v in ROAD_RANK.items() if v >= 1}


class _RoadCollector:
    """Streams a PBF and accumulates the road graph per H3 cell.

    Streaming rather than loading: the Chile extract is 348 MB and holds
    millions of nodes, and only those referenced by drivable ways matter.
    """

    def __init__(self, res: int, keep_cells=None):
        import osmium

        self.res = res
        self.keep = set(keep_cells) if keep_cells else None
        self.node_cells: dict[int, str] = {}
        self.node_degree: dict[int, int] = defaultdict(int)
        self.cell_links: dict[str, int] = defaultdict(int)
        self.cell_length: dict[str, float] = defaultdict(float)
        self.cell_rank: dict[str, int] = defaultdict(int)
        self._osmium = osmium

    def make_handler(self):
        import h3
        import osmium

        outer = self

        class Handler(osmium.SimpleHandler):
            def way(self, w):
                hw = w.tags.get("highway")
                if hw not in DRIVABLE:
                    return
                rank = ROAD_RANK.get(hw, 0)

                coords = []
                for n in w.nodes:
                    try:
                        coords.append((n.ref, n.location.lat, n.location.lon))
                    except osmium.InvalidLocationError:
                        continue
                if len(coords) < 2:
                    return

                for ref, lat, lon in coords:
                    cell = outer.node_cells.get(ref)
                    if cell is None:
                        cell = h3.latlng_to_cell(lat, lon, outer.res)
                        outer.node_cells[ref] = cell
                    if outer.keep is not None and cell not in outer.keep:
                        continue
                    if rank > outer.cell_rank[cell]:
                        outer.cell_rank[cell] = rank

                # Degree counts how many way-segments touch each node.
                for i in range(len(coords) - 1):
                    a, b = coords[i], coords[i + 1]
                    outer.node_degree[a[0]] += 1
                    outer.node_degree[b[0]] += 1
                    cell = outer.node_cells.get(a[0])
                    if outer.keep is not None and cell not in outer.keep:
                        continue
                    outer.cell_links[cell] += 1
                    outer.cell_length[cell] += _haversine_m(
                        a[1], a[2], b[1], b[2])

        return Handler()


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def cells_egress(res: int = 9, keep_cells=None, pbf: Path = PBF,
                 progress=True) -> dict:
    """Road-graph statistics per H3 cell.

    Returns `{h3: {links, nodes, dead_ends, link_node_ratio, road_rank,
    road_m}}`. Cells absent from the result had no drivable road in OSM,
    which is a different thing from having poor egress — see
    `coverage_check`.
    """
    if not pbf.exists():
        raise FileNotFoundError(
            f"{pbf} missing. Download the Chile extract:\n  {SOURCE}")

    collector = _RoadCollector(res, keep_cells)
    handler = collector.make_handler()
    if progress:
        print(f"  leyendo {pbf.name} ({pbf.stat().st_size / 1e6:.0f} MB)…",
              flush=True)
    handler.apply_file(str(pbf), locations=True)

    nodes_per_cell: dict[str, int] = defaultdict(int)
    dead_per_cell: dict[str, int] = defaultdict(int)
    for ref, cell in collector.node_cells.items():
        if keep_cells is not None and cell not in collector.cell_links:
            continue
        nodes_per_cell[cell] += 1
        if collector.node_degree.get(ref, 0) <= 1:
            dead_per_cell[cell] += 1

    out = {}
    for cell, links in collector.cell_links.items():
        nodes = nodes_per_cell.get(cell, 0)
        out[cell] = {
            "links": int(links),
            "nodes": int(nodes),
            "dead_ends": int(dead_per_cell.get(cell, 0)),
            "link_node_ratio": round(links / nodes, 3) if nodes else 0.0,
            "road_rank": int(collector.cell_rank.get(cell, 0)),
            "road_m": round(collector.cell_length.get(cell, 0.0), 1),
        }
    if progress:
        print(f"  {len(out):,} celdas con red vial", flush=True)
    return out


def egress_deficit(stats: dict | None, dwellings: float = 0.0) -> float | None:
    """0-1. How hard it would be to leave. None when OSM says nothing.

    Three things compound: a network with few alternative routes, dead ends,
    and no road bigger than a lane. Returning None for unmapped cells is
    deliberate — an unmapped *toma* is the most dangerous case there is, and
    scoring it as good egress would be the worst possible failure mode.
    """
    if not stats:
        return None

    lnr = stats.get("link_node_ratio", 0.0)
    # 1.0 or below is cul-de-sac; 1.4 is a connected grid.
    connectivity = max(0.0, min(1.0, (1.4 - lnr) / 0.6))

    nodes = max(stats.get("nodes", 0), 1)
    dead = max(0.0, min(1.0, stats.get("dead_ends", 0) / nodes * 3.0))

    rank = stats.get("road_rank", 0)
    # Nothing above a residential lane is a real constraint on capacity.
    capacity = max(0.0, min(1.0, (4 - rank) / 4.0))

    return round(min(1.0, 0.45 * connectivity + 0.30 * dead
                     + 0.25 * capacity), 4)


def coverage_check(cells, egress_stats: dict, dwellings=None,
                   population=None) -> dict:
    """How much of the inhabited grid OSM actually covers.

    **Weight by people, not by cells.** Measured over Valparaíso, raw cell
    coverage is 44.2% — which sounds alarming and is nearly meaningless,
    because it counts a cell holding 1.3 dwellings the same as one holding
    156. Weighted by population the same data gives **95.7%**, and among
    cells with ten or more dwellings it is **95.2%**, holding at 86.1% even
    on slopes above 25°.

    So the fear that OSM would be thinnest exactly where the danger is
    turned out to be mostly unfounded, and it was worth measuring rather
    than assuming in either direction. What remains true is that the few
    steep, well-populated cells that *are* unmapped are precisely the ones
    that matter, which is why `egress_deficit` still returns None for them
    rather than a score.

    Pass `dwellings` and `population` as `{h3: count}` to get the weighted
    figures; without them only the cell count is reported, and that number
    should not be quoted on its own.
    """
    total = len(cells)
    mapped = [c for c in cells if c in egress_stats]
    out = {
        "cells": total,
        "cells_with_roads": len(mapped),
        "cell_coverage": round(len(mapped) / total, 4) if total else 0.0,
    }
    for name, weights in (("dwelling", dwellings), ("population", population)):
        if not weights:
            continue
        tot = sum(weights.get(c, 0) or 0 for c in cells)
        got = sum(weights.get(c, 0) or 0 for c in mapped)
        out[f"{name}_total"] = round(tot, 1)
        out[f"{name}_coverage"] = round(got / tot, 4) if tot else 0.0
    return out
