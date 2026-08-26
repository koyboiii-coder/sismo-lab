-- Rupture-geometry uncertainty tracking for the local-intensity engine
-- (daemon/intensity.py) plus real finite-fault geometry from USGS
-- (daemon/connectors/usgs.py: fetch_rupture_geometry).
--
-- - event_reports.rupture_geometry: USGS ShakeMap rupture.json vertices,
--   as [[lat, lon, depth_km], ...]. Only ever populated by USGS, and only
--   for M >= 7 events that have a real (non-point) rupture model
--   published -- see usgs.fetch_rupture_geometry and its
--   _REAL_RUPTURE_GEOMETRY_TYPES check. Stored per-report like every
--   other parsed field, so reprocess.py/recompute.py can reuse it without
--   re-fetching from USGS.
-- - events.intensity_geometry_source: what estimated_mmi's Rrup was
--   actually based on for the canonical event -- 'finite_fault' (real
--   USGS rupture geometry) or 'wells_coppersmith' (magnitude-only
--   worst-case approximation, intensity.rupture_distance_km). NULL when
--   no intensity was computed at all (no location/magnitude yet).
-- - events.intensity_distance_saturated: TRUE when intensity_geometry_source
--   is 'wells_coppersmith' AND its depth floor was the binding constraint
--   -- i.e. the event's own approximated rupture length already reaches
--   (or exceeds) the hypocentral distance, so the worst-case bound can no
--   longer distinguish this event from one genuinely closer in. Always
--   FALSE for 'finite_fault' (real geometry has no such degeneracy) and
--   for NULL. The dashboard should render estimated_mmi as an uncertain
--   worst-case bound ("MMI VII estimado -- geometria de falla
--   desconocida") rather than a precise figure whenever this is TRUE, per
--   intensity.rupture_distance_km's docstring.

ALTER TABLE event_reports ADD COLUMN rupture_geometry JSONB;
ALTER TABLE events ADD COLUMN intensity_geometry_source TEXT;
ALTER TABLE events ADD COLUMN intensity_distance_saturated BOOLEAN NOT NULL DEFAULT FALSE;
