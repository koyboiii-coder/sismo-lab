# Monitor sísmico doméstico · Chile — especificación de diseño y handoff

Documento único para los docs del proyecto. Contiene (1) el contexto y las decisiones de diseño,
(2) la especificación pixel a pixel de las cuatro pantallas y del servicio de aviso, (3) el contrato
de datos esperado del backend, y (4) al final, el **prompt listo para pegar en Claude Code**.

Maqueta de referencia (prototipo HTML, no código de producción): `Monitor Sismico.dc.html`
(+ `seismic-map.js`, mapa D3/TopoJSON). Fidelidad: **alta (hi-fi)** — colores, tipografía,
tamaños y jerarquía son finales.

---

## 1. Contexto del producto

Pantalla fija montada en pared de una casa en Ñuñoa, Santiago (Chile), sobre un **Lenovo Tab M11
en horizontal: 1920 × 1200 px CSS**. Siempre encendida, sin teclado, sin ratón, casi sin toques.
Se lee **de pie, a 2–4 metros**, con luz diurna variable y en modo oscuro obligatorio.

Consecuencias de diseño, no negociables:

- **Sin interacción como requisito.** Todo lo importante debe estar visible sin tocar nada. El único
  toque previsto es cerrar el aviso emergente.
- **Nada de scroll, nada de hover, nada de tooltips.** No hay puntero.
- **Tamaño mínimo real:** texto de dato ≥ 20 px; etiquetas de sección 11–13 px solo en mayúsculas
  con tracking; cifras protagonistas 44–288 px. Zonas tocables ≥ 44 px.
- **Instrumento científico, no app de consumo.** Sin tarjetas redondeadas, sin sombras difusas, sin
  degradados decorativos, sin emoji, sin iconos ilustrativos. Regla de 2 px y alineación a la
  izquierda hacen todo el trabajo de orden (sistema Modernist).
- **Cifras tabulares** (`font-variant-numeric: tabular-nums`) en todo dato numérico: a 3 m, las cifras
  que bailan se leen mal.

### Estados del producto

| Estado | Cuándo | Archivo/marco |
| --- | --- | --- |
| **Normal** | 99 % del tiempo | `1a Normal` |
| **Aviso emergente** | 45 s tras un sismo significativo cercano | `2a Aviso emergente` |
| **Alerta** | Desde el cierre del aviso hasta 20 min tras la última réplica M 3.5 + | `1b Alerta` |
| **Error / sin dato** | El agregador no responde | `1c Error` |
| Sistema de diseño | Referencia (no es pantalla) | `1d`, `2b` |

---

## 2. Tokens de diseño

### Color

Paleta cerrada. **No agregar colores.** El significado del color es semántico y estricto.

| Token | Hex | Uso |
| --- | --- | --- |
| `--fondo` | `#171615` | Fondo de pantalla |
| `--fondo-lienzo` | `#0c0b0b` | Fondo del lienzo de maqueta / velo de atenuación |
| `--panel` | `#1c1a19` | Barra superior, paneles, fila destacada |
| `--panel-alto` | `#211f1d` | Bloques enfatizados (último sentible, pie del aviso) |
| `--tinta` | `#e8e4e1` | Texto principal |
| `--tinta-2` | `#c9c4c0` | Texto secundario / descripción |
| `--tinta-3` | `#a29c97` | Etiquetas activas, datos de apoyo |
| `--tinta-4` | `#6f6a66` | Etiquetas de sección, metadatos |
| `--div-fuerte` | `#35322f` | Divisor de 2 px entre zonas mayores |
| `--div-suave` | `#2a2725` | Divisor de 1 px entre filas |
| `--barra-1..4` | `#e8e4e1` `#6b645e` `#4a4540` `#423d39` | Peso de severidad en la lista (sin color) |
| `--alerta` | `#ff563c` | **Solo evento sísmico significativo** |
| `--degradado` | `#ffb43a` | **Solo el sistema no es confiable** / prof. 0–35 km / aviso nivel 2 |
| `--nominal` | `#3fb9a6` | Fuente en línea / prof. 35–120 km |
| `--profundo` | `#6a86d8` | Prof. +120 km |

Reglas semánticas:

1. **Rojo `#ff563c` = evento sísmico significativo.** Nunca para errores, nunca decorativo.
2. **Ámbar `#ffb43a` = el sistema no es confiable** (fuente caída, dato viejo, aviso menor).
3. **La severidad en la lista de eventos no usa color**: se codifica con luminancia del texto y con
   el alto/tono de la barra izquierda de 6 px. Así el rojo conserva su significado.
