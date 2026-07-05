# Ollama

To run LLMs locally you can use [Ollama](https://ollama.com/download); installing and updating use the same command:

```console
curl -fsSL https://ollama.com/install.sh | sh
```

## Server

First change the systemd service.

```console
sudo EDITOR=vim systemctl edit ollama.service
```

Add:

```
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Reload and restart:

```console
sudo systemctl daemon-reload
sudo systemctl restart ollama

# check
ss -tlnp | grep 11434
```

To use another instance of Ollama running on the network.

```bash
export OLLAMA_HOST=http://192.168.1.50:11434

# when you're done
unset OLLAMA_HOST
```

# Docker

As an alternative to installing Ollama system-wide as a service (see [Server](#server) above), you can run it in a container. This keeps Ollama isolated from the host, stores models in a directory you control (so they are only downloaded once), and exposes the server to other machines on your local network.

The files for this setup live in this repository:

| File                 | Purpose                                                        |
| -                    | -                                                              |
| `Dockerfile`         | Builds the image from the official `ollama/ollama` image       |
| `docker-compose.yml` | Runs the server with the port, volume and environment set      |
| `entrypoint.sh`      | Starts the server and optionally pre-pulls models on start     |
| `.env`               | Configuration knobs (port, model directory, context length)    |
| `.dockerignore`      | Keeps the build context minimal (only `entrypoint.sh` is sent) |

## Requirements

- [Docker Engine](https://docs.docker.com/engine/install/) with the Docker Compose plugin.
- (Optional) For GPU acceleration, the NVIDIA driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html); then uncomment the `deploy:` block in `docker-compose.yml`.

## Usage

Run all `docker compose` commands from this repository's directory; Compose reads `docker-compose.yml` and `.env` from wherever it is invoked.

### Build and start

One command builds the image *and* starts the server; there is no separate run step:

```console
docker compose up -d --build
```

This does three things:

1. **Builds the image** from the `Dockerfile` and tags it `ollama-server:latest` (the `image:` name in `docker-compose.yml`). If the `Dockerfile` and `entrypoint.sh` have not changed since the last build, this is a fast no-op.
2. **Creates and starts a container** named `ollama` from that image, publishing the API on `OLLAMA_PORT` and bind-mounting `OLLAMA_DATA` for model storage.
3. **Returns immediately** because of `-d` (detached); the server keeps running in the background. Use the logs command below to watch it.

On later runs you can drop `--build` and just use `docker compose up -d`; the flag is only needed after editing the `Dockerfile` or `entrypoint.sh`, but keeping it is harmless. If the container is already running and nothing changed, `up -d` is a no-op.

Because `.env` sets `OLLAMA_PULL_MODELS=phi4:latest`, the first start also downloads `phi4` automatically; follow the logs to watch the progress.

### Check that it is running

```console
docker compose ps        # container status, health, and published port
docker compose logs -f   # follow the server logs (Ctrl-C stops following, not the server)
```

The container has a healthcheck (`ollama list` every 30 seconds), so `docker compose ps` shows `healthy` once the server is accepting requests.

### Work with models

The `ollama` CLI lives inside the container, so prefix commands with `docker compose exec ollama`; the first `ollama` is the Compose service name, and everything after it is the command run inside the container:

```console
docker compose exec ollama ollama pull phi4:latest   # download a model
docker compose exec ollama ollama run phi4:latest    # chat with a model interactively
docker compose exec ollama ollama list               # models downloaded to disk
docker compose exec ollama ollama ps                 # models currently loaded in memory
```

Models and all Ollama state are stored on the host in the directory set by `OLLAMA_DATA` in `.env` (`./ollama_data`), so they survive container restarts, rebuilds, and `docker compose down`, and are never re-downloaded.

### Stop, start, remove

```console
docker compose stop      # stop the server; the container is kept
docker compose start     # start the stopped container again
docker compose restart   # stop + start in one step
docker compose down      # stop and remove the container
```

`docker compose down` removes the container but keeps the image and your models, so `docker compose up -d` restores everything. The container is set to `restart: unless-stopped`, meaning it also comes back automatically after a reboot or Docker daemon restart, unless you stopped it yourself.

## Configuration

Edit `.env` to change the settings, then apply with `docker compose up -d` (add `--build` if you changed the `Dockerfile` or `entrypoint.sh`):

| Variable                | Value in `.env` | Description                                                    |
| -                       | -               | -                                                              |
| `OLLAMA_PORT`           | `11444`         | Host port the API is published on                              |
| `OLLAMA_DATA`           | `./ollama_data` | Host directory for models and Ollama state                     |
| `OLLAMA_CONTEXT_LENGTH` | `8192`          | Default context window                                         |
| `OLLAMA_KEEP_ALIVE`     | `5m`            | How long a model stays loaded in memory after the last request |
| `OLLAMA_PULL_MODELS`    | `phi4:latest`   | Space/comma separated models to pull automatically on start    |

If a variable is unset in `.env`, `docker-compose.yml` falls back to Ollama's standard port `11434` and pulls no models automatically.

For example, to also download `llama3.2` automatically on start:

```
OLLAMA_PULL_MODELS=phi4:latest llama3.2:latest
```

## Access from other computers

The server listens on `0.0.0.0` inside the container, and the host port set by `OLLAMA_PORT` in `.env` (`11444` in this repo) is published, so other machines on the same network can reach it at `http://<host-ip>:<port>`, where `<port>` is your `OLLAMA_PORT` and `<host-ip>` comes from `hostname -I` or `ip addr`. (Inside the container Ollama always listens on `11434`; only the published host port changes.) Confirm it is listening on your `OLLAMA_PORT`:

```console
ss -tlnp | grep 11444   # replace 11444 with your OLLAMA_PORT
```

On another machine, point Ollama-aware tools at it (again using your `OLLAMA_PORT`):

```bash
export OLLAMA_HOST=http://<host-ip>:<port>

# Aider uses a different variable:
export OLLAMA_API_BASE=http://<host-ip>:<port>
```

> **Note:** publishing the port exposes an unauthenticated API to your network. Only do this on a trusted LAN, and add a firewall rule (or bind the port to a specific interface) if needed.

# Claude Code

You can use local models with Claude Code (although I feel like this defeats the purpose of using local models):

```console
ollama launch claude --model phi4:latest
```

# Create Python virtual environment

[Virtual environments](https://docs.python.org/3/library/venv.html#creating-virtual-environments) are created by executing the venv module:

```console
python3 -m venv ./venv
```

Activate:

```console
source ./venv/bin/activate
```

# Install Aider

After activating the virtual environment, [install](https://aider.chat/#getting-started) using:

```console
python -m pip install aider-install
aider-install
```

This will install to `${HOME}/.local/bin`.

# Aider  + Ollama

[Aider](https://aider.chat/docs/llms/ollama.html) can connect to local Ollama models; port 11434 is the default.

```console
export OLLAMA_API_BASE=http://127.0.0.1:11434
```

> **Note:** if you are running Ollama with [Docker](#docker), point `OLLAMA_API_BASE` at your `OLLAMA_PORT` (`http://127.0.0.1:11444` with this repo's `.env`), set `OLLAMA_CONTEXT_LENGTH` in `.env` instead of editing the systemd service, and skip the `systemctl` steps below.

Stop service.

```console
sudo systemctl stop ollama
```

Edit service.

```console
sudo EDITOR="vim" systemctl edit ollama
```
```
[Service]
Environment="OLLAMA_CONTEXT_LENGTH=8192"
```

Start service.

```console
sudo systemctl start ollama
```

Pull a model.

```console
ollama pull phi4:latest
```

Check context length.

```console
ollama run phi4:latest
ollama ps
```
```
NAME           ID              SIZE     PROCESSOR    CONTEXT    UNTIL
phi4:latest    ac896e5b8b34    10 GB    100% CPU     8192       4 minutes from now
```

Exit after checking.

```
>>> /exit
```

Start `aider`.

```console
aider --model ollama_chat/phi4:latest
```

Type `/exit` to quit.

# Aider commands

| Command         | What It Does            |
| -               | -                       |
| `/add` filename | Add a file to the chat/ |
| `drop` filename | Remove a file from chat |
| `/ls`           | List files in chat      |
| `/run` command  | Run a shell command     |
| `/undo`         | Undo last change        |
| `/diff`         | Show changes made       |
| `/clear`        | Clear chat history      |
| `/exit`         | Exit aider              |

# Tips

See [Tips](https://aider.chat/docs/usage/tips.html).
