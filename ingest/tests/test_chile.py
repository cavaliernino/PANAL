"""Territory clipping is correctness-critical: a bounding box over Chile is
roughly 90% Argentina and Bolivia, so every detection is tested against real
geometry before it reaches a map. These tests pin that geometry down.
"""

import numpy as np
import pytest

from panal_ingest import chile

# Cities, one per region-ish, plus every insular territory. Coordinates are
# town centres, except the Desventuradas, which are too small for a nominal
# coordinate to land inside — those use the polygon centroids.
INSIDE = [
    ("Arica", -70.30, -18.48),
    ("Iquique", -70.14, -20.21),
    ("Calama", -68.93, -22.46),
    ("Antofagasta", -70.40, -23.65),
    ("Copiapó", -70.33, -27.37),
    ("La Serena", -71.25, -29.90),
    ("Valparaíso", -71.62, -33.05),
    ("Santiago", -70.65, -33.45),
    ("Rancagua", -70.74, -34.17),
    ("Talca", -71.67, -35.43),
    ("Chillán", -72.10, -36.61),
    ("Concepción", -73.05, -36.83),
    ("Temuco", -72.60, -38.74),
    ("Valdivia", -73.25, -39.81),
    ("Puerto Montt", -72.94, -41.47),
    ("Castro (Chiloé)", -73.76, -42.48),
    ("Coyhaique", -72.07, -45.57),
    ("Punta Arenas", -70.92, -53.16),
    ("Puerto Williams", -67.62, -54.93),
    ("Rapa Nui", -109.35, -27.12),
    ("Juan Fernández", -78.83, -33.64),
    ("San Ambrosio", -79.8863, -26.3429),
    ("San Félix", -80.0983, -26.2978),
]

# The near misses that matter. Mendoza and Bariloche are precisely the false
# positives that made a naive bounding box 90% wrong.
OUTSIDE = [
    ("Mendoza AR", -68.85, -32.89),
    ("Bariloche AR", -71.31, -41.13),
    ("Neuquén AR", -68.06, -38.95),
    ("Río Gallegos AR", -69.22, -51.62),
    ("Salta AR", -65.41, -24.79),
    ("Tacna PE", -70.25, -18.01),
    ("La Paz BO", -68.15, -16.50),
    ("Pacífico abierto", -74.00, -33.00),
    ("Atlántico sur", -65.00, -54.00),
    ("Al norte de Arica", -70.30, -17.20),
]


@pytest.mark.parametrize("name,lon,lat", INSIDE, ids=[c[0] for c in INSIDE])
def test_inside_chile(name, lon, lat):
    assert chile.in_chile(np.array([lon]), np.array([lat]))[0], name


@pytest.mark.parametrize("name,lon,lat", OUTSIDE, ids=[c[0] for c in OUTSIDE])
def test_outside_chile(name, lon, lat):
    assert not chile.in_chile(np.array([lon]), np.array([lat]))[0], name


def test_insular_territories_are_where_they_actually_are():
    """Guards against a class of boundary file that silently breaks clipping.

    The INE ArcGIS Hub "Comunas de Chile" layer places Isla de Pascua at
    roughly (-73.9, -33.1) and Juan Fernández at (-73.9, -33.4) — inset boxes
    drawn beside the mainland for map layout, not geodetic positions. Clipping
    against a file like that would drop every Rapa Nui detection and accept
    ocean off Valparaíso instead. Any replacement boundary has to pass this.
    """
    rapa = [r for r in chile._rings() if r[:, 0].mean() < -100]
    assert rapa, "Rapa Nui missing or placed at mainland longitudes"
    assert -110 < rapa[0][:, 0].mean() < -109
    assert -28 < rapa[0][:, 1].mean() < -27

    jf = [r for r in chile._rings() if -81 < r[:, 0].mean() < -78
          and -34 < r[:, 1].mean() < -33]
    assert jf, "Juan Fernández missing or misplaced"


def test_empty_input_is_handled():
    assert chile.in_chile(np.array([]), np.array([])).shape == (0,)


def test_clip_preserves_columns():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({
        "lat": [-33.45, -32.89, -27.12],
        "lon": [-70.65, -68.85, -109.35],
        "frp_mw": [1.0, 2.0, 3.0],
    })
    out = chile.clip(df)
    assert list(out.columns) == list(df.columns)
    assert len(out) == 2                     # Santiago and Rapa Nui, not Mendoza
    assert set(out["frp_mw"]) == {1.0, 3.0}
