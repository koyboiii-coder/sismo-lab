# CLAUDE.md — sismos-dashboard

Sistema de monitoreo sísmico en tiempo real. Corre 24/7 en una Raspberry Pi 5
(ARM64, Raspberry Pi OS Lite) y se visualiza en una tablet Android montada en
pared, en modo kiosco.

Ingesta eventos de tres fuentes públicas, los deduplica, estima la intensidad
percibida en la ubicación del usuario y los emite a un dashboard vía SSE.

---

## Reglas del proyecto

Estas son invariantes. No las cambies sin que se pidan explícitamente.

1. **Todo timestamp se almacena en UTC**, con tipo `TIMESTAMPTZ`. La conversión
   a `America/Santiago` ocurre solo en la capa de presentación.
2. **Un sismo es una entidad mutable.** Las agencias revisan magnitud, ubicación
   y profundidad durante los minutos siguientes. Nunca trates un evento como
   registro inmutable.
3. **Nunca alertes por magnitud sola.** El criterio es la intensidad estimada en
   la ubicación del usuario. Ver sección "Motor de reglas".
4. **Degradación con gracia.** Si una fuente cae, el sistema sigue operando con
   las otras dos y lo refleja en el estado de salud. Nunca crashea el daemon.
5. **La Pi tiene recursos limitados.** Sin dependencias pesadas innecesarias.
   Las imágenes Docker deben ser `linux/arm64`. Construir con buildx en otra
   máquina, no en la Pi.
6. Todo el código y los comentarios en inglés. La UI en español de Chile.

---

## Arquitectura

```
daemon/     Python 3.11 + asyncio. Ingesta, deduplicación, reglas, notificación.
api/        FastAPI. REST para históricos + SSE para el stream en vivo.
web/        Next.js. Dashboard. Diseño ya definido (ver docs/design/).
infra/      docker-compose, Caddy, systemd, healthchecks.
```

Base de datos: PostgreSQL 16. El daemon escribe, la API solo lee.
Comunicación daemon → API: `LISTEN/NOTIFY` de Postgres sobre el canal
`seismic_events`. Sin broker adicional.

---

## Fuentes de datos

### 1. EMSC / SeismicPortal — WebSocket (prioritaria por latencia)

```
wss://www.seismicportal.eu/standing_order/websocket
```

Push, sin polling. Mantener conexión persistente con reconexión exponencial
(1s → 60s máx) y keepalive. Es la fuente más rápida.

Payload:

```json
{
  "action": "insert",
  "data": {
    "type": "Feature",
    "id": "20201230_0000082",
    "geometry": { "type": "Point", "coordinates": [lon, lat, depth_negativo] },
    "properties": {
      "unid": "20201230_0000082",
      "time": "2020-12-30T08:45:29.9Z",
      "lastupdate": "2020-12-30T08:47:00.0Z",
      "lat": 36.6, "lon": -121.2, "depth": 4.0,
      "mag": 2.4, "magtype": "md",
      "evtype": "ke",
      "auth": "NC",
      "source_catalog": "EMSC-RTS",
      "flynn_region": "CENTRAL CALIFORNIA"
    }
  }
}
```

Notas:
- `action` puede ser `insert` o `update`. Ambos deben procesarse.
- En `geometry.coordinates` la profundidad viene negativa; en `properties.depth`
  viene positiva en km. Usar `properties`.
- `evtype: "ke"` = earthquake conocido. Filtrar otros tipos (explosiones, etc.).

### 2. USGS — FDSN Event Web Service

```
https://earthquake.usgs.gov/fdsnws/event/1/query
  ?format=geojson
  &starttime=<ahora-30min ISO8601>
  &minmagnitude=4.0
```

Polling cada 60 s con ventana móvil de 30 min. Formato GeoJSON estándar FDSN.
Identificador en `features[].id`. Magnitud en `properties.mag`, profundidad en
`geometry.coordinates[2]` (km, positiva).

Para eventos chilenos usar además un query acotado por bounding box:
`minlatitude=-56 &maxlatitude=-17 &minlongitude=-76 &maxlongitude=-66`
con `minmagnitude=2.5`.

### 3. CSN Chile — vía api.gael.cloud (no oficial)

```
https://api.gael.cloud/general/public/sismos
```

Scraping de terceros sobre sismologia.cl. Se actualiza cada ~5 min.
Es la fuente con mejor cobertura de magnitudes chicas en Chile, pero es el
punto de falla más frágil del sistema.

```json
[
  {
    "Fecha": "2022-07-18 18:35:54",
    "Profundidad": "121",
    "Magnitud": "2.6",
    "RefGeografica": "43 km al O de Ollagüe",
    "FechaUpdate": "2022-07-18T23:10:00.830Z"
  }
]
```

Cuidado:
- Todos los campos vienen como **string**. Parsear explícitamente.
- **No entrega latitud ni longitud.** Hay que geocodificar desde
  `RefGeografica` o correlacionar con USGS/EMSC por tiempo y magnitud.
  Si no se logra ubicar, el evento se guarda sin coordenadas y no participa
  del cálculo de intensidad.
- `Fecha` viene en hora local de Chile, sin indicador de zona. Convertir a UTC
  asumiendo `America/Santiago` (ojo con el cambio de horario).
- Sin API oficial documentada del CSN. Si esta fuente cae, considerar scraping
  directo de sismologia.cl como fallback.

---

## Esquema de base de datos

