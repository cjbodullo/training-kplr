FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive TZ=Europe/London

RUN apt-get update && apt-get install -y --no-install-recommends \
        asterisk asterisk-doc python3 python3-numpy python3-scipy python3-pandas \
        gcc libc6-dev sqlite3 less ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY data/pbx/ /app/pbx/
COPY data/forecast/ /app/forecast/
