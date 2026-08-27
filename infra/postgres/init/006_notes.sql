-- Pizarra de notas manuscritas (lápiz/dedo) -- CLAUDE.md, "Arquitectura":
-- dominio propio, sin relación con el pipeline sísmico. La regla de "un
-- solo escritor" (daemon) es para events/event_reports/source_health
-- específicamente (evita carreras con la deduplicación); esta tabla no
-- tiene ese riesgo y la API la escribe directo (api/routers/notes.py).
CREATE TABLE notes (
    id         BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Vector, no bitmap: arreglo de trazos, cada uno con sus puntos
    -- {x,y,p,t} normalizados 0-1 por eje -- ver
    -- web/src/components/notes/NoteCanvas.tsx. Escala a cualquier
    -- resolución y deja abierta una futura conversión trazo -> texto.
    strokes    JSONB NOT NULL
);

CREATE INDEX idx_notes_created_at ON notes (created_at DESC);
