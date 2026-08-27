FROM python:3.11-slim

WORKDIR /app

# Baked in at build time (infra/deploy.sh passes these as --build-arg), and
# exposed read-only via GET /api/version -- so a `curl` from anywhere can
# confirm which commit a running container actually has, instead of
# assuming it matches the source tree (see CLAUDE.md decisions log: a
# stale `web` image cost a full debugging session before this existed).
ARG GIT_SHA=unknown
ARG BUILT_AT=unknown
ENV GIT_SHA=$GIT_SHA
ENV BUILT_AT=$BUILT_AT

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
