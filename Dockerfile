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
    py3-websockets \
    py3-serial \
    && apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust \
    && pip3 install --no-cache-dir \
    pynmea2==1.19.0 \
    pyubx2==1.2.37 \
    aiofiles==23.1.0 \
    && apk del .build-deps

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
RUN echo "=== Testing disk space and environment ===" && \
    df -h && \
    python3 -c "import tempfile; print('Temp dir:', tempfile.gettempdir())" && \
    ls -la /tmp/

# Try installing a tiny pure Python package instead of setuptools
RUN echo "=== Testing write permissions ===" && \
    python3 -c "import site; print('Site packages:', site.getsitepackages())" && \
    ls -la $(python3 -c "import site; print(site.getsitepackages()[0])") && \
    touch /tmp/test_write && rm /tmp/test_write && \
    echo "=== Write test passed ==="

# Capture full pip error output
RUN echo "=== Testing pip with full error output ===" && \
    pip3 install --no-cache-dir --no-deps --verbose --debug six 2>&1 || \
    (echo "=== Pip install failed, trying alternative approach ===" && \
     python3 -m pip install --no-cache-dir --no-deps --verbose six 2>&1)

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
