# linux-0.01-oneclick

`linux-0.01-oneclick` is a single-image Linux 0.01 boot environment packaged as an OCI/Docker repository. The repository builds a Linux 0.01-derived kernel from a pinned [`mariuz/linux-0.01`](https://github.com/mariuz/linux-0.01) commit inside Ubuntu 18.04 with GCC 7 and `bin86`, expands the kernel into a 1.44 MB floppy image, bundles the upstream root disk image, and ships a runtime container whose entrypoint launches QEMU directly into the guest shell.

## Repository scope

This repository contains:

- a multi-stage `Dockerfile` that reproduces the build inside Ubuntu 18.04
- a runtime image with `qemu-system-i386` as the execution path
- an entrypoint script that boots the guest in curses mode
- a strict PTY-based verification script that proves the shell prompt is interactive
- recorded source provenance for the pinned upstream repository and commit

## Runtime contract

The repository exposes a single interactive container runtime and supports both a published instant-demo image and local rebuilds.

### Instant demo via published image

Published image reference:

```text
docker.io/klee100/linux-0.01-oneclick:latest
```

The published image has been validated with the repository PTY-based verifier against the Docker Hub reference above.

Docker:

```bash
docker run --rm -it docker.io/klee100/linux-0.01-oneclick:latest
```

Podman:

```bash
podman run --rm -it docker.io/klee100/linux-0.01-oneclick:latest
```

### Local build

Docker:

```bash
docker build -t linux-0.01 .
docker run --rm -it linux-0.01
```

Podman:

```bash
podman build -t linux-0.01 .
podman run --rm -it linux-0.01
```

## Build pipeline

The build stage performs the following steps:

1. fetch `mariuz/linux-0.01` at a pinned commit
2. build the kernel with GCC 7, multilib support, and `bin86`
3. unpack the upstream `hd_oldlinux.img`
4. copy the generated `Image` into a padded `Image.1440` floppy image
5. record the source repository and exact commit inside `/opt/linux-0.01`

The runtime stage installs only the QEMU userspace needed to boot the guest and copies in:

- `Image`
- `Image.1440`
- `hd_oldlinux.img`
- provenance files
- `container/run-linux-0.01.sh`

## Boot behavior

Container startup launches `qemu-system-i386` as the entrypoint. The runtime uses:

- `-display curses` for direct terminal interaction
- `-snapshot` to avoid mutating the packaged root disk
- a floppy drive for `Image.1440`
- an IDE hard disk for `hd_oldlinux.img`
- `-no-reboot`, `-net none`, `-monitor none`, `-serial none`, and `-parallel none` for a minimal boot path

A successful boot reaches the Linux shell prompt. Typical terminal output ends in a screen similar to:

```text
Partition table ok.
31279/40950 free blocks
13546/13664 free inodes
1498 buffers = 1533952 bytes buffer space
Ok.
#
```

## Strict verification

Strict verification is implemented in `scripts/verify_container.py`.

The verifier:

1. starts the container under a pseudo-terminal
2. waits for the guest `#` prompt
3. sends `/bin/ls /bin/sh`
4. confirms that `/bin/sh` appears in guest output
5. confirms that the shell prompt returns afterward
6. writes proof artifacts under `artifacts/verify/`

Verification dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

Verification commands:

Local image via Docker:

```bash
python3 scripts/verify_container.py --runtime docker --image linux-0.01:latest
```

Local image via Podman:

```bash
python3 scripts/verify_container.py --runtime podman --image linux-0.01:latest
```

Published image via Podman:

```bash
python3 scripts/verify_container.py --runtime podman --image docker.io/klee100/linux-0.01-oneclick:latest
```

Generated proof artifacts include:

- `raw.log`
- `transcript.txt`
- `final-screen.txt`
- `final-screen.png`
- `summary.txt`

## Authenticity caveat

This repository is a reproducible Linux 0.01 boot environment, but it is **not** a pristine 1991 Linux 0.01 system image. The pinned upstream tree is a Linux 0.01-derived fork that adds ELF support and hardcoded `uname` data. The repository target is reproducible boot-to-shell packaging, not historical byte-for-byte preservation.

## Source provenance

The Docker build pins the upstream source to:

- repository: `https://github.com/mariuz/linux-0.01.git`
- commit: `b0d17028228c83d68cc68646c25bd664a1ece50f`

The built runtime image records the same information at:

- `/opt/linux-0.01/source-repo.txt`
- `/opt/linux-0.01/source-commit.txt`

## Repository layout

```text
.
├── Dockerfile
├── Makefile
├── README.md
├── container/
│   └── run-linux-0.01.sh
├── requirements-dev.txt
└── scripts/
    └── verify_container.py
```

## Notes

- Interactive TTY mode is required because the runtime uses QEMU curses display.
- Detached container mode is not the intended execution model.
- Guest filesystem changes are intentionally discarded because the runtime uses QEMU `-snapshot`.