4. **Profundidad** es la única escala cromática: ámbar (superficial) → teal → azul (profundo).
5. `sin dato ≠ todo en calma`: si una fuente falla se rotula *SIN DATO* en ámbar, jamás se afirma
   que no hay sismos.

### Tipografía

Familia única: **Archivo** (Google Fonts, pesos 400–900). Sin segunda familia.

| Rol | px | peso | tracking | notas |
| --- | --- | --- | --- | --- |
| Magnitud héroe (alerta) | 288 | 800 | −0.04em | line-height 0.82 |
| Magnitud aviso emergente | 196 | 800 | −0.04em | line-height 0.84 |
| Intensidad MMI | 104–112 | 800 | — | color `--alerta` |
| Título de aviso | 38 | 800 | 0.02em | mayúsculas |
| Epicentro | 60 | 800 | −0.02em | caja alta y baja |
| Cifra grande de panel | 44–76 | 800 | — | tabular |
| Dato de fila | 20–34 | 600–800 | — | tabular |
| Referencia geográfica | 21 | 600 | — | caja alta y baja |
| Encabezado de panel | 12 | 700 | 0.14em | MAYÚSCULAS |
| Etiqueta de sección | 11–13 | 700 | 0.16–0.18em | MAYÚSCULAS, `--tinta-4` |
| Metadato de fila | 11 | 600 | 0.12–0.14em | MAYÚSCULAS |

### Espaciado y estructura

Escala: **4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56**.

- Radio de esquina: **0 px en todo el producto.**
- Divisor de zona mayor: **2 px `#35322f`**. Divisor de fila: **1 px `#2a2725`**.
- Barra superior: **76 px**. Cabecera de panel: **44 px**. Fila de evento: **90 px** exactos.
- Padding: panel 20 px · columna de eventos 24 px · barra superior 28 px.
- Sombras: ninguna, salvo el halo del aviso emergente (`0 0 0 12px rgba(255,86,60,0.10)`), que es
  un realce de borde, no una elevación.
- Animación: solo `pulse-dot` (`opacity 0.35 → 1`, 2.4 s en alerta, 1.6 s en el aviso). Nada se
  desliza, nada rebota. Los cambios de valor son reemplazos directos.

---

## 3. Pantalla `1a` — estado normal

`1920 × 1200`. Columna vertical: barra superior 76 px + cuerpo 1122 px.

### 3.1 Barra superior (76 px, fondo `--panel`, borde inferior 2 px)

Flex, `gap: 28px`, padding lateral 28 px:
`MONITOR SÍSMICO` (22/800/0.04em) · separador vertical 2 × 34 px · `ÑUÑOA · SANTIAGO · 33.457°S 70.601°W`
(15/600/0.1em, `--tinta-3`) · **a la derecha**: tres indicadores de fuente (cuadrado 10 px + sigla
13/700/0.12em) `CSN` `USGS` `EMSC`, separador, reloj `15:42:07` (30/700, tabular) con
`LUN 25 AGO 2026 · CLT` debajo (11/600/0.16em).

### 3.2 Cuerpo — tres columnas: **520 | flexible (996) | 400**

Divisores verticales de 2 px entre columnas.

**Columna A — mapa nacional (520 px)**
1. Cabecera 44 px: `ACTIVIDAD NACIONAL · 48 H` / `37 EVENTOS`.
2. Mapa de Chile (D3 + TopoJSON, proyección Mercator ajustada al país), 518 × 856. Círculos: radio
   por magnitud (M2 = 8 px, M3 = 16, M4 = 26, M5 = 38 px de diámetro), relleno translúcido y borde
   por profundidad. Cuadrado de 18 px con borde `--tinta` = *mi ubicación*.
3. Chile es angosto: el espacio muerto del costado lleva un **histograma latitudinal** — una barra
   ámbar por región con el conteo de eventos, alineada a la latitud del mapa. Permite leer "dónde
   está pasando" sin contar puntos.
4. Leyenda inferior: profundidad (3 muestras), magnitud (4 círculos), mi ubicación.

**Columna B — lista de eventos (flexible)**
1. Cabecera 44 px: `ÚLTIMOS EVENTOS · AGREGADO CSN + USGS + EMSC` / `ORDEN CRONOLÓGICO INVERSO`.
2. Bloque **último sismo sentible** (fondo `--panel-alto`, padding 18/24): `HACE 3 DÍAS` (46/800),
   separador, `M 4.4 · 22 km NO de Valparaíso · Mercalli III` (20/600) con metadato debajo, y a la
   derecha `RACHA SIN SISMOS SENTIBLES` + `72 h 14 min` (26/700).
