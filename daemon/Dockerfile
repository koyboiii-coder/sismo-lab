FROM python:3.11-slim

WORKDIR /app

# Same as api/Dockerfile: baked in by infra/deploy.sh, readable via
# `docker exec infra-daemon-1 env | grep GIT_SHA` -- the daemon has no HTTP
# endpoint of its own to serve this through.
ARG GIT_SHA=unknown
ARG BUILT_AT=unknown
ENV GIT_SHA=$GIT_SHA
ENV BUILT_AT=$BUILT_AT

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
