-- Support for the local-intensity engine (daemon/intensity.py) and for
-- CSN geocoding (daemon/geocoding.py).
--
-- distance_km/estimated_pga/estimated_mmi/is_significant already exist on
-- `events` since 001_schema.sql; this migration only adds:
--
-- - event_reports.source_mmi: a source's own MMI estimate, verbatim, when
--   it provides one (currently only USGS, via GeoJSON properties.mmi --
--   its ShakeMap-derived intensity). Stored per-report like every other
--   parsed field.
-- - events.usgs_reported_mmi: the latest USGS-reported MMI attached to
--   this cluster, if any -- kept alongside our own estimated_mmi to
--   sanity-check the GMPE's calibration. NOT directly comparable to
--   estimated_mmi as-is: USGS's mmi is its ShakeMap's near-epicenter/max
--   intensity, while estimated_mmi is intensity at HOME_LAT/HOME_LON --
--   a meaningful comparison needs our own GMPE evaluated at a matching
--   distance, not just these two columns side by side. Not part of the
--   canonical-field priority system in dedup.py either: USGS is the only
--   source that ever has it, so there's nothing to prioritize between
--   sources on this field.

ALTER TABLE event_reports ADD COLUMN source_mmi DOUBLE PRECISION;
ALTER TABLE events ADD COLUMN usgs_reported_mmi DOUBLE PRECISION;
