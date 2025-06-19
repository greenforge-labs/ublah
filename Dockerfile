ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.2
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system packages and Python dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-yaml \
    py3-requests \
    py3-aiohttp \
    py3-pyserial \
    && apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    && pip3 install --no-cache-dir --break-system-packages \
    aiofiles \
    websockets \
    pynmea2 \
    pyubx2 \
    && apk del .build-deps

# Python 3 HTTP Server serves the current working dir
# So let's set it to our add-on persistent data directory.
WORKDIR /data

# Copy root filesystem
COPY rootfs /

# Make s6 service run script executable
RUN chmod +x /etc/services.d/ublox-gps/run

# Copy Python application
COPY ublox_gps /opt/ublox_gps

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Geoff Sokoll <geoff.s@greenforgelabs.com.au>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="HomeAssistant Community Add-ons" \
    org.opencontainers.image.authors="Geoff Sokoll <geoff.s@greenforgelabs.com.au>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/greenforge-labs/ublah" \
    org.opencontainers.image.source="https://github.com/greenforge-labs/ublah" \
    org.opencontainers.image.documentation="https://github.com/greenforge-labs/ublah/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
