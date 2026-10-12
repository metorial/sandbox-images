FROM composer:2 AS composer
FROM php:8.5-cli-bookworm

USER root
ARG SOURCE_DATE_EPOCH=0

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash ca-certificates curl git openssh-client build-essential procps unzip libicu-dev libonig-dev libpq-dev libsqlite3-dev libzip-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/cache/ldconfig/aux-cache /var/cache/fontconfig/* /var/log/* /tmp/* /var/tmp/*

COPY --from=composer /usr/bin/composer /usr/local/bin/composer
RUN docker-php-ext-install -j2 intl mbstring pdo_mysql pdo_pgsql pdo_sqlite zip \
    && if ! php -r 'exit(extension_loaded("Zend OPcache") ? 0 : 1);'; then docker-php-ext-install -j2 opcache; fi \
    && rm -rf /usr/src/php /tmp/* /var/tmp/*

ENV LANG=C.UTF-8

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
