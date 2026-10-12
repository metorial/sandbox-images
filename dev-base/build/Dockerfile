FROM ghcr.io/astral-sh/uv:0.10.0 AS uv
FROM node:24-bookworm-slim AS node
FROM oven/bun:1.3-debian AS bun
FROM python:3.13-slim-bookworm

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip jq ripgrep sqlite3 pkg-config libssl-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

COPY --from=uv /uv /uvx /usr/local/bin/

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s bun /usr/local/bin/bunx \
    && npm install --global pnpm@12.11.2 typescript@7.0.2 \
    && npm cache clean --force \
    && rm -rf /root/.npm

ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
