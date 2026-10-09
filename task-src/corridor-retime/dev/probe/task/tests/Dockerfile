FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive SUMO_HOME=/usr/share/sumo

RUN apt-get update && apt-get install -y --no-install-recommends \
        sumo python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages pytest==9.1.1 pytest-json-ctrf==0.5.2

COPY . /tests/

RUN mkdir -p /app /logs/verifier
