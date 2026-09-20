# api — FastAPI service

Serves scored H3 cells to the web and mobile clients.

```
GET /risk?h3=...            risk for specific cells
GET /risk/bbox?...&res=7    all cells in a viewport
GET /timeseries?h3=...      history for one cell
GET /forecast?h3=...        projection (Phase 5)
GET /meta                   data dates and freshness, always exposed
```

Every response carries the data date. Per ground rule 1, the client must never
be able to render PANAL without knowing how stale the data is.

## Status

Not implemented. Phase 3.