```sql
CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    -- identidad canónica del evento (nuestra, no de las agencias)
    cluster_key     UUID NOT NULL UNIQUE,

    origin_time     TIMESTAMPTZ NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    depth_km        DOUBLE PRECISION,
    magnitude       DOUBLE PRECISION,
    magnitude_type  TEXT,
    region          TEXT,

    -- calculados por nosotros
    distance_km     DOUBLE PRECISION,   -- hipocentral, desde HOME_LAT/HOME_LON
    estimated_pga   DOUBLE PRECISION,   -- en g
    estimated_mmi   DOUBLE PRECISION,   -- Mercalli modificada

    preferred_source TEXT NOT NULL,     -- 'CSN' | 'USGS' | 'EMSC'
    is_significant  BOOLEAN NOT NULL DEFAULT FALSE,
    alert_sent_at   TIMESTAMPTZ,

    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revision        INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_events_origin_time ON events (origin_time DESC);
CREATE INDEX idx_events_significant ON events (is_significant, origin_time DESC);

-- cada reporte crudo de cada fuente, sin modificar
CREATE TABLE event_reports (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,      -- 'CSN' | 'USGS' | 'EMSC'
    source_event_id TEXT NOT NULL,
    payload         JSONB NOT NULL,     -- respuesta original íntegra
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
```

Guardar siempre el payload crudo en `event_reports`. Cuando el deduplicador se
equivoque —y se va a equivocar— es la única forma de reconstruir qué pasó.

---

## Deduplicación

El mismo sismo llega de las tres fuentes con IDs distintos y parámetros que
difieren. Reglas de clustering:

- **Ventana temporal:** ±90 s en `origin_time`
- **Ventana espacial:** < 100 km de separación epicentral
- **Sin coordenadas** (caso CSN): ±90 s y diferencia de magnitud < 0.7

Si un reporte entrante cae dentro de un cluster existente → se agrega a
`event_reports` y se recalculan los campos canónicos de `events`.
Si no → se crea un cluster nuevo.

**Prioridad de fuente para los valores canónicos:**
- Eventos dentro del bounding box de Chile: `CSN > USGS > EMSC`
- Resto del mundo: `USGS > EMSC`

Al actualizar un evento existente: incrementar `revision`, actualizar
`updated_at`, y emitir `NOTIFY` para que la UI refresque en vivo.

---

## Motor de reglas

Configuración en `.env`:

```
HOME_LAT=-36.8270      # ajustar a la ubicación exacta
HOME_LON=-73.0498
```

Pipeline de cálculo:

1. **Distancia hipocentral** — haversine para la distancia epicentral, luego
   `sqrt(epicentral² + depth²)`.
2. **PGA estimado** — GMPE para zona de subducción. Usar Youngs et al. (1997)
   o Abrahamson-Gregor-Addo (2016) como implementación inicial. Distinguir
   eventos interplaca de intraplaca por profundidad si es posible.
3. **PGA → Mercalli** — relación de Wald et al. (1999).

Umbrales:

| MMI estimada | Acción |
|---|---|
| < III | Solo se guarda, aparece en el listado |
| III – IV | Notificación silenciosa, se destaca en el dashboard |
| ≥ V | Alerta completa: dashboard en modo alerta, push, TTS en la tablet |
| M ≥ 6.5 mundial | Aparece en el panel de eventos globales, sin alerta local |

`is_significant = TRUE` cuando MMI ≥ III o cuando M ≥ 6.5 en cualquier parte.

**Nunca reenviar alerta por una revisión** salvo que la magnitud suba y cruce
un umbral que no había cruzado antes. Usar `alert_sent_at` para controlarlo.

---

## API

```
GET  /api/events?since=<iso8601>&limit=50     Listado, orden descendente
GET  /api/events/{cluster_key}                Detalle + todos sus reportes
GET  /api/health                              Estado de las tres fuentes
GET  /api/stream                              SSE — eventos nuevos y revisiones
```

Formato de los mensajes SSE:

```
event: seismic
data: {"type":"insert"|"update","event":{...}}

event: health
data: {"CSN":"ok","USGS":"ok","EMSC":"degraded"}
```

Heartbeat cada 15 s para que la tablet detecte desconexión. El frontend debe
reconectar automáticamente y mostrar estado degradado mientras tanto.

---

## Frontend

- Next.js, target exclusivo: **1920×1200, horizontal, modo oscuro**
- Se ve desde 2–4 m de distancia. Números en fuente tabular.
- Dos estados de layout: normal y alerta. El diseño está en `docs/design/`.
- Sin interacción táctil como requisito: todo debe funcionar sin que nadie toque
  la pantalla.
- Sin animaciones permanentes ni blancos puros — la pantalla está encendida de
  noche en una sala.
- Estado de error explícito si el SSE se cae: la UI nunca debe mostrar datos
  viejos como si fueran actuales.

---

## Comandos

```bash
docker compose up -d              # levantar todo
docker compose logs -f daemon     # seguir el daemon
docker compose exec postgres psql -U sismos sismos

# construir para la Pi desde otra máquina
docker buildx build --platform linux/arm64 -t ghcr.io/<user>/sismos-daemon:latest --push ./daemon
```

---

## Estado y fases

- [ ] **Fase 1** — `daemon/`: ingesta de las 3 fuentes, deduplicación, persistencia
- [ ] **Fase 2** — `api/`: REST + SSE
- [ ] **Fase 3** — `web/`: dashboard según diseño
- [ ] **Fase 4** — `infra/`: compose, Caddy, systemd, healthchecks
- [ ] **Fase 5** — notificaciones: ntfy + MQTT hacia Home Assistant
- [ ] **Futuro** — SeedLink: detección propia sobre forma de onda de estaciones
      públicas, con STA/LTA. Objetivo: anticipación de 20–40 s antes de la onda S.

Trabajar una fase por sesión. Al terminar cada una, marcar aquí y anotar
decisiones no obvias que se hayan tomado.
