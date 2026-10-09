FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /tmp/whl && cd /tmp/whl \
    && for i in $(seq 200); do curl -fL --speed-limit 2000 --speed-time 20 -C - -o torch-2.6.0+cpu-cp312-cp312-linux_x86_64.whl \
       "https://download-r2.pytorch.org/whl/cpu/torch-2.6.0%2Bcpu-cp312-cp312-linux_x86_64.whl" && break; sleep 5; done \
    && for i in $(seq 10); do pip install --no-cache-dir --default-timeout=600 --retries 20 filelock==3.18.0 \
       typing-extensions==4.14.1 sympy==1.13.1 mpmath==1.3.0 networkx==3.4.2 jinja2==3.1.6 MarkupSafe==3.0.2 \
       fsspec==2025.5.1 setuptools==80.9.0 && break; sleep 5; done \
    && pip install --no-cache-dir --no-index --find-links /tmp/whl torch==2.6.0 \
    && python -c "import torch" && rm -rf /tmp/whl
RUN for i in $(seq 10); do pip install --no-cache-dir --default-timeout=600 --retries 20 numpy==2.2.6 safetensors==0.5.3 \
       tokenizers==0.21.1 tqdm==4.67.1 pyyaml==6.0.2 requests==2.32.3 && break; sleep 5; done \
    && python -c "import numpy, safetensors, tokenizers, yaml, tqdm, requests"
RUN for i in $(seq 50); do curl -fsSL --speed-limit 2000 --speed-time 20 -o /tmp/llama.tgz \
       https://github.com/ggml-org/llama.cpp/archive/refs/tags/b10964.tar.gz && break; rm -f /tmp/llama.tgz; sleep 5; done \
    && mkdir -p /opt/llama.cpp && tar xzf /tmp/llama.tgz -C /opt/llama.cpp --strip-components=1 && rm /tmp/llama.tgz \
    && cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF \
       -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_APP=OFF -DBUILD_SHARED_LIBS=ON \
    && cmake --build /opt/llama.cpp/build -j 2 --target llama-tokenize llama-eval-callback llama-simple llama-gguf \
    && rm -rf /opt/llama.cpp/build/CMakeFiles /opt/llama.cpp/build/*/CMakeFiles
ENV PATH="/opt/llama.cpp/build/bin:${PATH}" \
    PYTHONPATH="/opt/llama.cpp/gguf-py" \
    LD_LIBRARY_PATH="/opt/llama.cpp/build/bin"

COPY tools/kestrel_logits.cpp /opt/kestrel-eval/kestrel_logits.cpp
RUN g++ -O2 -std=c++17 -I/opt/llama.cpp/include -I/opt/llama.cpp/ggml/include \
        /opt/kestrel-eval/kestrel_logits.cpp -o /usr/local/bin/kestrel-logits \
        -L/opt/llama.cpp/build/bin -lllama -lggml -lggml-base -Wl,-rpath,/opt/llama.cpp/build/bin

COPY kestrel/ /app/kestrel/
WORKDIR /app
