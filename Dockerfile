ARG UBUNTU_VERSION=18.04
ARG BUILDER_PLATFORM=linux/amd64
ARG LINUX001_REPO=https://github.com/mariuz/linux-0.01.git
ARG LINUX001_REF=b0d17028228c83d68cc68646c25bd664a1ece50f

FROM --platform=${BUILDER_PLATFORM} ubuntu:${UBUNTU_VERSION} AS builder
ARG DEBIAN_FRONTEND=noninteractive
ARG LINUX001_REPO
ARG LINUX001_REF

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bin86 \
        build-essential \
        ca-certificates \
        gcc \
        gcc-multilib \
        git \
        unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git init linux-0.01 \
    && cd linux-0.01 \
    && git remote add origin "${LINUX001_REPO}" \
    && git fetch --depth 1 origin "${LINUX001_REF}" \
    && git checkout --detach FETCH_HEAD

WORKDIR /src/linux-0.01
RUN make clean \
    && make \
    && unzip -o hd_oldlinux.img.zip \
    && install -d /opt/linux-0.01 \
    && install -m 0644 Image /opt/linux-0.01/Image \
    && cp Image /opt/linux-0.01/Image.1440 \
    && truncate -s 1474560 /opt/linux-0.01/Image.1440 \
    && install -m 0644 hd_oldlinux.img /opt/linux-0.01/hd_oldlinux.img \
    && git rev-parse HEAD > /opt/linux-0.01/source-commit.txt \
    && printf '%s\n' "${LINUX001_REPO}" > /opt/linux-0.01/source-repo.txt

FROM --platform=$BUILDPLATFORM ubuntu:${UBUNTU_VERSION} AS runtime
ARG DEBIAN_FRONTEND=noninteractive

# Keep the Linux 0.01 build on amd64, but let the runtime QEMU userspace match
# the local builder host so Apple Silicon does not have to execute QEMU through
# Rosetta when the image was produced with `buildx --platform linux/amd64`.

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        qemu-system-x86 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/linux-0.01 /opt/linux-0.01
COPY container/run-linux-0.01.sh /usr/local/bin/run-linux-0.01
RUN chmod +x /usr/local/bin/run-linux-0.01

ENV TERM=xterm \
    LANG=C.UTF-8

LABEL org.opencontainers.image.title="linux-0.01" \
      org.opencontainers.image.description="Single-image Linux 0.01 shell boot via QEMU" \
      org.opencontainers.image.source="https://github.com/mariuz/linux-0.01" \
      org.opencontainers.image.licenses="Unknown"

ENTRYPOINT ["/usr/local/bin/run-linux-0.01"]
