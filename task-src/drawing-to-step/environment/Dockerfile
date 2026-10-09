FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv libgl1 libglu1-mesa libxrender1 libxext6 libglib2.0-0 libfontconfig1 libxcursor1 libxft2 libxinerama1 \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/cad && /opt/cad/bin/pip install --no-cache-dir --default-timeout=120 --retries=10 cadquery==2.8.0 ezdxf==1.4.4
ENV PATH=/opt/cad/bin:$PATH

WORKDIR /app
COPY data/drawings/ /app/drawings/
RUN mkdir -p /app/models
