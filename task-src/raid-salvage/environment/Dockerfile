FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends mdadm e2fsprogs gddrescue xz-utils && rm -rf /var/lib/apt/lists/*

# ddrescue images of the four tarn raid members, xz compressed for transport, with their mapfiles
COPY data/ /data/tarn/
RUN mkdir -p /app/out
WORKDIR /app
