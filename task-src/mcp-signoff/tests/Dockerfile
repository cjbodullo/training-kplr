FROM debian:bookworm-slim AS sta
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake tcl-dev swig bison flex libfl-dev libeigen3-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY data/cudd-3.0.0.tar.gz data/opensta-aa1e537.tar.gz /src/
RUN cd /src && tar xzf cudd-3.0.0.tar.gz && cd cudd-3.0.0 \
    && ./configure --prefix=/opt/cudd && make -j4 && make install
RUN cd /src && tar xzf opensta-aa1e537.tar.gz \
    && mv OpenSTA-aa1e53738cea47402012d2be8be705c29a9a49f1 OpenSTA \
    && mkdir OpenSTA/build && cd OpenSTA/build \
    && cmake -DCUDD_DIR=/opt/cudd -DCMAKE_INSTALL_PREFIX=/opt/sta .. \
    && make -j4 && make install \
    && gunzip -c /src/OpenSTA/examples/sky130hd_tt.lib.gz > /opt/sta/sky130hd_tt.lib

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends tcl8.6 zlib1g \
    && rm -rf /var/lib/apt/lists/*
RUN pip install pytest==9.1.1 pytest-json-ctrf==0.5.2
COPY --from=sta /opt/sta/bin /usr/local/bin
COPY --from=sta /opt/sta/sky130hd_tt.lib /opt/sta/sky130hd_tt.lib
COPY . /tests/
RUN rm -rf /tests/data \
    && mkdir -p /opt/design && cp /tests/design/cicd.v /tests/design/base.sdc /opt/design/ \
    && chmod 755 /opt/design && chmod 644 /opt/design/* \
    && chmod -R go-rwx /tests && chmod 600 /tests/expected.json
RUN mkdir -p /app
