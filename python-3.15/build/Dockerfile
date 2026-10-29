FROM python:3.15-slim-bookworm

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/log/* /tmp/* /var/tmp/*

ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
