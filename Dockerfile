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
    && rm -rf /var/lib/apt/lists/*

# Set up build directories
WORKDIR /usr/src

# 1. Build & Install ION-DTN (from local source)
COPY ION-DTN ./ION-DTN
WORKDIR /usr/src/ION-DTN
RUN ./configure --enable-bpv7 && make -j$(nproc) && make install && ldconfig

# 2. Build & Install pyion (from local source)
WORKDIR /usr/src
COPY pyion ./pyion
WORKDIR /usr/src/pyion
RUN pip3 install .

# 3. Install EmION (from local source)
WORKDIR /usr/src/emion
COPY . .
RUN pip3 install -e ".[dashboard]"

# Environment setup
ENV PATH="/usr/local/bin:${PATH}"
EXPOSE 8420

# Default command: Start Mission Control
ENTRYPOINT ["emion"]
CMD ["dashboard", "--port", "8420"]
