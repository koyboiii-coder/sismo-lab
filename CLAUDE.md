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

Configuración en `infra/.env` (obligatoria, sin default -- ver "Sin
default de ubicación en silencio" más abajo):

```
HOME_LAT=-36.633544    # Coihueco, Región de Ñuble
HOME_LON=-71.829477
HOME_LABEL=Coihueco
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
- [x] **Fase 3** — `web/`: dashboard según diseño
- [ ] **Fase 4** — `infra/`: compose, Caddy, systemd, healthchecks
- [~] **Fase 5** — notificaciones: ntfy hecho, MQTT/Home Assistant pendiente
- [ ] **Futuro** — SeedLink: detección propia sobre forma de onda de estaciones
      públicas, con STA/LTA. Objetivo: anticipación de 20–40 s antes de la onda S.

Trabajar una fase por sesión. Al terminar cada una, marcar aquí y anotar
decisiones no obvias que se hayan tomado.

### Decisiones no obvias — motor de intensidad y alertas (sesión posterior a fase 2)

- **Rrup vs. distancia hipocentral**: `youngs_1997_pga_g` necesita distancia
  a la ruptura (Rrup), no al hipocentro. Sin geometría real, se usa
  Wells & Coppersmith (1994) para estimar el largo de ruptura desde M y
  recortar la distancia hipocentral por ese largo, con piso en `depth_km`
  (`intensity.rupture_distance_km`) — deliberadamente el caso más
  conservador (la ruptura se extiende su largo completo hacia el sitio),
  no un promedio. Sin esto, un M8.8 a 350 km calculaba MMI IV en vez de
  VII y no cruzaba el umbral de alerta completa. Cuando USGS publica
  geometría real de ruptura (M≥7, `shakemap.rupture.json`, ver
  `connectors/usgs.fetch_rupture_geometry`), esa geometría reemplaza la
  aproximación — `events.intensity_geometry_source` /
  `intensity_distance_saturated` registran cuál se usó, para que el
  dashboard pueda mostrar la MMI como cota incierta en vez de cifra precisa
  cuando corresponda. Ver `daemon/validate_intensity.py` para el detalle
  numérico completo.
- **Alertas por proximidad, no por anticipación**: las 3 fuentes publican
  con 2-5 min de retraso, así que no hay ventana de anticipación real. El
  daemon prioriza latencia de notificación sobre precisión inicial: alerta
  con el primer reporte que cruce un umbral MMI, sin esperar confirmación
  de otras fuentes (`db.Writer._create_event`/`_recanonicalize` +
  `alerts.py`). Nunca reenvía por una revisión salvo que se cruce un umbral
  más alto que el ya notificado (`events.alert_level_sent`).
- **ntfy con auth, no un topic público**: el servicio `ntfy` en
  docker-compose corre con `auth-default-access=deny-all`. Bootstrap único
  vía `infra/ntfy-setup.sh` (crea usuario/token para el daemon y un usuario
  de solo lectura para el teléfono/dashboard). `NTFY_TOKEN` vive en
  `infra/.env` (gitignored), nunca en docker-compose.yml.
- **Bandera de tsunami es solo un heurístico de "revisa la fuente oficial"**:
  `tsunami.py` marca eventos costeros y superficiales (tabla de referencia
  de costa hecha a mano, sin dataset real) para destacar el aviso — nunca
  reemplaza una determinación real. No existe una API/feed pública de
  boletines SHOA/SNAM en tiempo real (se investigó shoa.cl y snamchile.cl:
  ambos son páginas pensadas para humanos, sin JSON/RSS consultable); la
  notificación simplemente enlaza a snamchile.cl y menciona SENAPRED en vez
  de intentar un scraper frágil para una decisión de evacuación.
- **UI (Fase 3): implementada en `web/`**, ver la sección de decisiones más
  abajo. El texto permanente "informativo post-evento, no alerta
  temprana" ya está en el pie del aviso emergente
  (`web/src/components/alert/AvisoPopup.tsx`).

### Decisiones no obvias — dashboard (fase 3, `web/`)

- **`docs/design/handoff.md` §7 (contrato de datos) es de la maqueta, no
  de la API real.** La API de fases 1-2 entrega filas crudas de `events`
  (ver `api/notifier.py:serialize_event`), no el `Evento`/`Estado`
  idealizado del handoff. Todo lo derivado — rumbo, nivel de aviso,
  resumen 48h, sentidos 90 días — se calcula en el cliente
  (`web/src/lib/derive.ts`, `web/src/state/`), no en el backend. El nivel
  de aviso (escalera 1/2/3 del handoff §5.1) se deriva de
  `estimated_mmi` solamente, no de umbrales de magnitud+distancia por
  separado: el backend ya resume ambas cosas en un único número vía su
  GMPE, reimplementar el umbral en el cliente sería una segunda fuente de
  verdad que puede desincronizarse de la real.
- **Next.js, no Vite** (el prompt del propio handoff sugería Vite):
  se mantuvo la invariante ya escrita en este archivo. Todo cliente, sin
  SSR real — el REST inicial y el SSE corren en el navegador de la tablet,
  no en el proceso de Next.js.
- **Dos adiciones mínimas a `api/`**, ambas de solo lectura: `GET
  /api/config` (expone `HOME_LAT`/`HOME_LON`/`HOME_LABEL`, que ya
  calculaba el daemon pero no se exponían) y el filtro `?significant=true`
  en `GET /api/events` (para pedir 90 días de "sentidos aquí" sin traer
  cada sismo chico de ese período). Ver `api/routers/config.py`,
  `api/routers/events.py`.
- **Mapa de Chile sin maqueta portada**: `Monitor Sismico.dc.html` /
  `seismic-map.js`, referenciados por el handoff, no están en el repo. El
  contorno nacional sale de `world-atlas` (Natural Earth, dominio
  público), recortado una sola vez a Chile por
  `web/scripts/build-chile-map-data.mjs` en `web/src/data/chile.geo.json`
  — no se le manda a la tablet el atlas mundial completo.
- **"N de 3 fuentes confirman" solo se pide para el evento activo en
  aviso/alerta** (`GET /api/events/{cluster_key}`), no para las 8 filas de
  la lista normal, para no hacer un fetch extra por fila cada 30 s.
- **Réplicas para la salida de "alerta" (20 min sin M≥3.5, handoff §4)**:
  sin clustering espacial en el cliente — cualquier evento M≥3.5
  significativo posterior al inicio de la ventana extiende la salida. Es
  conservador a propósito: en una secuencia activa mantiene la pantalla en
  alerta un poco más de lo necesario, nunca menos.
- **Dos textos del handoff se omitieron a propósito**, por contradecir
  reglas ya escritas en este archivo en vez de reproducir el mockup
  literal: no se muestra una "próxima revisión" a una hora fija (las
  fuentes no publican en un horario conocido) ni una estimación de
  llegada de onda S ("Alertas por proximidad, no por anticipación" arriba
  es explícito en que no hay ventana de anticipación real).
- **No se pudo verificar visualmente en navegador** — el entorno de esta
  sesión no tenía un browser real disponible para probar. Verificado en
  su lugar: `tsc --noEmit`, `next lint` y `next build` limpios, y las 5
  pantallas (`?escenario=normal|aviso2|aviso3|alerta|error`, ver
  `web/README.md`) responden 200 sin errores de servidor tanto en `next
  start` como en la imagen Docker final. Falta una revisión visual real
  en la tablet o un navegador antes de dar la fase por completamente
  cerrada.

### Decisiones no obvias — conectividad del dashboard y ubicación (sesión posterior a fase 3)

- **`/api/*` vía proxy de Next.js, no `NEXT_PUBLIC_API_URL`**: el
  navegador de la tablet (o cualquier PC en la LAN) solo habla con el
  propio origen de `web/` (puerto 3000), que reenvía hacia
  `API_INTERNAL_URL` (el nombre del servicio Docker `api`, solo resuelve
  dentro de la red de compose — ver `infra/docker-compose.yml`). El diseño
  anterior horneaba `NEXT_PUBLIC_API_URL` en el bundle del cliente en build
  time con default `http://localhost:8000`; como "localhost" desde el
  navegador de cualquier dispositivo que no fuera la propia Pi apunta al
  dispositivo mismo, `/api/*` fallaba con `net::ERR_*` desde la tablet y
  desde cualquier PC — el backend estaba sano, el cliente apuntaba mal. El
  proxy también evita tener que configurar CORS.
  - **Route Handler (`web/src/app/api/[...path]/route.ts`), no
    `rewrites()` en `next.config.ts`**: `rewrites()` resuelve su
    `destination` en build time — con `API_INTERNAL_URL` sin definir
    durante `docker build` (docker-compose solo la pasa como `environment`
    en runtime, nunca como build arg), la imagen quedaba con
    `http://localhost:8000` horneado sin importar el ENV real del
    contenedor, y el proxy fallaba con `ECONNREFUSED 127.0.0.1:8000` pese a
    que `API_INTERNAL_URL=http://api:8000` era correcta en runtime
    (`docker compose exec web env` la mostraba bien — el bug estaba en
    cuándo se leía, no en su valor). El Route Handler lee
    `process.env.API_INTERNAL_URL` en cada request, así que la misma
    imagen sirve en cualquier entorno sin reconstruirla.
  - Verificado que `/api/stream` (SSE) sigue sin bufferearse a través del
    Route Handler: contra un backend con framing por chunks real (igual al
    `StreamingResponse` de starlette/uvicorn), los ticks llegan al cliente
    espaciados como el backend los emite, no todos juntos al final. Un
    cierre ordenado del backend (`res.end()`) termina el stream del
    cliente con normalidad; un cierre abrupto (`socket.destroy()`,
    simulando que cae el contenedor de `api`) se propaga como error de
    conexión de inmediato en vez de dejar el fetch colgado — el cliente
    (`web/src/lib/sse.ts`) lo ve como el `error` nativo de `EventSource` y
    reconecta con su backoff ya existente, sin depender del watchdog de
    40 s. (Un mock inicial con `http.server` de Python en HTTP/1.0, sin
    `Transfer-Encoding: chunked`, sí dejaba el fetch de Node colgado
    indefinidamente al cerrar la conexión — es una limitación de cómo
    undici interpreta el cierre de un socket HTTP/1.0 sin framing
    explícito, no representativa del backend real, que siempre habla
    HTTP/1.1 con chunks.)
- **Sin default de ubicación en silencio**: `HOME_LAT`/`HOME_LON` ya no
  tienen valor por defecto en `daemon/config.py` ni `api/config.py` (antes
  caían en un placeholder de Concepción, `-36.8270,-73.0498`, que nunca
  fue la ubicación real) — falta cualquiera de las dos y el proceso
  levanta una `RuntimeError` al iniciar. `infra/docker-compose.yml` usa
  `${HOME_LAT:?...}` (sin default), así que `docker compose up` falla de
  inmediato si `infra/.env` no las trae, antes incluso de levantar
  contenedores. En el frontend, `web/src/components/Dashboard.tsx` ya no
  usa un fallback con coordenadas reales (antes eran las de Santiago,
  `-33.457,-70.601`, mostradas como si fueran datos mientras `/api/config`
  no cargaba o fallaba) — mientras la config no llega, se muestra un
  estado de carga genuino sin cifras, y `TopBar`/`ErrorState` aceptan
  `homeLat`/`homeLon` nulos para mostrar "ubicación no disponible" en vez
  de una posición fabricada. Motivo: un número con pinta de coordenada
  real es indistinguible de un dato real para quien mira el dashboard —
  el mismo principio que "la UI nunca debe mostrar datos viejos como si
  fueran actuales" (sección Frontend), aplicado a la ubicación.
- **`daemon/recompute.py` corrido una vez tras fijar `HOME_LAT`/`HOME_LON`
  reales** (Coihueco, Región de Ñuble): todo evento guardado hasta ahora
  tenía `distance_km`/`estimated_pga`/`estimated_mmi`/`is_significant`
  calculados contra el placeholder de Concepción, no la ubicación real —
  ver el resultado del run para el conteo de eventos corregidos.

### Decisiones no obvias — `?escenario=alerta` en blanco, badge de "sentido" y layout angosto (sesión posterior a fase 3)

- **La causa de `?escenario=alerta` era un loop de render infinito, no un
  fixture con forma equivocada.** `Dashboard.tsx` llamaba
  `construirEscenario(nombreEscenario)` directo en el cuerpo del
  componente, sin `useMemo`; para "aviso2"/"aviso3"/"alerta",
  `fixtures/scenarios.ts` arma el array de eventos con spread
  (`[evento, ...EVENTOS_BASE]`), una referencia nueva en cada llamada
  (a diferencia de "normal"/"error", que reusan la constante
  `EVENTOS_BASE` tal cual). `useAvisoMachine.ts` ajusta su estado
  comparando `eventos !== eventosProcesados` durante el render -- un
  patrón que React solo soporta si esa referencia eventualmente se
  vuelve estable. Como nunca lo hacía, cada render disparaba otro
  render con una referencia distinta de nuevo, sin converger, hasta que
  React lo corta con "Too many re-renders" y Next reemplaza toda la
  pantalla por su fallback genérico ("This page couldn't load"). Se
  reprodujo aislado (fuera de Next, con `react-dom/server` + una copia
  mínima de la lógica) antes de tocar el código, para no perseguir un
  diagnóstico equivocado -- confirmado que memoizar `escenario` con
  `useMemo(..., [nombreEscenario])` lo resuelve. Quedaba latente también
  en aviso2/aviso3 aunque no se hubiera notado ahí todavía.
- **`AlertErrorBoundary` envuelve solo `<AlertLayout>`**, no todo
  `Dashboard`: por diseño no captura el bug de arriba (el throw ocurre
  antes, dentro del hook, no en el subárbol de AlertLayout), pero sí
  cualquier falla futura específica de esa pantalla -- durante un sismo
  real, magnitud/distancia/MMI a medias es mejor que la pantalla en
  blanco de Next. El fallback recibe `evento` por prop, no lo lee del
  subárbol que falló.
- **`sentidoEnLaZona` (badge "SENTIDO EN LA ZONA" en `EventRow.tsx`) ahora
  exige `enChile(evento)` además de M≥4.0.** La lista de columna B mezcla
  actividad nacional con sismos mundiales M6.5+ (CLAUDE.md, "sin alerta
  local" -- ver `EVENTOS_BASE` en fixtures, que ya incluye dos de esos).
  Sin el filtro, cualquier evento mundial grande mostraba la etiqueta
  como si fuera relevante (caso real: M en Afganistán, 16.700 km, MMI I
  aquí). "Zona" se refiere al entorno del epicentro, no a HOME, pero un
  evento fuera de Chile no es una "zona" que este dashboard pueda
  interpretar.
- **Layout angosto (~1200-1920px, solo para revisar en un navegador de
  escritorio -- el target sigue siendo 1920×1200 fijo en la tablet):**
  `--ancho-col-mapa`/`--ancho-col-estado` (`theme/tokens.css`) pasaron de
  px fijo a `clamp()` en vw, para que el mapa y la columna de estado
  cedan ancho antes que la lista de eventos. Las columnas del `NormalLayout`
  llevan `container-type: inline-size` y las cabeceras/grillas usan
  `@container`, no `@media`: lo que importa es el ancho de esa columna,
  no el del viewport (las tres columnas nunca miden lo mismo). La grilla
  de fila de `EventList` pasó de anchos fijos a `minmax()` con piso más
  alto en lugar/distancia que en hora/magnitud -- para que esas dos nunca
  sean las primeras en perder espacio -- y la columna de profundidad
  (la única puramente decorativa: se repite como color en otras vistas)
  es la primera en ocultarse del todo bajo cierto ancho de columna. Por
  debajo de ~1200px no se intenta soportar: `Dashboard.module.css` fija
  un `min-width` y `html`/`body` permiten scroll horizontal ahí, para que
  se vea recortado en vez de con texto solapado.
- **`?noche=false`/`?noche=true`** (`useNightMode.ts`, parámetro opcional
  `forzar`) sobrescriben el cálculo por hora del atenuador nocturno
  (handoff §5.1) sin cambiar la hora del sistema, para poder revisar el
  diseño a brillo pleno en desarrollo. Sin el parámetro decide el reloj
  real, igual que antes.
