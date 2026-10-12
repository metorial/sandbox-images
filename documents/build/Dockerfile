FROM ghcr.io/astral-sh/uv:0.10.0 AS uv
FROM python:3.13-slim-bookworm

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip libreoffice-writer libreoffice-calc libreoffice-impress poppler-utils tesseract-ocr tesseract-ocr-eng fonts-dejavu fonts-liberation fonts-noto-core \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

COPY --from=uv /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /opt/sandbox/requirements.txt
RUN uv pip install --system --no-cache --only-binary=:all: -r /opt/sandbox/requirements.txt

COPY smoke-test.py /opt/sandbox/smoke-test.py

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
