# web -- dashboard sísmico

Next.js (App Router, todo cliente: sin SSR real, todo es SSE/polling en
vivo). Ver `docs/design/handoff.md` para la especificación de diseño y
`CLAUDE.md` (sección "Frontend") para el contexto del proyecto.

## Desarrollo local

```bash
npm install
npm run dev
```

El servidor de Next.js reescribe `/api/*` hacia `API_INTERNAL_URL` (por
defecto `http://localhost:8000`, ver `.env.example` -> `.env.local`) --
el navegador siempre habla con el propio origen de Next.js, nunca
directo con la API. Si el backend (fases 1-2) no está levantado, la
página igual carga pero se queda "conectando" -- para ver algo sin
backend, usa los escenarios forzados de abajo.

## Forzar un estado para revisión (`?escenario=`)

Cada una de las 5 pantallas del handoff se puede forzar agregando
`?escenario=<nombre>` a la URL, sin tocar el backend ni esperar un sismo
real. Los datos vienen de `src/fixtures/`, con la misma forma que entrega
la API real (no la del handoff §7 -- ver `src/lib/types.ts`).

| Escenario | URL | Pantalla |
| --- | --- | --- |
| Normal | `/?escenario=normal` | `1a` -- actividad de fondo, sin avisos |
| Aviso nivel 2 | `/?escenario=aviso2` | Franja discreta de 120px sobre la lista |
| Aviso nivel 3 | `/?escenario=aviso3` | Popup emergente (`2a`), se cierra solo a los 45s |
| Alerta | `/?escenario=alerta` | `1b` -- igual que aviso3 pero ya pasó la ventana del popup |
| Error / sin dato | `/?escenario=error` | `1c` -- todas las fuentes en ámbar |

En un despliegue real (tablet en la pared) también funciona apuntando el
navegador a `http://<ip-de-la-pi>:3000/?escenario=aviso3`, útil para
probar el sonido/brillo nocturno sin esperar un sismo M6+.

### Forzar el brillo nocturno (`?noche=`)

`?noche=false` fuerza brillo pleno y `?noche=true` fuerza la atenuación al
45% (handoff §5.1, 23:00-07:00 CLT), sin tener que cambiar la hora del
sistema -- útil para revisar el diseño a plena luz del día. Combina con
`?escenario=`, ej. `/?escenario=alerta&noche=false`. Sin el parámetro,
decide el reloj real (`src/state/useNightMode.ts`).

### Revisar en una ventana angosta

El target es 1920×1200 fijo, pero el layout degrada con gracia hasta
~1200px de ancho (columnas del mapa/estado más angostas, luego la columna
de profundidad de la lista de eventos desaparece primero -- lugar y
distancia nunca lo hacen). Por debajo de 1200px no es un rango soportado:
la página fuerza un ancho mínimo y aparece scroll horizontal en vez de
solapar contenido.

Sin `?escenario=`, la página usa datos en vivo: `GET /api/events` +
`GET /api/config` + `GET /api/health` para la carga inicial, `GET
/api/stream` (SSE) después, con reconexión automática con backoff
exponencial (`src/lib/sse.ts`).

### Tablet Android / Fully Kiosk

`app/layout.tsx` fija `width=1920, initialScale=1, minimumScale=1,
maximumScale=1` en el meta viewport para que el WebView calcule un
viewport de layout de 1920px CSS en vez de su default (~980px, lo que
forzaba scroll horizontal en la tablet real -- "versión de escritorio"
se veía bien solo porque ese modo del navegador fija su propio ancho de
viewport por su cuenta, sin pasar por esta meta tag). Si algún WebView
igual la ignora, en Fully Kiosk Browser: **Web Content Settings → Force
Viewport Meta / Desktop Site → desactivado**, y **Zoom Level → 100%**
(no usar el zoom de la app para "hacer caber" la página: eso reescala
todo el layout, incluida la tipografía ya calibrada para 1920px reales).

