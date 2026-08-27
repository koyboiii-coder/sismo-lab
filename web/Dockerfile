# Multi-stage: el runner final solo lleva .next/standalone + .next/static +
# public (CLAUDE.md regla 5, imagen liviana para la Pi), no node_modules
# completo ni el código fuente de web/.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Baked in by infra/deploy.sh. NEXT_PUBLIC_* has to be set before `next
# build` -- Next.js inlines it into the client bundle at build time, it
# can't be read from the container's runtime env like a normal server var.
# Also written to public/version.json (plain static file, no route handler
# needed) so `curl http://<pi>:3000/version.json` can confirm what's
# actually running without opening a browser -- see CLAUDE.md decisions
# log: a stale `web` image cost a full debugging session before this
# existed, because nothing surfaced which commit the container had.
ARG GIT_SHA=unknown
ARG BUILT_AT=unknown
ENV NEXT_PUBLIC_GIT_SHA=$GIT_SHA
ENV NEXT_PUBLIC_BUILT_AT=$BUILT_AT
RUN echo "{\"git_sha\":\"$GIT_SHA\",\"built_at\":\"$BUILT_AT\"}" > public/version.json
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
