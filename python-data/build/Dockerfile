FROM ghcr.io/astral-sh/uv:0.10.0 AS uv
FROM python:3.13-slim-bookworm

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip  \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

COPY --from=uv /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /opt/sandbox/requirements.txt
RUN uv pip install --system --no-cache --only-binary=:all: -r /opt/sandbox/requirements.txt

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
