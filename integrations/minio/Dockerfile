FROM golang:1.24.8-alpine AS binarios
ARG RELEASE=RELEASE.2025-10-15T17-29-55Z
ARG MC_RELEASE=RELEASE.2025-08-13T08-35-41Z
RUN go install "github.com/minio/minio@${RELEASE}" && \
    go install "github.com/minio/mc@${MC_RELEASE}"

FROM alpine:3.22
RUN apk add --no-cache ca-certificates && \
    addgroup -S -g 10001 minio && adduser -S -D -H -u 10001 -G minio minio && \
    mkdir -p /data && chown minio:minio /data
COPY --from=binarios /go/bin/minio /go/bin/mc /usr/local/bin/
USER minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