3. Encabezado de tabla 34 px y **8 filas de 90 px** (total 726 px). Grilla de fila, idéntica en
   encabezado y filas: `6px 104px 116px 1fr 108px 168px`, `padding-right: 24px`.
   - Col 1: barra de severidad de 6 px (alto 46 px normal, 66 px destacada; color de `--barra-*`).
   - Col 2: hora `15:12` (24/700 tabular) + `HACE 30 MIN` (11/600/0.12em).
   - Col 3: `M` (15/700 `--tinta-4`) + cifra (34/800; 38 si el evento fue sentido).
   - Col 4: referencia geográfica (21/600) + `REGIÓN · FUENTES · MERCALLI` (11/600/0.14em). Si fue
     sentido en la zona: etiqueta `SENTIDO EN LA ZONA` (11/700, borde 1 px ámbar, padding 2/7).
   - Col 5: cuadrado 10 px del color de profundidad + `62 KM` (20/600 tabular).
   - Col 6, a la derecha: distancia `41 km` (22/600) + `SE · NO SENTIDO` o `N · MMI I AQUÍ`.
   - Fila destacada (evento sentido): fondo `#1c1a19`, barra `--tinta`, distancia en `--tinta`.

**Columna C — estado del sistema (400 px)**, apilada de arriba a abajo:
1. `SALUD DEL SISTEMA` — una fila por fuente: cuadrado de estado, sigla, latencia, y `SIN DATO` en
   ámbar si falla.
2. `SISMICIDAD MUNDIAL M 6.0 +` — 3 eventos con magnitud (28/800), lugar y
   `HACE 2 D · PROF. 65 KM`; incluye la nota de tsunami cuando aplica. Panel opcional (tweak).
3. `RESUMEN 48 H · CHILE` — rejilla 2 × 2: `EVENTOS 37`, `M 4.0 + 06`, `MAGNITUD MÁX. 5.2`,
   `SENTIDOS AQUÍ 00` (cifras 44/800; el cero va en `--tinta-4`).
4. `SENTIDOS AQUÍ · 90 DÍAS` — 4 filas de 38 px: fecha, magnitud, lugar, `MMI III/IV/V`
   (el V en `--alerta`). Es la memoria local del hogar, no un dato de catálogo.
5. Pie (2 px arriba): `PAQUETE RECIBIDO HACE 12 S` con punto nominal y
   `SONDEO CADA 30 S · AGREGADOR v2.4 · UMBRAL DE AVISO MMI V O M 5.5 A MENOS DE 300 KM`.

---

## 4. Pantalla `1b` — estado de alerta

Se entra al cerrarse el aviso emergente (o a los 45 s). Reencuadra toda la jerarquía sobre el evento.

- **Franja superior 72 px, fondo `--alerta`, texto `#171615`**: `SISMO CERCA DE TU UBICACIÓN` (28/800),
  separador, `DETECTADO HACE 42 S · 15:41:38` (22/700), y a la derecha
  `CSN + USGS · 2 DE 3 FUENTES CONFIRMAN` (18/800/0.14em).
- **Panel izquierdo (flexible, padding 36/40)**: `M` 96/800 + `6.1` a **288 px**;
  al lado, `INTENSIDAD ESTIMADA AQUÍ` con `VI` a 104 px en rojo + `MERCALLI`, y la frase Mercalli en
  22/600 (`Sacudida fuerte. Objetos inestables se desplazan o caen…`).
- Caja `border: 2px solid --alerta`: `MAGNITUD PRELIMINAR — PUEDE CORREGIRSE EN LOS PRÓXIMOS MINUTOS`
  + `PRÓXIMA REVISIÓN 15:46`. **Honestidad del dato provisorio, obligatoria.**
- `EPICENTRO` `12 km al SO de Ñuñoa` (60/800) + coordenadas y comunas.
- Pie de 4 celdas (divisores de 1 px): `DISTANCIA 12 km`, `PROFUNDIDAD 47 km` (+ `INTERMEDIA`),
  `HORA LOCAL 15:41:38` (+ `ONDA S AQUÍ ≈ +3 s`), y la **escala Mercalli de 12 celdas** con la
  celda VI en rojo y las demás en grises del ramp.
