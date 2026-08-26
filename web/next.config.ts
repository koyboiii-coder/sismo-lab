import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen liviana para la Pi (CLAUDE.md regla 5): el runner del Dockerfile
  // solo copia .next/standalone + .next/static + public, no node_modules
  // completo.
  output: "standalone",
  // El navegador de la tablet solo habla con este origen (puerto 3000).
  // El proxy hacia la API dentro de la red de Docker vive en
  // src/app/api/[...path]/route.ts, no acá: `rewrites()` resuelve sus
  // destinos en build time, así que un `API_INTERNAL_URL` que solo existe
  // en runtime (docker-compose environment, no el Dockerfile build) quedaba
  // ignorado a favor del default -- el Route Handler lee la variable en
  // cada request en vez de hornearla en la imagen.
};

export default nextConfig;
