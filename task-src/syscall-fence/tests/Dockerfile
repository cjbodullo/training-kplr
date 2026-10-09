FROM python:3.13-slim-bookworm

# verifier tooling, all pre-installed here (test.sh installs nothing at verify time):
#   gcc + libc headers to compile the sealed target and helper,
#   pytest + the ctrf reporter for the reward contract.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install pytest==9.1.1 pytest-json-ctrf==0.5.2

# bake tests (target.c, helper.c, jobs, data) into the image
COPY . /tests/

# compile the sealed target and the exec-tamper helper at build time
RUN gcc -O2 -o /tests/target /tests/target.c \
    && gcc -O2 -o /tests/helper /tests/helper.c

# the agent's /app/filter.bpf is uploaded here; the target reads it from /app
RUN mkdir -p /app