- **Panel derecho (720 px)**: cabecera `EPICENTRO Y DISTANCIA` / `ANILLOS 50 / 100 / 200 KM`,
  mapa de zoom 718 × 620 con anillos de distancia, y `HISTORIAL DE SOLUCIONES` — tres filas
  (`15:41:44 M 5.8 CSN AUTOMÁTICA`, `15:42:10 M 6.0 USGS AUTOMÁTICA`, `15:43:02 M 6.1 CSN VIGENTE`)
  más la regla de salida: `LA PANTALLA VUELVE AL ESTADO NORMAL 20 MIN DESPUÉS DE LA ÚLTIMA RÉPLICA M 3.5 +`.

---

## 5. Pantalla `2a` — aviso emergente (el popup)

Es el servicio de alerta de proximidad. Aparece **encima** del estado normal.

- **Velo**: el tablero se mantiene visible al `22 %` de opacidad y encima va
  `rgba(12,11,11,0.82)`. No se usa blur: a 3 m el blur solo ensucia.
- **Ventana**: `left: 230px; top: 180px; width: 1460px`, fondo `--panel`, `border: 2px solid --alerta`,
  halo `0 0 0 12px rgba(255,86,60,0.10)`. Alto según contenido (≈ 640 px). Sin radio.
- **Cabecera 96 px, fondo `--alerta`**: punto pulsante de 16 px (`pulse-dot`, 1.6 s),
  `SISMO CERCA DE TU UBICACIÓN` (38/800), y a la derecha `HACE 8 S · 15:41:38` (24/800).
- **Bloque de datos** (dos celdas, divisor de 2 px):
  - Izquierda, 520 px: `MAGNITUD PRELIMINAR · Mw`, `M` 64 + `6.1` a **196 px**,
    y `CSN + USGS · 2 DE 3 FUENTES CONFIRMAN` (15/700/0.12em).
  - Derecha: `INTENSIDAD ESTIMADA AQUÍ`, `VI` a 112 px en rojo + `MERCALLI`, y la frase de qué
    significa, con instrucción práctica: 26/600, `--tinta-2`, `text-wrap: pretty`.
- **Rejilla de 4 celdas** (divisores de 1 px, padding 24/32): `EPICENTRO` (30/800, dos líneas),
  `DISTANCIA 12 km`, `PROFUNDIDAD 47 km`, `RÉPLICAS M 3.5 + 2 en 8 min` (cifras 64/800).
- **Pie (fondo `--panel-alto`, padding 22/32)**:
  `EL AVISO SE CIERRA SOLO EN 37 S Y EL TABLERO QUEDA EN ESTADO DE ALERTA` (19/700), barra de
  progreso de 6 px (`--div-fuerte` con relleno `--alerta`) que **decrece con el tiempo restante**, y
  el botón `TOCAR PARA CERRAR AHORA` (borde 2 px `--tinta`, padding 12/22, 17/800/0.1em).
- **Dos notas al pie de pantalla** (borde superior 2 px, ancho 1460):
  - `NO ES ALERTA TEMPRANA` (en ámbar): el aviso llega **después** del sismo (5–90 s), depende de la
    publicación de CSN/USGS. Este texto es obligatorio: no se puede insinuar anticipación.
  - `POR QUÉ INTERRUMPE`: nadie mira la pantalla en el momento; la ventana pone la respuesta al
    centro y en un solo tamaño para quien gira la cabeza después de sentirlo.

### 5.1 Escalera de aviso (`2b`) — lógica del servicio

| Nivel | Umbral | Comportamiento | Frecuencia esperada |
| --- | --- | --- | --- |
| **1 · Sin aviso** | MMI < III aquí, o M < 4.0 | Entra a la lista y al histograma. Nada se mueve, nada suena. | ≈ 40–90 / semana |
| **2 · Aviso discreto** | MMI III–IV aquí, o M 4.0–4.9 a < 150 km | Franja de **120 px** sobre la lista de eventos, **3 min**, barra ámbar de 8 px, cuenta atrás `SE CIERRA EN 2:20`. No tapa el mapa, no pide toque, no suena. | ≈ 2–6 / semana |
| **3 · Aviso emergente** | **MMI ≥ V aquí, o M ≥ 5.5 a < 300 km** | Ventana `2a` sobre el tablero atenuado, **45 s**; al cerrarse queda el estado de alerta `1b` hasta 20 min tras la última réplica M 3.5 +. | ≈ 3–8 / año |

Reglas transversales:

