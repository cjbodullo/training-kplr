FROM python:3.13-slim-bookworm

# everything the verifier needs is installed here; test.sh never installs anything
RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2

# bake the tests and the sealed truth into the image
COPY . /tests/

# parent dir of every declared artifact
RUN mkdir -p /app/out
