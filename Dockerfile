ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.2
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Step 1: Install core Python packages (should always work)
RUN apk add --no-cache python3 py3-pip

# Step 2: Test basic Alpine package installation
RUN echo "=== Testing core Alpine packages ===" && \
    apk add --no-cache py3-yaml py3-requests

# Step 3: Test potentially problematic Alpine packages
RUN echo "=== Testing py3-aiohttp ===" && \
    apk search py3-aiohttp && \
    apk add --no-cache py3-aiohttp

RUN echo "=== Testing py3-pyserial ===" && \
    apk search py3-pyserial && \
    apk add --no-cache py3-pyserial

# Step 4: Install build dependencies
RUN echo "=== Installing build dependencies ===" && \
    apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev

# Step 5: Test pip functionality
RUN echo "=== Testing pip ===" && \
    pip3 --version && \
    pip3 list

# Step 6: Install packages one by one
RUN echo "=== Installing aiofiles ===" && \
    pip3 install --no-cache-dir aiofiles==23.1.0

RUN echo "=== Installing websockets ===" && \
    pip3 install --no-cache-dir websockets==11.0.3

RUN echo "=== Installing pynmea2 ===" && \
    pip3 install --no-cache-dir pynmea2==1.19.0

RUN echo "=== Installing pyubx2 ===" && \
    pip3 install --no-cache-dir pyubx2==1.2.37

# Step 7: Clean up
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