- **Un aviso por sismo.** Las réplicas y las revisiones actualizan la ventana abierta (reemplazo del
  número en su lugar, con la hora del cambio); no se abre una segunda ventana ni se apila nada.
- **Escalada en sitio.** Si un nivel 2 pasa a nivel 3 por revisión de magnitud, la franja se
  convierte en ventana en la misma posición del contenido.
- **Sonido:** solo nivel 3 — dos tonos de 0,4 s, sin repetición.
- **Noche (23:00–07:00):** el aviso aparece **sin sonido** y al 45 % de brillo.
- **Sin dato ≠ sin sismo.** Si el agregador no responde no se puede emitir aviso; eso se declara en
  el estado de error `1c` en ámbar, nunca como calma.

Contenido de la franja de nivel 2 (a escala, alto 120 px): barra ámbar 8 px · `M 4.4` (62/800) ·
divisor · `Melipilla · 58 km` (26/700) + `MMI III AQUÍ · PROF. 61 KM · HACE 40 S` (15/600/0.12em) ·
`SE CIERRA EN 2:20` a la derecha (14/700).

---

## 6. Pantalla `1c` — error / sin dato

Barra superior en gris (no roja: no hay sismo). El contenido se reemplaza por la declaración honesta
del fallo:

- Cifra grande con el tiempo **sin dato** y la hora del último paquete válido.
- `NO PUEDO AFIRMAR QUE NO HAY SISMOS` como mensaje central — el punto de todo el estado.
- Estado por fuente, todas en ámbar con `SIN DATO`; reintento y su cuenta atrás.
- Los datos viejos que se siguen mostrando quedan **rotulados como viejos**, atenuados, nunca como
  actuales.
- Sin rojo en toda la pantalla. Ámbar en todo lo que declare falta de confiabilidad.

---

## 7. Contrato de datos (lo que el frontend necesita del agregador)

```ts
type Fuente = { id: 'CSN' | 'USGS' | 'EMSC'; estado: 'ok' | 'sin_dato'; latenciaS: number | null };

type Evento = {
  id: string;
  hora: string;            // ISO 8601 con offset de Chile
  magnitud: number;        // Mw
  tipoMagnitud: string;    // 'Mw' | 'ML' …
  profundidadKm: number;
  lugar: string;           // "24 km NE de San José de Maipo"
  region: string;
  lat: number; lon: number;
  distanciaKm: number;     // calculada respecto de la ubicación de la casa
  rumbo: string;           // 'N' | 'NE' | …
  mmiAqui: number | null;  // intensidad estimada en la casa (1–12), null si no estimable
  sentido: boolean;
  fuentes: string[];       // qué fuentes lo confirman
  preliminar: boolean;
  revisiones: { hora: string; magnitud: number; fuente: string; vigente: boolean }[];
};

type Estado = {
  actualizadoEn: string;
  fuentes: Fuente[];
  ubicacion: { lat: number; lon: number; etiqueta: string };
  eventos: Evento[];          // 48 h, orden cronológico inverso
  mundiales: Evento[];        // M 6.0 + globales
  sentidos90d: Evento[];      // memoria local
  resumen48h: { total: number; sobre4: number; magMax: number; sentidosAqui: number };
  aviso: { nivel: 1 | 2 | 3; eventoId: string; abiertoEn: string; cierraEn: string } | null;
};
```

Reglas de backend que el frontend asume:

- La ventana de aviso se **deriva de `aviso`**, no de heurística en el cliente: el nivel lo decide el
  agregador para que sea auditable y no cambie por un refresh.
- Si una fuente falla, el campo llega como `sin_dato`; el backend **nunca** infiere "no hay sismos".
- `mmiAqui` es una estimación (atenuación por distancia y profundidad) y debe rotularse como tal.
- Sondeo cada 30 s; el frontend muestra la edad del último paquete siempre.

---

## 8. Prompt para Claude Code

Copiar y pegar tal cual en Claude Code, en la raíz del repositorio del proyecto, junto a este
documento y a los archivos de maqueta (`Monitor Sismico.dc.html`, `seismic-map.js`).

