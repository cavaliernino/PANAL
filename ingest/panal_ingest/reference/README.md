# Reference geometry

## `chile_boundary.geojson`

Chilean territory, 38 polygons including the mainland, Chiloé, Tierra del
Fuego, Juan Fernández, the Desventuradas and Rapa Nui.

**Provisional.** This is a third-party public GeoJSON extract, good enough to
clip satellite detections for the MVP. It must be replaced by the **official
INE census cartography**, which PANAL needs anyway for the Censo 2024
demographics, before anything is published as authoritative.

Used to stop a bounding box from putting Argentine and Bolivian fires on a
Chilean map — a naive box over Chile is roughly 90% foreign territory.
