ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.2
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system packages first
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-yaml \
    py3-requests

# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust

# Test basic functionality
RUN echo "=== Testing basic pip functionality ===" && \
    pip3 --version && \
    pip3 list

# Install packages one by one to isolate failures
RUN echo "=== Installing pyserial ===" && \
    pip3 install --no-cache-dir --verbose pyserial==3.5

RUN echo "=== Installing aiohttp ===" && \
    pip3 install --no-cache-dir --verbose aiohttp==3.8.5

RUN echo "=== Installing aiofiles ===" && \
    pip3 install --no-cache-dir --verbose aiofiles==23.1.0

RUN echo "=== Installing websockets ===" && \
    pip3 install --no-cache-dir --verbose websockets==11.0.3

RUN echo "=== Installing pynmea2 ===" && \
    pip3 install --no-cache-dir --verbose pynmea2==1.19.0

RUN echo "=== Installing pyubx2 ===" && \
    pip3 install --no-cache-dir --verbose pyubx2==1.2.37

# Clean up build dependencies
RUN apk del .build-deps

# Python 3 HTTP Server serves the current working dir
# So let's set it to our add-on persistent data directory.
WORKDIR /data

# Copy root filesystem
COPY rootfs /

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
