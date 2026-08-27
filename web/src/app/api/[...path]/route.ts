/**
 * Proxy a la API, evaluado en cada request en vez de en next.config.ts.
 *
 * next.config.ts hacía esto con `rewrites()`, pero esa función corre en
 * build time: `process.env.API_INTERNAL_URL` quedaba resuelto al valor por
 * defecto (`http://localhost:8000`) si la variable no estaba presente
 * durante `docker build` -- la imagen quedaba con esa URL horneada sin
 * importar qué ENV se le pasara después en runtime al contenedor. Leer la
 * variable acá, dentro del handler, hace que la imagen sirva para
 * cualquier entorno sin reconstruirla.
 *
 * No usar `fetch` con `cache`/Next Data Cache: cada respuesta (incluido
 * /api/stream, ver api/routers/stream.py) debe pasar a través tal cual,
 * sin que Next intente cachearla o interpretarla.
 */
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

// Cabeceras hop-by-hop o que Next/Node deben recalcular ellos mismos --
// copiarlas desde la respuesta de la API rompería el streaming (p. ej. un
// Content-Length de la respuesta original ya no aplica una vez que el
// cuerpo se retransmite en chunks) o no tiene sentido (Connection).
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "content-length",
  "content-encoding",
]);

function apiInternalUrl(): string {
  return process.env.API_INTERNAL_URL ?? "http://localhost:8000";
}

async function proxy(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = `${apiInternalUrl()}/api/${path.join("/")}${req.nextUrl.search}`;

  const hasBody = req.method !== "GET" && req.method !== "DELETE";
  const upstream = await fetch(target, {
    method: req.method,
    headers: {
      accept: req.headers.get("accept") ?? "*/*",
      ...(hasBody ? { "content-type": req.headers.get("content-type") ?? "application/json" } : {}),
    },
    body: hasBody ? await req.text() : undefined,
    signal: req.signal,
    cache: "no-store",
  });

  const headers = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  return new Response(upstream.body, { status: upstream.status, headers });
}

// GET (todo lo demás: eventos, salud, config, stream) y POST/DELETE
// (/api/notes -- ver CLAUDE.md "Arquitectura", único dominio con
// escritura directa desde la API) pasan por el mismo reenvío: el body y
// el método se retransmiten tal cual, sin interpretarlos acá.
export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
