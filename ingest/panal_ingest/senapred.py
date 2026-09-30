"""Capas públicas de SENAPRED, del Visor Chile Preparado.

El visor (`visorchilepreparado.cl`) es una app ArcGIS y sus 22 capas viven en
una organización pública. Dos le sirven a PANAL de inmediato.

**No es competencia.** Su capa de incendio es recurrencia histórica —dónde ha
ardido entre 2020 y 2024— y PANAL mide condición actual: con el combustible y
el terreno de esta temporada seca, dónde correría un incendio si llegara. La
correlación de rangos entre ambas es 0,145. Son preguntas distintas.

## Permiso

Las capas son públicas y consultarlas no requiere credenciales. **Publicar un
producto derivado sí debería pedirse**, y por eso todo lo que sale de acá se
marca: `build_wui.py --with-senapred` produce la versión enriquecida, y sin la
bandera produce la versión que PANAL puede publicar hoy sin preguntarle nada a
nadie.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://services5.arcgis.com/i7S5PSnIJAUcWvSE/arcgis/rest/services"

LAYERS = {
    # Densidad de Incendios Forestales 2020-2024 (Inc./Km²). gridcode 1..5,
    # recurrencia "Muy baja".."Muy alta".
    "recurrencia": f"{BASE}/Amenaza_por_Incendio_Forestal_2024/FeatureServer/0",
    # Cuarteles de bomberos.
    "bomberos": f"{BASE}/Servicios_2024/FeatureServer/1",
}

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "senapred"

RECURRENCIA = {1: "Muy baja", 2: "Baja", 3: "Media", 4: "Alta", 5: "Muy alta"}


def fetch(layer: str, bbox=None, out_fields="*", max_records=2000,
          refresh=False) -> dict:
    """Descarga una capa como GeoJSON, cacheada en disco."""
    if layer not in LAYERS:
        raise ValueError(f"capa desconocida {layer!r}; hay {sorted(LAYERS)}")

    CACHE.mkdir(parents=True, exist_ok=True)
    tag = "pais" if bbox is None else "_".join(f"{v:.2f}" for v in bbox)
    path = CACHE / f"{layer}_{tag}.geojson"
    if path.exists() and not refresh:
        return json.loads(path.read_text())

    params = {
        "where": "1=1", "outFields": out_fields, "outSR": "4326",
        "returnGeometry": "true", "f": "geojson",
        "resultRecordCount": str(max_records),
    }
    if bbox is not None:
        params.update({
            "geometry": ",".join(str(v) for v in bbox),
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        })

    url = f"{LAYERS[layer]}/query?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=180) as resp:
        data = json.load(resp)
    if "features" not in data:
        raise RuntimeError(f"respuesta inesperada: {str(data)[:180]}")

    path.write_text(json.dumps(data))
    return data


def cells_recurrencia(cells, bbox=None) -> dict:
    """Recurrencia histórica de incendios por celda, 0-5.

    Cero significa *fuera de todo polígono*, que aquí sí quiere decir "sin
    incendios registrados entre 2020 y 2024" — la capa cubre el país, no es
    un muestreo. Distinto de los casos donde ausencia de dato es
    desconocimiento.
    """
    import h3
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    if not cells:
        return {}
    if bbox is None:
        lats, lons = zip(*(h3.cell_to_latlng(c) for c in cells))
        bbox = (min(lons), min(lats), max(lons), max(lats))

    data = fetch("recurrencia", bbox)
    polys, codes = [], []
    for f in data.get("features", []):
        if f.get("geometry"):
            polys.append(shape(f["geometry"]))
            codes.append(int(f["properties"].get("gridcode") or 0))
    if not polys:
        return {}

    tree = STRtree(polys)
    out = {}
    for c in cells:
        lat, lon = h3.cell_to_latlng(c)
        p = Point(lon, lat)
        hits = [i for i in tree.query(p) if polys[i].contains(p)]
        out[c] = max((codes[i] for i in hits), default=0)
    return out


def cells_estacion_bomberos(cells, bbox=None) -> dict:
    """Distancia en metros al cuartel de bomberos más cercano.

    Es un término de *consecuencia*, no de amenaza: no cambia si el fuego
    llega, cambia cuánto demora en llegar ayuda. Una quebrada a 20 km del
    cuartel más cercano arde de otra manera que una a 2 km.
    """
    import h3
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    if not cells:
        return {}
    if bbox is None:
        lats, lons = zip(*(h3.cell_to_latlng(c) for c in cells))
        # Margen amplio: el cuartel más cercano puede estar fuera del área.
        bbox = (min(lons) - 0.6, min(lats) - 0.6,
                max(lons) + 0.6, max(lats) + 0.6)

    data = fetch("bomberos", bbox)
    pts = [shape(f["geometry"]) for f in data.get("features", [])
           if f.get("geometry")]
    if not pts:
        return {}

    tree = STRtree(pts)
    out = {}
    for c in cells:
        lat, lon = h3.cell_to_latlng(c)
        # shapely 2 devuelve un índice (numpy int), no la geometría.
        nearest = pts[int(tree.nearest(Point(lon, lat)))]
        out[c] = round(_haversine_m(lat, lon, nearest.y, nearest.x), 1)
    return out


def respuesta_factor(metros: float | None, saturar_km: float = 25.0) -> float | None:
    """Distancia al cuartel como término 0-1 de consecuencia.

    Raíz cuadrada: la diferencia entre 2 y 8 km pesa más que entre 18 y 24,
    porque los primeros minutos son los que deciden si un foco se ataca o se
    persigue. Satura a 25 km, donde el tiempo de viaje ya domina todo lo
    demás.
    """
    if metros is None:
        return None
    return round(min(1.0, (metros / 1000.0 / saturar_km) ** 0.5), 4)


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))
