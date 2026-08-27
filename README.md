# sismos-dashboard

Sistema de monitoreo sísmico en tiempo real para una Raspberry Pi 5. Ver
[`CLAUDE.md`](CLAUDE.md) para arquitectura, fuentes de datos, esquema de base
de datos y reglas del proyecto.

## Desarrollo local

```bash
cd infra
docker compose up -d
docker compose logs -f daemon
```

`docker compose` combina automáticamente `docker-compose.yml` con
`docker-compose.override.yml` (sin flags extra) cuando corre desde `infra/`.
Ese override monta `daemon/` como volumen dentro del contenedor, así que un
archivo nuevo o editado se ve inmediatamente adentro sin rebuild.

**Igual hay que reiniciar el proceso para que tome el cambio** — el volumen
solo sincroniza los archivos, no reinicia el intérprete de Python:

```bash
docker compose restart daemon
```

### Cuándo sí hace falta rebuild

El volumen no reemplaza el build en estos casos, porque son cosas que se
resuelven al construir la imagen, no al arrancar el proceso:

- **Cambios en `daemon/requirements.txt`** (dependencias se instalan en el
  build).
- **Cambios en `daemon/Dockerfile`**.

```bash
docker compose build daemon && docker compose up -d daemon
```

Si algo se comporta raro y no estás seguro de si es por esto, `docker compose
up -d --build daemon` fuerza el rebuild y de paso el restart — más lento pero
elimina la duda.

Lo mismo aplica en principio para `api/`, pero `docker-compose.override.yml`
hoy solo monta `daemon/` y `web/` (ver ese archivo si hace falta
extenderlo). `web/` es la excepción: `next dev` ya trae su propio hot
reload, así que ahí ni reinicio ni rebuild hacen falta por archivo
editado -- ver [`web/README.md`](web/README.md) para cómo forzar cada
pantalla del dashboard sin backend.

### Por qué no está esto en producción

`docker-compose.override.yml` es solo para desarrollo local — está pensado
para correr directo sobre el código fuente. En la Pi, el despliegue debe usar
la imagen prebuilt de `linux/arm64` (ver el flujo de `buildx` en
`CLAUDE.md`), no un bind mount del árbol fuente. No copiar ese archivo al
despliegue de producción.

## Redesplegar después de un commit en `api/` o `web/`

**Un commit no basta.** A diferencia de `daemon` (bind mount + `restart` en
dev, ver arriba), `api/` y `web/` corren desde una imagen construida una
sola vez -- si corrés `docker compose -f infra/docker-compose.yml up -d`
(sin el override de dev, que es como corre la Pi real), el contenedor sigue
sirviendo el código de cuando se hizo el último `build`, sin importar
cuántos commits se hagan después. Ya pasó tres veces perseguir un bug real
que resultó ser una imagen vieja (gazetteer, `reprocess.py`, y el loop de
render de `useAvisoMachine` que motivó esta sección) -- en el último caso,
el fix llevaba dos horas commiteado mientras el contenedor seguía sirviendo
la versión rota.

```bash
infra/deploy.sh          # detecta qué servicio(s) cambiaron desde su último
                          # deploy (commit más reciente que toca esa carpeta
                          # vs. fecha de creación del contenedor) y solo
                          # reconstruye esos
infra/deploy.sh web      # fuerza un servicio puntual
infra/deploy.sh --all    # reconstruye daemon, api y web sin importar fecha
```

El script también verifica el resultado: después de levantar `api`/`web`
hace `curl` a su endpoint de versión y compara contra el commit que
debería haber quedado corriendo, en vez de asumir que "no hubo errores de
Docker" significa "quedó lo que yo creo que quedó".

### Verificar qué está corriendo, sin `deploy.sh`

Cada contenedor expone el commit que tiene adentro (horneado en build time,
no leído en runtime -- ver `api/Dockerfile`, `daemon/Dockerfile`,
`web/Dockerfile`):

```bash
curl http://localhost:8000/api/version      # {"git_sha": "...", "built_at": "..."}
curl http://localhost:3000/version.json     # ídem, para el contenedor web
docker exec infra-daemon-1 env | grep GIT_SHA  # el daemon no tiene HTTP propio
```

`web/` además muestra su propio commit en una esquina del dashboard (texto
chico, opacidad baja, no interactivo -- pensado para confirmarlo de un
vistazo parado frente a la tablet, no para el uso normal del panel).

Si construís las imágenes a mano (sin `deploy.sh`) y te falta pasar
`GIT_SHA`/`BUILT_AT` como `--build-arg`, todo esto cae en `"unknown"` en vez
de fallar el build -- una señal más de que ese contenedor no pasó por el
flujo de deploy real.
