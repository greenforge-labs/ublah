ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.2
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install packages - use Alpine packages where possible to avoid compilation issues
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-setuptools \
    py3-wheel \
    py3-pyserial \
    py3-requests \
    py3-aiohttp \
    py3-yaml \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev

# Python 3 HTTP Server serves the current working dir
# So let's set it to our add-on persistent data directory.
WORKDIR /data

# Copy Python requirements
COPY requirements.txt /tmp/

# Test basic pip functionality with default version (skip upgrade)
RUN echo "=== Pip Status Check ===" && \
    which pip3 && \
    pip3 --version && \
    python3 -m pip --version

# Test pip list separately
RUN echo "=== Testing pip list ===" && \
    pip3 list

# Test PyPI connectivity separately  
RUN echo "=== Testing PyPI access ===" && \
    pip3 --timeout=10 --index-url https://pypi.org/simple/ --trusted-host pypi.org list || echo "PyPI access failed"

# Try installing the most basic package possible
RUN echo "=== Testing minimal package install ===" && \
    pip3 install --no-cache-dir --timeout=30 --verbose setuptools

# Try installing packages with default pip (no upgrade)
RUN echo "=== Testing package install with default pip ===" && \
    pip3 install --no-cache-dir pyserial==3.5 && \
    echo "=== pyserial successful ==="

# Install each package individually with verbose output to identify failures
RUN echo "=== Installing pynmea2 ===" && \
    pip3 install --no-cache-dir --verbose pynmea2==1.19.0 && \
    echo "=== Installing pyubx2 ===" && \
    pip3 install --no-cache-dir --verbose pyubx2==1.2.37 && \
    echo "=== Installing aiohttp ===" && \
    pip3 install --no-cache-dir --verbose aiohttp==3.8.5 && \
    echo "=== Installing aiofiles ===" && \
    pip3 install --no-cache-dir --verbose aiofiles==23.1.0 && \
    echo "=== Installing pyyaml ===" && \
    pip3 install --no-cache-dir --verbose pyyaml==6.0.1 && \
    echo "=== Installing websockets ===" && \
    pip3 install --no-cache-dir --verbose websockets==11.0.3 && \
    echo "=== All packages installed successfully ==="

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
