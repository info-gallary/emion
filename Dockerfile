FROM ubuntu:22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install core build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    git \
    python3 \
    python3-dev \
    python3-pip \
    wget \
    cmake \
    libexpat1-dev \
    autoconf \
    automake \
    libtool \
    && rm -rf /var/lib/apt/lists/*

# Install native CORE-GUI (Common Open Research Emulator) and Networking Tools
RUN apt-get update && apt-get install -y \
    iproute2 ethtool tk python3-tk tcl net-tools tcpdump python3-venv \
    && wget -q https://github.com/coreemu/core/releases/download/release-9.0.3/core_9.0.3_amd64.deb \
    && apt-get install -y ./core_9.0.3_amd64.deb \
    && rm core_9.0.3_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Set up build directories
WORKDIR /usr/src

# 1. Build & Install ION-DTN (from local source)
COPY ION-DTN ./ION-DTN
WORKDIR /usr/src/ION-DTN
# Run autoreconf to handle any timestamp issues with Makefile.in/configure
RUN autoreconf -fi && ./configure --enable-bpv7 && make -j$(nproc) && make install && ldconfig

# 2. Install EmION (from local source)
# This will automatically build the internal pyion C-bindings
# against the ION-DTN headers/libs installed above.
WORKDIR /usr/src/emion
COPY . .
RUN pip3 install ".[dashboard]"

# Environment setup
ENV ION_HOME=/usr/local
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
ENV PATH="/usr/local/bin:${PATH}"
EXPOSE 8420

# Default command: Start Mission Control
ENTRYPOINT ["emion"]
CMD ["dashboard", "--port", "8420"]
