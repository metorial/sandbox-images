FROM gradle:9.1.0-jdk25 AS gradle
FROM maven:3.9-eclipse-temurin-25

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip  \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

COPY --from=gradle /opt/gradle /opt/gradle
ENV GRADLE_HOME=/opt/gradle
ENV PATH="/opt/gradle/bin:${PATH}"

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
