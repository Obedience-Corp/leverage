FROM golang:1.26-trixie AS scc
RUN go install github.com/boyter/scc/v3@v3.7.0
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash git curl ca-certificates librsvg2-bin && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pyyaml && useradd -m tester
COPY --from=scc /go/bin/scc /usr/local/bin/scc
USER tester
WORKDIR /src
ENV LEVERAGE_TEST_ISOLATED=1
