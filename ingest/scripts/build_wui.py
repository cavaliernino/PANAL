#!/usr/bin/env python3
"""Cross the census grid with terrain and score wildland-urban exposure.

    python scripts/build_wui.py --region valparaiso -o ../data/processed/wui_valparaiso.parquet
    python scripts/build_wui.py --all -o ../data/processed/wui_chile.parquet

Terrain is fetched per 1°x1° DEM tile and cached, so the first run over a
region is slow and later ones are not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ingest"))
sys.path.insert(0, str(ROOT / "engine"))

import pandas as pd  # noqa: E402
from h3 import cell_to_latlng as h3_latlng  # noqa: E402

from panal_engine import wui  # noqa: E402
from panal_ingest import census, egress, fuel, senapred, terrain  # noqa: E402

REGIONS = {
    # cut prefixes: 5 = Valparaíso, 13 = Metropolitana, 8 = Biobío
    "valparaiso": (5,),
    "metropolitana": (13,),
    "biobio": (8, 16),
    "centro_sur": (5, 13, 6, 7, 16, 8),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--census", default=str(ROOT / "data/processed/censo_h3_r9.parquet"))
    p.add_argument("--region", choices=sorted(REGIONS))
    p.add_argument("--all", action="store_true")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--fuel-year", type=int, default=2026,
                   help="dry season to read fuel from (default 2026)")
    p.add_argument("--fuel-window", nargs=2, metavar=("MM-DD", "MM-DD"),
                   default=list(fuel.DEFAULT_WINDOW),
                   help="días de esa temporada (default feb–mar). Para "
                        "validar contra un incendio, una ventana que termine "
                        "antes del incendio: ver validate_wui.py")
    p.add_argument("--no-fuel", action="store_true")
    p.add_argument("--no-egress", action="store_true")
    p.add_argument("--with-senapred", action="store_true",
                   help="añade recurrencia de ignición y distancia a cuartel "
                        "desde las capas públicas de SENAPRED. Produce la "
                        "versión enriquecida, que no debe publicarse sin "
                        "permiso explícito")
    a = p.parse_args()

    df = pd.read_parquet(a.census)
    print(f"censo: {len(df):,} celdas", file=sys.stderr)

    if a.region:
        # CUT is region*1000 + comuna for both 4- and 5-digit codes, so
        # integer division recovers the region either way: 5101 -> 5,
        # 13101 -> 13.
        prefixes = set(REGIONS[a.region])
        df = df[(df["cut"].fillna(0).astype("int64") // 1000).isin(prefixes)]
        print(f"  {a.region}: {len(df):,} celdas", file=sys.stderr)
    elif not a.all:
        p.error("elige --region o --all")

    cells = df["h3"].tolist()
    # Count the tiles that actually contain cells, not every tile in the
    # bounding box: Valparaíso reaches Rapa Nui at -109°, so its box spans
    # 39° of empty ocean and tiles_for would report 280 for about nine.
    import math
    import h3 as _h3
    need = {terrain.tile_name(math.floor(la), math.floor(lo))
            for la, lo in (_h3.cell_to_latlng(c) for c in cells)}
    print(f"terreno para {len(cells):,} celdas ({len(need)} tiles DEM)…",
          file=sys.stderr)
    t = terrain.cells_terrain(cells)
    print(f"  con elevación: {len(t):,}", file=sys.stderr)

    df = df.copy()
    df["slope_deg"] = [t.get(c, {}).get("slope_deg") for c in cells]
    df["elev_m"] = [t.get(c, {}).get("elev_m") for c in cells]
    df["relief_m"] = [t.get(c, {}).get("relief_m") for c in cells]
    df["slope_factor"] = [terrain.slope_factor(s) for s in df["slope_deg"]]

    if a.no_fuel:
        df["fuel_factor"] = None
        print("combustible: omitido", file=sys.stderr)
    else:
        print(f"combustible Sentinel-2 ({a.fuel_year}, "
              f"{a.fuel_window[0]}..{a.fuel_window[1]})…", file=sys.stderr)
        f = fuel.cells_fuel(cells, year=a.fuel_year,
                            window=tuple(a.fuel_window))
        df["ndvi"] = [f.get(c, {}).get("ndvi") for c in cells]
        df["ndmi"] = [f.get(c, {}).get("ndmi") for c in cells]
        df["fuel_factor"] = [f.get(c, {}).get("fuel_factor") for c in cells]
        # Which scene each value came from, so a validation can check that
        # the fuel it ranks by predates the fire it is tested against.
        df["fuel_scene"] = [f.get(c, {}).get("scene") for c in cells]
        got = df["fuel_factor"].notna().sum()
        print(f"  con combustible: {got:,} de {len(df):,} "
              f"({100 * got / len(df):.1f}%)", file=sys.stderr)

    if a.no_egress:
        df["egress_deficit"] = None
        print("egreso: omitido", file=sys.stderr)
    else:
        print("egreso OpenStreetMap…", file=sys.stderr)
        stats = egress.cells_egress(res=9, keep_cells=set(cells))
        df["link_node_ratio"] = [stats.get(c, {}).get("link_node_ratio") for c in cells]
        df["dead_ends"] = [stats.get(c, {}).get("dead_ends") for c in cells]
        df["road_rank"] = [stats.get(c, {}).get("road_rank") for c in cells]
        df["egress_deficit"] = [egress.egress_deficit(stats.get(c)) for c in cells]
        cov = egress.coverage_check(
            cells, stats,
            dwellings=dict(zip(df["h3"], df["n_vp"])),
            population=dict(zip(df["h3"], df["n_per"])))
        print(f"  cobertura: {100*cov['cell_coverage']:.1f}% de celdas, "
              f"{100*cov.get('population_coverage',0):.1f}% de población",
              file=sys.stderr)

    if a.with_senapred:
        print("capas SENAPRED (recurrencia de ignición, cuarteles)…",
              file=sys.stderr)
        lats = [h3_latlng(c)[0] for c in cells]
        lons = [h3_latlng(c)[1] for c in cells]
        bbox = (min(lons), min(lats), max(lons), max(lats))
        ign = senapred.cells_recurrencia(cells, bbox)
        est = senapred.cells_estacion_bomberos(cells, bbox)
        df["ignition"] = [ign.get(c, 0) for c in cells]
        df["cuartel_m"] = [est.get(c) for c in cells]
        df["response_factor"] = [senapred.respuesta_factor(est.get(c))
                                 for c in cells]
        print(f"  ignición >0 en {int((df['ignition'] > 0).sum()):,} celdas · "
              f"cuartel mediano {df['cuartel_m'].median() / 1000:.1f} km",
              file=sys.stderr)
    else:
        df["ignition"] = None
        df["response_factor"] = None

    df = census.exposure_terms(df)
    scored = wui.score_frame(df,
                             fuel_col=None if a.no_fuel else "fuel_factor",
                             egress_col=None if a.no_egress else "egress_deficit",
                             response_col="response_factor" if a.with_senapred else None,
                             ignition_col="ignition" if a.with_senapred else None)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    scored.to_parquet(tmp)
    tmp.replace(out)

    print(f"\n{out}  ({out.stat().st_size / 1024 / 1024:.1f} MB)", file=sys.stderr)
    print(f"  {len(scored):,} celdas puntuadas", file=sys.stderr)
    both = wui.priority(scored)
    if len(both):
        print(f"\namenaza y consecuencia ambas en el decil superior: "
              f"{len(both):,} celdas", file=sys.stderr)
        print(f"  {both['n_vp'].sum():,.0f} viviendas · "
              f"{both['n_per'].sum():,.0f} personas · "
              f"egreso conocido en {int(both['has_egress'].sum())}/{len(both)}",
              file=sys.stderr)

        print(f"\n{'amen':>6}{'cons':>6}{'viv':>6}{'pers':>7}{'pend':>6}"
              f"{'fuel':>6}{'egr':>6}  comuna", file=sys.stderr)
        for r in both.nlargest(12, "n_per").itertuples():
            eg = "n/d" if not r.has_egress else f"{r.egress_deficit:.2f}"
            print(f"{r.wui:>6.2f}{r.consequence:>6.2f}{r.n_vp:>6.0f}"
                  f"{r.n_per:>7.0f}{(r.slope_deg or 0):>6.1f}"
                  f"{(getattr(r, 'fuel_factor', 0) or 0):>6.2f}{eg:>6}"
                  f"  {r.cut}", file=sys.stderr)


if __name__ == "__main__":
    main()
