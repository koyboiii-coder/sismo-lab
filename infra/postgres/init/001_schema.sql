-- Initial schema. Simple SQL, no migration framework (no Alembic).
-- Runs automatically on first container start via
-- /docker-entrypoint-initdb.d (only on an empty data volume). Any
-- future schema change should be added as a new numbered file here.

CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    -- our own canonical identity for the event, not any agency's id
    cluster_key     UUID NOT NULL UNIQUE,

    origin_time     TIMESTAMPTZ NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    depth_km        DOUBLE PRECISION,
    magnitude       DOUBLE PRECISION,
    magnitude_type  TEXT,
    region          TEXT,

    -- computed by us
    distance_km     DOUBLE PRECISION,   -- hypocentral, from HOME_LAT/HOME_LON
    estimated_pga   DOUBLE PRECISION,   -- in g
    estimated_mmi   DOUBLE PRECISION,   -- modified Mercalli intensity

    preferred_source TEXT NOT NULL,     -- 'CSN' | 'USGS' | 'EMSC'
    is_significant  BOOLEAN NOT NULL DEFAULT FALSE,
    alert_sent_at   TIMESTAMPTZ,

    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revision        INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_events_origin_time ON events (origin_time DESC);
CREATE INDEX idx_events_significant ON events (is_significant, origin_time DESC);

-- every raw report from every source, unmodified
CREATE TABLE event_reports (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,      -- 'CSN' | 'USGS' | 'EMSC'
    source_event_id TEXT NOT NULL,
    payload         JSONB NOT NULL,     -- original raw response, verbatim
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_event_id, received_at)
);

CREATE TABLE source_health (
    source          TEXT PRIMARY KEY,
    last_success_at TIMESTAMPTZ,
    last_error_at   TIMESTAMPTZ,
    last_error      TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);
