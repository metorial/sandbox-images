FROM ubuntu:24.04

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/log/* /tmp/* /var/tmp/*

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
