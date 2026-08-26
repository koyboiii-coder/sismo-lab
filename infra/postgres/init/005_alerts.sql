-- Tracks which notification tier (daemon/alerts.py) has actually been sent
-- for an event, so a later revision doesn't resend at the same tier --
-- CLAUDE.md rule 3: "Nunca reenviar alerta por una revision salvo que la
-- magnitud suba y cruce un umbral que no habia cruzado antes."
--
-- events.alert_sent_at already exists (001_schema.sql) but was never
-- written to by any code until now -- a bare timestamp can't by itself
-- distinguish "already sent the silent tier" from "already sent the full
-- tier", which matters once there are two notifiable tiers instead of one.
-- alert_level_sent is that missing piece: NULL (never notified), 'silent',
-- or 'full' (see alerts.ALERT_SILENT / alerts.ALERT_FULL). db.Writer only
-- sends a new notification, and only then updates both columns, when the
-- newly computed tier outranks whatever is already stored here.

ALTER TABLE events ADD COLUMN alert_level_sent TEXT;
