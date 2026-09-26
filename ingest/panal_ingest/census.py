"""Censo 2024 — who and what is exposed, on the H3 grid.

Slope tells you where fire runs. This tells you whether anyone lives there.
A steep ravine with no houses is landscape, not wildland-urban interface.

Source: INE's Censo 2024 cartography, geoparquet, 221 variables at block
level. The direct download is not linked from the results page; it lives at

    https://storage.googleapis.com/bktdescargascenso2024/Cartografia/
    GEOPARQUET/Cartografia_censo2024_Pais.zip                    (758 MB)

**Two files, not one.** `Manzanas` carries 16.19M people — essentially all
the urban population — and `Entidades` carries another 2.04M, all rural.
Together 18.23M against the census total of 18.48M, the remaining 1.4%
being units too small to publish or not assigned to either. Reading only
the manzanas would silently drop two million rural people, which is
precisely the population living at the wildland interface.

CRS is EPSG:4674 (SIRGAS 2000). It differs from WGS84 by centimetres, which
is irrelevant against a 321 m cell, so geometry is used as-is.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "censo"
FILES = {
    "manzanas": "Cartografia_censo2024_Pais_Manzanas.parquet",
    "entidades": "Cartografia_censo2024_Pais_Entidades.parquet",
}

# Curated from the 221 available. Each earns its place in a fire map.
VARIABLES = {
    # Exposure: who and what is there.
    "n_per": "personas",
    "n_vp": "viviendas particulares",
    "n_hog": "hogares",
    # Vulnerability: who cannot leave quickly without help.
    "n_edad_0_5": "menores de 6",
    "n_edad_60_mas": "60 y más",
    "n_dificultad_mover": "dificultad para moverse",
    "n_hog_unipersonales": "hogares unipersonales",
    # Construction: what burns fastest. The February 2024 deaths in Viña
    # concentrated in informal hillside housing.
    "n_tipo_viv_mediagua": "mediaguas",
    "n_mat_paredes_precarios": "paredes precarias",
    "n_viv_irrecuperables": "viviendas irrecuperables",
    "n_viv_hacinadas": "viviendas hacinadas",
    # Ignition sources.
    "n_comb_cocina_lena": "cocina a leña",
    "n_basura_eriazo": "basura en sitio eriazo",
    # Firefighting capacity: no mains water means no hydrants.
    "n_fuente_agua_camion": "agua por camión aljibe",
    "n_fuente_agua_publica": "agua de red pública",
    # Evacuation capacity.
    "n_transporte_auto": "se moviliza en auto",
}

KEYS = ["CUT", "AREA_C"]

# Below this, a block is small enough that putting all of it in the cell
# containing its centre loses nothing worth chasing. Above it, the block is
# split across cells by area. Measured: the median urban block is 138 m
# across, but the 12.8% larger than a cell hold 32.9% of the population, so
# centroid-only assignment would misplace a third of the country.
SPLIT_ABOVE_M = 300.0

# When a block is only somewhat larger than a cell, its share of each cell is
# estimated by polyfilling two resolutions finer and counting children per
# parent. That is area weighting, cheaply.
FINE_OFFSET = 2

# Above this many cells, a polygon is emitted at a coarser resolution instead.
# Rural entidades reach 367 km across — 67,000 km², which is 640,000 cells at
# r9 — and the largest are essentially uninhabited (0.00 hab/km²). Spreading a
# handful of people uniformly across that is both ruinous to compute and a
# fiction about where they live. Only 86 entities (0.3%, holding 0.2% of the
# rural population) exceed this, and they are emitted coarse rather than
# dropped: an H3 index carries its own resolution, so a consumer can see that
# those rows are less precise instead of being quietly misled.
MAX_CELLS = 20_000

# A cell carrying less than this is noise, not interface. But the fix is not
# to drop it — it is to stop pretending the census knows more than it does.
#
# Rural entidades report a population for the whole entity, not its
# distribution, and people there cluster in hamlets rather than spreading
# evenly. Spreading 50 people across 130 cells gives 0.4 each, which is both
# false and useless; a first version dropped everything below this threshold
# and lost 18.5% of the rural population that way.
#
# So each block is emitted at the finest resolution that still leaves this
# many dwellings per cell, never finer than requested. Urban blocks land at
# the requested resolution; rural entities land coarser, and the H3 index
# says so. Resolution follows what the data supports, the same rule the
# detection layers follow.
MIN_DWELLINGS = 1.0


def _bbox_arrays(table):
    """Works on both a Table and a RecordBatch.

    `iter_batches` yields RecordBatches, whose columns are plain Arrays with
    no `combine_chunks`. Reading a whole Table gives ChunkedArrays, which
    need it. Handling only one of the two cost three silent-looking runs.
    """
    bb = table["SHAPE_bbox"]
    if hasattr(bb, "combine_chunks"):
        bb = bb.combine_chunks()
    return (np.asarray(bb.field("xmin")), np.asarray(bb.field("ymin")),
            np.asarray(bb.field("xmax")), np.asarray(bb.field("ymax")))


def _diagonal_m(xmin, ymin, xmax, ymax):
    lat = (ymin + ymax) / 2.0
    dx = (xmax - xmin) * 111_320.0 * np.cos(np.radians(lat))
    dy = (ymax - ymin) * 110_540.0
    return np.hypot(dx, dy)


def _polyfill(geom, res: int):
    """Every H3 cell of `res` whose centre falls inside the geometry."""
    import h3

    cells = []
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        ring = [(y, x) for x, y in poly.exterior.coords]
        holes = [[(y, x) for x, y in i.coords] for i in poly.interiors]
        try:
            cells.extend(h3.polygon_to_cells(h3.LatLngPoly(ring, *holes), res))
        except Exception:                               # noqa: BLE001
            continue
    return cells


def res_for_block(area_km2: float, dwellings: float, res: int) -> int:
    """The finest resolution at which this block still has real density.

    Never finer than `res`. A dense city block stays at `res`; a sparse rural
    entity steps out until each cell would hold at least `MIN_DWELLINGS`.
    """
    import h3

    if dwellings <= 0 or area_km2 <= 0:
        return res
    target = res
    while target > 0:
        cells = max(1.0, area_km2 / h3.average_hexagon_area(target, unit="km^2"))
        if dwellings / cells >= MIN_DWELLINGS:
            return target
        target -= 1
    return 0


def _split_weights(wkb: bytes, res: int, area_km2: float | None = None):
    """How a block's population divides across the cells it covers.

    Returns `{h3: fraction}`, where the keys may be coarser than `res` for
    polygons too large to enumerate — an H3 index carries its resolution, so
    a coarse key is self-describing rather than a silent approximation.

    Three regimes, chosen by how the polygon compares to a cell:

    * comparable to a cell — polyfill two resolutions finer and count
      children per parent, which weights by area without intersecting
      anything;
    * much larger — polyfill at `res` directly with equal weights, since
      fully-contained cells have equal area and the fine pass would only
      cost time;
    * vast — step out to whatever resolution keeps the count under
      `MAX_CELLS`.
    """
    import h3
    from shapely import wkb as shapely_wkb

    geom = shapely_wkb.loads(wkb)
    cell_km2 = h3.average_hexagon_area(res, unit="km^2")
    if area_km2 is None:
        area_km2 = 0.0

    if area_km2 > cell_km2 * 4:
        # Large: choose the finest resolution that stays within the cap.
        target = res
        while target > 0 and area_km2 / h3.average_hexagon_area(
                target, unit="km^2") > MAX_CELLS:
            target -= 1
        cells = _polyfill(geom, target)
        if cells:
            w = 1.0 / len(cells)
            return {c: w for c in cells}
    else:
        # Comparable: weight by area via a finer pass.
        counts: dict[str, int] = {}
        for f in _polyfill(geom, min(15, res + FINE_OFFSET)):
            parent = h3.cell_to_parent(f, res)
            counts[parent] = counts.get(parent, 0) + 1
        if counts:
            total = sum(counts.values())
            return {k: v / total for k, v in counts.items()}

    # Too thin to contain any cell centre — a narrow rural strip, typically.
    c = geom.centroid
    return {h3.latlng_to_cell(c.y, c.x, res): 1.0}


def to_h3(res: int = 9, sources=("manzanas", "entidades"), progress=True,
          batch_size: int = 20_000):
    """Aggregate census variables onto H3 cells.

    Returns one row per cell with the curated variables, plus `cut` (the
    comuna contributing the most people, since a cell can straddle a
    boundary) and `res`, which is **per block, not global**: the finest
    resolution at which that block still has real density. Urban blocks land
    at the requested resolution; sparse rural entities land coarser, and the
    H3 index says so.

    Memory is the constraint, and it bit twice. Materialising all 216,341 WKB
    geometries as Python objects was killed by the OS without a message, and
    so was reading the whole 194 MB geometry column into Arrow before
    filtering. Both files are now streamed in row batches, so peak memory
    depends on `batch_size` rather than on the size of the country.
    """
    import h3
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq

    cols = KEYS + list(VARIABLES) + ["SHAPE_bbox", "SHAPE"]
    frames = []

    for source in sources:
        path = CACHE / FILES[source]
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing. Download and unzip the Censo 2024 "
                "cartography — see the module docstring."
            )

        pf = pq.ParquetFile(path)
        total = pf.metadata.num_rows
        seen = 0
        if progress:
            print(f"  {source}: {total:,} bloques", flush=True)

        for batch in pf.iter_batches(batch_size=batch_size, columns=cols):
            table = batch
            xmin, ymin, xmax, ymax = _bbox_arrays(table)
            diag = _diagonal_m(xmin, ymin, xmax, ymax)
            cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
            lat_mid = (ymin + ymax) / 2.0
            area_km2 = ((xmax - xmin) * 111.320 * np.cos(np.radians(lat_mid))
                        * (ymax - ymin) * 110.540 * 0.5)

            values = np.column_stack([
                np.nan_to_num(np.asarray(table[v], dtype="float64"))
                for v in VARIABLES
            ])
            cut = np.asarray(table["CUT"], dtype="int64")
            dwellings = np.nan_to_num(np.asarray(table["n_vp"], dtype="float64"))
            n = len(diag)

            block_res = np.array([
                res_for_block(float(area_km2[i]), float(dwellings[i]), res)
                for i in range(n)
            ], dtype="int8")

            small = diag <= SPLIT_ABOVE_M
            rows = list(np.flatnonzero(small))
            cells = [h3.latlng_to_cell(float(cy[i]), float(cx[i]),
                                       int(block_res[i])) for i in rows]
            weights = [1.0] * len(rows)

            big_idx = np.flatnonzero(~small)
            if len(big_idx):
                shapes = table["SHAPE"].to_pylist()
                for i in big_idx:
                    r_i = int(block_res[i])
                    try:
                        parts = _split_weights(shapes[int(i)], r_i,
                                               float(area_km2[i]))
                    except Exception:                   # noqa: BLE001
                        parts = {h3.latlng_to_cell(float(cy[i]), float(cx[i]),
                                                   r_i): 1.0}
                    for cell, w in parts.items():
                        cells.append(cell)
                        rows.append(int(i))
                        weights.append(w)
                del shapes

            idx = np.asarray(rows, dtype="int64")
            wt = np.asarray(weights)
            part = pd.DataFrame(values[idx] * wt[:, None],
                                columns=list(VARIABLES))
            part["h3"] = cells
            part["cut"] = cut[idx]
            # Collapse within the batch so the concat stays small.
            frames.append(part.groupby(["h3", "cut"], as_index=False).sum())

            seen += n
            if progress:
                print(f"    {seen:,}/{total:,}", flush=True)

    allrows = pd.concat(frames, ignore_index=True)
    del frames

    agg = allrows.groupby("h3", as_index=False)[list(VARIABLES)].sum()
    owner = (allrows.groupby(["h3", "cut"], as_index=False)["n_per"].sum()
             .sort_values("n_per", ascending=False)
             .drop_duplicates("h3")[["h3", "cut"]])
    df = agg.merge(owner, on="h3", how="left")
    df["res"] = [h3.get_resolution(c) for c in df["h3"]]
    for v in VARIABLES:
        df[v] = df[v].round(2)

    if progress:
        for r, v in df.groupby("res")["n_per"].sum().items():
            print(f"  r{r}: {(df.res == r).sum():>8,} celdas, "
                  f"{v:>11,.0f} personas", flush=True)

    out_cols = ["h3", "res", "cut"] + list(VARIABLES)
    return df[out_cols].sort_values("n_per", ascending=False).reset_index(drop=True)


def exposure_terms(df):
    """Derive the 0-1 terms the WUI score consumes.

    Every term is a *share*, not a count, so a dense city block and a small
    hamlet are judged on their condition rather than their size. Counts stay
    in the frame for the totals that matter operationally — how many people
    are behind this cell.
    """
    out = df.copy()
    per = out["n_per"].replace(0, np.nan)
    viv = out["n_vp"].replace(0, np.nan)

    # Who needs help to leave.
    out["frac_vulnerable"] = (
        (out["n_edad_0_5"] + out["n_edad_60_mas"] + out["n_dificultad_mover"])
        / per
    ).clip(0, 1).fillna(0)

    # What burns fastest.
    out["frac_precario"] = (
        (out["n_tipo_viv_mediagua"] + out["n_mat_paredes_precarios"]
         + out["n_viv_irrecuperables"]) / viv
    ).clip(0, 1).fillna(0)

    # Ignition pressure from how people cook and dispose of waste.
    out["frac_ignicion"] = (
        (out["n_comb_cocina_lena"] + out["n_basura_eriazo"]) / viv
    ).clip(0, 1).fillna(0)

    # No mains water means no hydrants. This is the term a firefighter reads
    # first, and it is invisible on any map built from imagery alone.
    out["frac_sin_red_agua"] = (
        1 - (out["n_fuente_agua_publica"] / viv)
    ).clip(0, 1).fillna(0)

    return out