```text
Contexto: adjunto la especificación de diseño "HANDOFF Monitor Sismico.md" y la maqueta HTML
"Monitor Sismico.dc.html" (+ "seismic-map.js"). La maqueta es una REFERENCIA DE DISEÑO en HTML:
un prototipo que muestra el aspecto y el comportamiento final. NO la copies como código de
producción y NO la importes: reconstruye estas pantallas en el entorno del repositorio siguiendo
sus patrones existentes. Si el repositorio todavía no tiene frontend, crea uno con Vite + React +
TypeScript y CSS plano con variables de tema (sin librería de componentes ni framework de utilidades:
este diseño es a medida y las librerías estorban).

Objetivo: el frontend de un panel sísmico doméstico que corre a pantalla completa en una tablet
Lenovo Tab M11 montada en la pared, 1920 × 1200 px CSS, horizontal, siempre encendida, leída a 2–4
metros y casi sin interacción. Fidelidad requerida: ALTA. Los valores del documento (hex, px, pesos,
tracking, alturas de fila) son finales; respétalos al pixel y no los "mejores".

Alcance de esta tarea:
1. Layout base 1920 × 1200 sin scroll, en modo oscuro, con las variables de color y la escala
   tipográfica de la sección 2 del documento como tokens CSS en un único archivo de tema.
2. Pantalla de estado normal (sección 3): barra superior, columna de mapa 520, lista de eventos
   flexible con filas de EXACTAMENTE 90 px, y columna de estado 400 con sus cuatro módulos.
3. Mapa de Chile con D3 + TopoJSON: vista nacional, vista de zoom con anillos de 50/100/200 km, y el
   histograma latitudinal por región. Puedes portar la lógica de "seismic-map.js" como componente del
   repositorio; mantén el radio por magnitud y el color por profundidad tal como están especificados.
4. Estado de alerta (sección 4) y estado de error / sin dato (sección 6) como estados de la misma
   pantalla, no como rutas distintas.
5. Servicio de aviso (sección 5): componente de ventana emergente nivel 3 con temporizador de 45 s y
   barra de progreso decreciente, franja discreta nivel 2 de 120 px con cierre a los 3 min, y la
   máquina de estados de la escalera (un aviso por sismo, escalada en sitio, salida de alerta 20 min
   tras la última réplica M 3.5 +, silencio y 45 % de brillo entre 23:00 y 07:00).
6. Capa de datos contra el contrato de la sección 7, con sondeo cada 30 s, edad del último paquete
   siempre visible, y datos de ejemplo (fixtures) tomados de la maqueta para desarrollo sin backend.

Reglas de diseño que no se negocian:
- Radio de esquina 0 en todo. Divisores de 2 px entre zonas y 1 px entre filas. Sin sombras (la única
  excepción es el halo del aviso emergente, especificado en la sección 5).
- Rojo #ff563c solo para evento sísmico significativo. Ámbar #ffb43a solo para "el sistema no es
  confiable". La severidad en la lista se codifica con luminancia y con la barra de 6 px, nunca con
  color. Profundidad es la única escala cromática (ámbar → teal → azul).
- font-variant-numeric: tabular-nums en todo dato numérico. Familia única Archivo.
- Todo alineado a la izquierda, incluidas las etiquetas dentro de botones. Nada centrado.
- Sin hover, sin tooltips, sin scroll, sin emoji, sin iconos decorativos. La única zona tocable es
  cerrar el aviso, y mide más de 44 px.
- "Sin dato" nunca se representa como calma: si una fuente falla, se rotula SIN DATO en ámbar.
- La magnitud preliminar siempre viene acompañada de la advertencia de que puede corregirse, y el
  aviso siempre lleva la nota de que NO es alerta temprana.
- Animación: solo el punto pulsante especificado. Ningún elemento se desliza ni rebota; los valores
  se reemplazan en su lugar.

Entrega: componentes tipados, un archivo de tema con los tokens, fixtures de datos, y un README
corto que explique cómo forzar cada estado (normal, aviso nivel 2, aviso nivel 3, alerta, error) para
poder revisarlos en la tablet. Antes de escribir código, dime en una lista breve cómo vas a estructurar
los componentes y qué decisiones del documento piensas resolver distinto en este repositorio.
```

---

## 9. Pendientes y decisiones abiertas

- **Umbrales**: los de la sección 5.1 son una propuesta (MMI ≥ V o M ≥ 5.5 a < 300 km). Ajustar tras
  observar un mes real de eventos; el objetivo es 3–8 ventanas al año, no más.
- **Sensor local**: si más adelante se agrega un acelerómetro en la casa, el MMI observado reemplaza
  al estimado y la etiqueta cambia de `ESTIMADA AQUÍ` a `MEDIDA AQUÍ`.
- **Panel de tendencia histórica** y **atenuación nocturna automática** existen como opciones en la
  maqueta (`mostrarTendencia`, `atenuacionNocturna`); decidir si entran a la v1.
