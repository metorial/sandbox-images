FROM node:24-bookworm-slim

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip  \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright NODE_PATH=/opt/browser/node_modules
COPY package.json package-lock.json /opt/browser/
RUN cd /opt/browser \
    && npm ci --ignore-scripts \
    && ./node_modules/.bin/playwright install --with-deps chromium \
    && npm cache clean --force \
    && rm -rf /root/.npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*
COPY smoke-test.cjs /opt/sandbox/smoke-test.cjs

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
