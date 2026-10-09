FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv libgl1 libglu1-mesa libxrender1 libxext6 libglib2.0-0 libfontconfig1 libxcursor1 libxft2 libxinerama1 \
    && rm -rf /var/lib/apt/lists/*
# big wheels (cadquery-ocp, casadi): retry, and let pip's cache keep the wheels already fetched
RUN python3 -m venv /opt/cad \
    && for i in $(seq 1 20); do /opt/cad/bin/pip install --default-timeout=120 --retries=10 cadquery==2.8.0 && break; sleep 5; done \
    && /opt/cad/bin/python -c "import cadquery" \
    && rm -rf /root/.cache/pip
ENV PATH=/opt/cad/bin:$PATH
RUN pip install --no-cache-dir --default-timeout=120 --retries=10 pytest==9.1.1 pytest-json-ctrf==0.5.2

COPY . /tests/

RUN mkdir -p /app/models
RUN mkdir -p /logs/verifier
