FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake tcl-dev swig bison flex libfl-dev libeigen3-dev zlib1g-dev ca-certificates && rm -rf /var/lib/apt/lists/*
COPY cudd-3.0.0.tar.gz opensta-aa1e537.tar.gz /src/
RUN cd /src && tar xzf cudd-3.0.0.tar.gz && cd cudd-3.0.0 && ./configure --prefix=/opt/cudd && make -j8 && make install
RUN cd /src && tar xzf opensta-aa1e537.tar.gz && mv OpenSTA-aa1e53738cea47402012d2be8be705c29a9a49f1 OpenSTA && mkdir OpenSTA/build && cd OpenSTA/build && cmake -DCUDD_DIR=/opt/cudd -DCMAKE_INSTALL_PREFIX=/opt/sta .. && make -j8 && make install
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends yosys iverilog tcl8.6 zlib1g python3 && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/sta /opt/sta
COPY --from=build /src/OpenSTA/examples/sky130hd_tt.lib.gz /opt/sta/share/
ENV PATH=/opt/sta/bin:$PATH
