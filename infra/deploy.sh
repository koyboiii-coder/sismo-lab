#!/usr/bin/env bash
# Rebuild + redeploy exactly the services whose source changed since the
# container currently running them -- so we stop losing sessions to bugs
# that turn out to be a stale image (three times now: gazetteer,
# reprocess.py, and the useAvisoMachine render loop -- see CLAUDE.md
# decisions log). `docker compose restart` does NOT pick up source changes
# for daemon/api/web -- images are built once, not bind-mounted, outside
# of docker-compose.override.yml's dev-only setup (see ../README.md).
#
# Usage:
#   infra/deploy.sh              # detect + redeploy whatever changed
#   infra/deploy.sh web api      # force rebuild+redeploy specific services
#   infra/deploy.sh --all        # rebuild+redeploy daemon, api, web
#
# After redeploying api/web, curls GET /api/version and /version.json to
# confirm the commit actually running matches the one just built -- if it
# doesn't, something cached wrong and printing "success" would be a lie.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

COMPOSE=(docker compose -f infra/docker-compose.yml)
ALL_SERVICES=(daemon api web)

GIT_SHA="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  GIT_SHA="${GIT_SHA}-dirty"
  echo "aviso: hay cambios sin commitear -- se van a construir igual, pero" >&2
  echo "       la versión reportada (${GIT_SHA}) no corresponde a ningún commit real." >&2
fi
export GIT_SHA
export BUILT_AT
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

needs_rebuild() {
  local svc="$1"
  local container
  container="$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null)"
  if [[ -z "$container" ]]; then
    echo yes # nunca se levantó -- constrúyelo
    return
  fi
  local created_epoch last_commit_epoch
  created_epoch="$(date -d "$(docker inspect --format '{{.Created}}' "$container")" +%s)"
  last_commit_epoch="$(git log -1 --format=%ct -- "$svc" 2>/dev/null || echo 0)"
  if [[ -n "$(git status --porcelain -- "$svc")" ]]; then
    echo yes # cambios sin commitear en esa carpeta
  elif (( last_commit_epoch > created_epoch )); then
    echo yes # el commit más reciente que toca esa carpeta es posterior al deploy actual
  else
    echo no
  fi
}

targets=()
if [[ "${1:-}" == "--all" ]]; then
  targets=("${ALL_SERVICES[@]}")
elif [[ $# -gt 0 ]]; then
  targets=("$@")
else
  for svc in "${ALL_SERVICES[@]}"; do
    if [[ "$(needs_rebuild "$svc")" == "yes" ]]; then
      targets+=("$svc")
    fi
  done
fi

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "Nada que redesplegar -- todos los contenedores son más nuevos que su último commit."
  exit 0
fi

echo "Redesplegando: ${targets[*]} (GIT_SHA=$GIT_SHA)"
"${COMPOSE[@]}" build "${targets[@]}"
"${COMPOSE[@]}" up -d "${targets[@]}"

sleep 2
status=0
for svc in "${targets[@]}"; do
  deployed=""
  case "$svc" in
    api) deployed="$(curl -fsS --max-time 5 http://localhost:8000/api/version 2>/dev/null | grep -o '"git_sha":"[^"]*"' | cut -d'"' -f4 || true)" ;;
    web) deployed="$(curl -fsS --max-time 5 http://localhost:3000/version.json 2>/dev/null | grep -o '"git_sha":"[^"]*"' | cut -d'"' -f4 || true)" ;;
  esac
  if [[ -z "$deployed" ]]; then
    continue # daemon no expone versión por HTTP -- ver daemon/Dockerfile
  fi
  if [[ "$deployed" == "$GIT_SHA" ]]; then
    echo "OK  $svc corriendo $deployed"
  else
    echo "MAL $svc corriendo '$deployed', se esperaba '$GIT_SHA' -- revisar" >&2
    status=1
  fi
done

exit $status
