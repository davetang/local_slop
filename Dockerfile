# Ollama server with sensible defaults for a LAN-accessible deployment
# whose models live in a host-mounted directory.
#
# Built on top of the official image:
# https://hub.docker.com/r/ollama/ollama
#
# Pinned by digest for reproducible builds. This is the multi-arch index
# digest for the :latest tag, so Docker still resolves the correct
# platform (amd64/arm64) while the exact content stays locked. The :latest
# tag is kept only as a human-readable label; the digest is what's used.
#
# To refresh the pin to the current :latest:
#   docker buildx imagetools inspect ollama/ollama:latest   # copy top-level Digest
# or, if you have pulled it:
#   docker pull ollama/ollama:latest
#   docker inspect --format='{{index .RepoDigests 0}}' ollama/ollama:latest
FROM ollama/ollama:latest@sha256:f1a705f2bd113fb8d15f85f7c217f0dc5f6bebda6b0cc42b82c3ad165ffcb9dc

# OLLAMA_HOST=0.0.0.0 makes the server listen on all interfaces so it is
# reachable from other machines on the network (the port is published by
# docker-compose.yml). The other values are convenient defaults that can
# be overridden per-container via the environment / .env file.
ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_CONTEXT_LENGTH=8192 \
    OLLAMA_KEEP_ALIVE=5m

# Custom entrypoint: starts the server and optionally pre-pulls models.
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 11434

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
