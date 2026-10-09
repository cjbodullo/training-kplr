FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends mono-devel ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY Prog.cs .
RUN mcs -out:app.exe Prog.cs && echo "=== RUN ===" && mono app.exe && echo "=== MONODIS present ===" && which monodis ikdasm 2>/dev/null; monodis app.exe 2>/dev/null | grep -iE 'GetType|Invoke|ldstr' | head
