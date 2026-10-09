FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv libgl1 libglu1-mesa libxrender1 libxext6 libglib2.0-0 libfontconfig1 libxcursor1 libxft2 libxinerama1 \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/cad && /opt/cad/bin/pip install --no-cache-dir --default-timeout=120 --retries=10 cadquery==2.8.0 ezdxf==1.4.4
ENV PATH=/opt/cad/bin:$PATH
RUN pip install --no-cache-dir --default-timeout=120 --retries=10 pytest==9.1.1 pytest-json-ctrf==0.5.2

COPY . /tests/

RUN mkdir -p /app/models
RUN mkdir -p /logs/verifier
