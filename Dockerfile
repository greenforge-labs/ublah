ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:14.0.2
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install packages
RUN apk add --no-cache \
    python3=~3.11 \
    py3-pip=~23.1 \
    py3-setuptools=~67.7 \
    py3-wheel=~0.40

# Python 3 HTTP Server serves the current working dir
# So let's set it to our add-on persistent data directory.
WORKDIR /data

# Copy Python requirements
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

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
