FROM alpine:3.14

# Install dependencies
RUN apk add --no-cache \
    build-base \
    openssl-dev \
    git \
    python3 \
    python3-dev \
    py3-pip \
    linux-headers \
    wget

# Clone and install ION-DTN
WORKDIR /usr/src
RUN git clone --branch ion-open-source-4.1.2 https://github.com/nasa-jpl/ION-DTN.git ion-dtn
WORKDIR /usr/src/ion-dtn
RUN ./configure --enable-bpv7 && make && make install

# Clone and install pyion
WORKDIR /usr/src
RUN git clone --branch v4.1.2 https://github.com/nasa-jpl/pyion.git pyion
WORKDIR /usr/src/pyion

# Set environment variables for pyion installation
ENV ION_HOME=/usr/src/ion-dtn
ENV PYION_BP_VERSION=BPv7

# Install pyion
RUN pip3 install .

# Setup workspace
WORKDIR /workspace
