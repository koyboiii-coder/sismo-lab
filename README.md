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
hoy solo monta `daemon/` (ver ese archivo si hace falta extenderlo).

### Por qué no está esto en producción

`docker-compose.override.yml` es solo para desarrollo local — está pensado
para correr directo sobre el código fuente. En la Pi, el despliegue debe usar
la imagen prebuilt de `linux/arm64` (ver el flujo de `buildx` en
`CLAUDE.md`), no un bind mount del árbol fuente. No copiar ese archivo al
despliegue de producción.
