# Reference geometry

## `chile_boundary.geojson`

Chilean territory, 38 polygons including the mainland, Chiloé, Tierra del
Fuego, Juan Fernández, the Desventuradas and Rapa Nui.

**Provisional in provenance, but verified correct.** A third-party public
GeoJSON extract. It passes 33 assertions in `tests/test_chile.py`: every
regional capital, Chiloé, Tierra del Fuego, Puerto Williams, Rapa Nui, Juan
Fernández and both Desventuradas inside; Mendoza, Bariloche, Neuquén, Río
Gallegos, Salta, Tacna, La Paz and open ocean outside.

**The obvious official replacement is worse.** The INE ArcGIS Hub "Comunas de
Chile" layer draws the insular territories as **cartographic insets**: Isla
de Pascua sits at roughly (-73.9, -33.1) and Juan Fernández at (-73.9,
-33.4), beside the mainland, not where they are. Clipping against it would
drop every Rapa Nui detection and accept ocean off Valparaíso instead. It is
also missing 5 of 346 comunas including Antártica, and the OCUC "DPA 2026"
layer is line geometry with no comuna code.

So this file stays until a replacement is verified against those tests. The
real need for official INE cartography is **Phase 2** — manzana-level census
geography for WUI exposure, and comuna polygons carrying the `cut` code that
joins to SADU and Censo 2024. That is a different dataset, fetched when it is
needed, from the census cartography download rather than the display layer.

Used to stop a bounding box from putting Argentine and Bolivian fires on a
Chilean map — a naive box over Chile is roughly 90% foreign territory.
