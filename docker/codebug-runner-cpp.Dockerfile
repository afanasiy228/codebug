FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        coreutils \
        g++ \
        gcc \
        libc6-dev \
        make \
        time \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
