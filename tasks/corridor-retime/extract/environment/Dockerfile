FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive TZ=Europe/London SUMO_HOME=/usr/share/sumo

RUN apt-get update && apt-get install -y --no-install-recommends \
        sumo sumo-tools python3 python3-numpy python3-pandas python3-scipy \
        less ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY data/model/ /app/model/
COPY data/utc/ /app/utc/
COPY data/docs/ /app/docs/