## Variables de entorno

Ver `.env.example`. `API_INTERNAL_URL` es la única obligatoria: debe ser
una URL alcanzable desde el **servidor de Next.js** (que reescribe
`/api/*` hacia ahí, ver `next.config.ts`), no desde el navegador -- típicamente
`http://api:8000` (el nombre del servicio Docker) en producción/infra,
`http://localhost:8000` corriendo `npm run dev` fuera de Docker. El
navegador nunca necesita saber dónde vive la API: solo habla con su
propio origen (puerto 3000), lo que evita CORS y funciona igual desde la
tablet, un PC, o cualquier device en la LAN.

## Docker

```bash
cd ../infra
docker compose up -d --build web
```

`docker-compose.override.yml` (solo desarrollo) monta el código fuente y
corre `npm run dev` con hot reload -- no se necesita rebuild por cada
cambio, salvo en `package.json`. Producción en la Pi construye la imagen
`linux/arm64` con buildx (ver `CLAUDE.md`) y usa la imagen prebuilt, igual
que `daemon` y `api`.

## Decisiones de esta fase (no obvias)

- **El backend no expone el contrato del handoff §7 tal cual.** La API
  real (fases 1-2) entrega campos crudos (`lib/types.ts:RawEvent`), no el
  `Evento`/`Estado` idealizado de la maqueta. Todo lo derivado -- rumbo,
  nivel de aviso, resumen 48h, sentidos 90 días -- se calcula en
  `src/lib/derive.ts` y `src/state/`, no en el backend.
- **Nivel de aviso derivado de `estimated_mmi`, no de magnitud+distancia
  por separado.** El backend ya resume ambas cosas en un único número vía
  su GMPE (`daemon/intensity.py`); reimplementar el umbral "M 4.0-4.9 a
  <150km" del handoff en el cliente sería una segunda fuente de verdad que
  puede desincronizarse de la real.
- **"N de 3 fuentes confirman" solo se pide para el evento activo en
  aviso/alerta** (`GET /api/events/{cluster_key}`, con sus `reports`), no
  para las 8 filas de la lista normal -- sería un fetch extra por fila
  cada 30s sin necesidad.
- **Se agregó `GET /api/config`** (home lat/lon/etiqueta) y el filtro
  `?significant=true` en `GET /api/events` -- ambos de solo lectura,
  reflejan config/datos que el backend ya calculaba pero no exponía. Ver
  `api/routers/config.py` y `api/routers/events.py`.
- **Sin mapa de Chile "real" portado de una maqueta**: el HTML/JS de
  referencia del handoff (`Monitor Sismico.dc.html`, `seismic-map.js`) no
  está en el repo. El contorno nacional sale de `world-atlas` (Natural
  Earth, dominio público) recortado una sola vez a Chile en
  `scripts/build-chile-map-data.mjs` -> `src/data/chile.geo.json`, para no
  enviarle a la tablet el atlas mundial completo.
- **Réplicas para la salida de "alerta"**: sin clustering espacial en el
  cliente (eso es trabajo de `dedup.py` sobre `cluster_key`, no de esta
  UI), cualquier evento M>=3.5 significativo posterior al inicio de la
  ventana extiende los 20 minutos de salida. Es conservador a propósito:
  en una secuencia sísmica activa mantiene la pantalla en alerta un poco
  más de lo estrictamente necesario, nunca menos.
- **Dos textos del handoff se omitieron a propósito** por contradecir
  reglas explícitas de CLAUDE.md en vez de reproducir el mockup literal:
  no se muestra una "próxima revisión" a una hora fija (las fuentes no
  publican en un horario conocido; se muestra la hora de la última
  revisión real en su lugar) ni una estimación de llegada de onda S (el
  propio proyecto documenta que no hay ventana de anticipación real --
  CLAUDE.md "Alertas por proximidad, no por anticipación").
