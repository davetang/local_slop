# Contents

- [Ollama](#ollama)
  - [Server](#server)
  - [Client on another machine](#client-on-another-machine)
- [Docker](#docker)
  - [Requirements](#requirements)
  - [Usage](#usage)
  - [Configuration](#configuration)
  - [Access from other computers](#access-from-other-computers)
- [Claude Code](#claude-code)
- [Create Python virtual environment](#create-python-virtual-environment)
- [Install Aider](#install-aider)
- [Choosing a local model](#choosing-a-local-model)
- [Aider + Ollama](#aider--ollama)
  - [The context-window gotcha](#the-context-window-gotcha)
  - [Run Aider](#run-aider)
- [Persisting Aider settings](#persisting-aider-settings)
- [Aider workflow and commands](#aider-workflow-and-commands)
- [Tuning Aider for local models](#tuning-aider-for-local-models)
- [Aider troubleshooting](#aider-troubleshooting)
- [Aider tips and further reading](#aider-tips-and-further-reading)
- [OpenCode + Ollama](#opencode--ollama)
  - [Install OpenCode](#install-opencode)
  - [Connect to the Docker Ollama server](#connect-to-the-docker-ollama-server)
  - [Usage](#usage-1)
  - [Privacy notes](#privacy-notes)
  - [OpenCode further reading](#opencode-further-reading)
- [llm + Ollama](#llm--ollama)
  - [Install](#install)
  - [Connect to the Docker Ollama server](#connect-to-the-docker-ollama-server-1)
  - [Usage](#usage-2)

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

## Client on another machine

Everything above sets up the machine that *serves* models. To drive that server from a second machine on the network you do not need a second Ollama server; you only need the `ollama` binary, which is an HTTP client for every subcommand except `serve`.

`OLLAMA_HOST` is overloaded and means two different things depending on which side reads it:

| Where it is read            | What it means          | Example                     |
| -                           | -                      | -                           |
| Server (`ollama serve`)     | Address to **bind** to | `0.0.0.0:11434`             |
| Client (`run`, `list`, ...) | Server to **talk to**  | `http://192.168.1.50:11434` |

### Install the client only

`install.sh` also creates and enables a systemd service, so the client machine would end up running an idle server it never uses. To install just the binary, pull it out of the release archive.

Releases now ship as zstd-compressed tarballs (the older `.tgz` assets no longer exist, so URLs ending in `.tgz` return 404). `bin/ollama` is the first member of the archive, so `tar --occurrence=1` extracts it and then exits, which aborts the download before any of the ~1.4 GB of GPU runners and support libraries transfer. In practice this fetches about 11 MB.

```console
sudo apt install zstd

cd "$(mktemp -d)"
curl -sL https://ollama.com/download/ollama-linux-amd64.tar.zst \
  | zstd -d \
  | tar -x --occurrence=1 bin/ollama

sudo install -m 755 bin/ollama /usr/local/bin/ollama
```

The result is a single 39 MB binary that needs nothing beyond the system C and C++ libraries: no service, no `ollama` user, and no `lib/ollama/` runner directory to clean up later. Re-running the same commands is the whole upgrade procedure.

Swap `amd64` for `arm64` on an ARM machine. To pin a version, append `?version=` to the URL, giving the number *without* a leading `v` (`?version=v0.32.0` redirects to a `vv0.32.0` path and 404s):

```console
curl -sL 'https://ollama.com/download/ollama-linux-amd64.tar.zst?version=0.32.0' | ...
```

`--occurrence` is GNU tar. On macOS the equivalent is `-q` (`--fast-read`), and the macOS asset is still a `.tgz` with a flat layout:

```console
curl -sL https://ollama.com/download/ollama-darwin.tgz | tar -xzq ollama
```

### Point it at the server

The CLI has no `--host` flag, so `OLLAMA_HOST` is the only way to redirect it. A full URL and a bare `host:port` both work:

```bash
export OLLAMA_HOST=http://192.168.1.50:11434

# when you're done
unset OLLAMA_HOST
```

Persist it in `~/.bashrc` if the machine always talks to the same server. Use whatever port the server publishes: `11434` for the systemd install above, or your `OLLAMA_PORT` (`11444` in this repo) for the Docker setup, see [Access from other computers](#access-from-other-computers).

```console
ollama list             # lists the server's models
ollama run llama3.1
```

If that fails, test the network path directly before suspecting the client:

```console
curl -s http://192.168.1.50:11434/api/tags
```

### Things to watch

- `ollama pull` downloads to the **server's** disk, not the client's; the client only sends the request. `ollama rm` likewise deletes from the server. Every management subcommand acts on the remote machine even though the prompt looks local.
- `ollama ps` shows what is loaded on the server, so the server's `OLLAMA_KEEP_ALIVE` governs what you see.
- Do not run `ollama serve` on the client. The bare binary starts a server and binds the port quite happily, but without `lib/ollama/` it has no inference runners and only fails once a model is actually requested.
- `ollama --version` reports the client and server versions and warns when they differ, so re-run the install command after upgrading the server.
- The API is unauthenticated and unencrypted. Keep it on a trusted LAN and firewall the port (`sudo ufw allow from 192.168.1.0/24 to any port 11434 proto tcp`), or bind the server to one interface (`Environment="OLLAMA_HOST=192.168.1.50:11434"` in the systemd drop-in above) instead of `0.0.0.0`.

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

[Aider](https://aider.chat/) is a terminal-based AI pair programmer: you add files to a chat, describe a change, and it edits the files and commits the result. It needs Python 3.8+ and git, and it must be run inside a git repository; Aider auto-commits every edit, so git history is your undo log.

After activating the virtual environment, [install](https://aider.chat/#getting-started) using:

```console
python -m pip install aider-install
aider-install
```

This will install to `${HOME}/.local/bin`. Verify the install:

```console
aider --version
```

> **Note:** `pipx install aider-chat` and `uv tool install --python python3.12 aider-chat` also work, but the `aider-install` route is the least fuss. Do not run bare `aider` until a model is configured (see below); without one it looks for a hosted-model API key and complains.

# Choosing a local model

Model quality is the single biggest lever on how usable a local coding assistant feels. A weak model produces broken diffs, forgets to finish edits, and ignores your abstractions; pick the strongest model your hardware can hold. As a rough rule of thumb for a quantised (Q4) model, budget a bit more memory than the download size: a 20 GB model wants around 24 GB of RAM or VRAM to run comfortably.

| Hardware (RAM/VRAM) | Suggested model       | `ollama pull` tag   | Notes                                                        |
| -                   | -                     | -                   | -                                                            |
| 24 GB+              | Qwen2.5-Coder 32B     | `qwen2.5-coder:32b` | Very strong general coding model; a proven default for Aider |
| 24 GB+              | Qwen3-Coder 30B (MoE) | `qwen3-coder:30b`   | Newer MoE model with a large context window                  |
| 16-24 GB            | Devstral Small 24B    | `devstral:24b`      | Purpose-built for agentic coding (multi-file edits)          |
| ~16 GB              | gpt-oss 20B           | `gpt-oss:20b`       | Good fit for tighter memory budgets                          |
| < 16 GB             | Qwen2.5-Coder 7B/14B  | `qwen2.5-coder:7b`  | Usable for small, surgical edits; expect more hand-holding   |

If you have the RAM, start with `qwen2.5-coder:32b` or `qwen3-coder:30b`; they are the most reliable inside Aider. For heavier multi-file work try `devstral:24b`. Prefer models tagged `-coder` or `-instruct`, which follow editing instructions better than base models.

> **Note:** the table reflects widely cited 2026 community rankings (linked under [Aider tips and further reading](#aider-tips-and-further-reading)). Like Aider's own [leaderboard](https://aider.chat/docs/leaderboards/edit.html), rankings are informative but not proof of fitness for *your* codebase; try a model and watch the diffs.

# Aider + Ollama

[Aider](https://aider.chat/docs/llms/ollama.html) can connect to local Ollama models: no API key, no per-token bill, and no code leaving your machine. The trade-off is that local models are weaker than frontier hosted models and need some tuning to behave well (see [Tuning Aider for local models](#tuning-aider-for-local-models)).

Two things make the connection: an environment variable telling Aider where the Ollama server is (port 11434 is the default for a native install), and a model name with the `ollama_chat/` prefix (see [Run Aider](#run-aider)).

```bash
export OLLAMA_API_BASE=http://127.0.0.1:11434
```

> **Note:** if you are running Ollama with [Docker](#docker), point `OLLAMA_API_BASE` at your `OLLAMA_PORT` (`http://127.0.0.1:11444` with this repo's `.env`), set `OLLAMA_CONTEXT_LENGTH` in `.env` instead of editing the systemd service, and skip the `systemctl` steps below.

## The context-window gotcha

This is the mistake that makes people give up on local Aider. Ollama defaults to a 2,048-token context window, which is tiny; worse, when a request exceeds the window Ollama does not error, it silently truncates the context. The model simply stops seeing part of your files or instructions, and you get baffling, half-finished edits with no warning. Set at least `8192`; go higher if your model and RAM allow.

The Docker setup already handles this via `OLLAMA_CONTEXT_LENGTH` in `.env`. For a native install, set it on the systemd service. Stop service.

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

Alternatively, set the context window per model in `.aider.model.settings.yml`. Aider looks for this file in your home directory, the git repo root, and the current directory, in that order (later files win):

```yaml
# .aider.model.settings.yml
- name: ollama_chat/phi4:latest
  extra_params:
    num_ctx: 8192
```

The `name:` must exactly match the model string passed to `--model`, prefix included, or the setting is silently ignored. `extra_params` is passed straight through to the model call, so `num_ctx` sets Ollama's context window; bigger values use more memory. Use `- name: aider/extra_params` to apply settings to every model at once.

## Run Aider

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

Start `aider` from inside a git repository.

```console
aider --model ollama_chat/phi4:latest
```

Type `/exit` to quit.

> **Note:** use the `ollama_chat/` prefix, not `ollama/`. Aider's docs recommend it; it uses Ollama's chat endpoint and produces noticeably better results. Whichever prefix you choose, use it consistently, including in `.aider.model.settings.yml`.

# Persisting Aider settings

Typing `--model` and exporting variables every session gets old. Add the export to your shell profile (`~/.bashrc`, `~/.zshrc`), or put it in a `.env` file in your project; Aider reads `.env` automatically.

```
# .env
OLLAMA_API_BASE=http://127.0.0.1:11444
```

> **Note:** in this repository, `.env` is also read by Docker Compose for the [Docker](#docker) setup; the two uses coexist fine, as each tool ignores variables it does not know.

Set the default model (and other options) in `.aider.conf.yml`, searched for in the same places as the model settings file:

```yaml
# .aider.conf.yml
model: ollama_chat/phi4:latest

# Optional:
# auto-commits: true   # git history is your undo log (default true)
# map-tokens: 1024     # size of the repo map (default ~1k)
# dark-mode: true
```

With this in place, a bare `aider` just works. Three files, three jobs: `.env` holds environment variables, `.aider.conf.yml` holds Aider options (which model, which flags), and `.aider.model.settings.yml` holds low-level per-model parameters like `num_ctx`.

# Aider workflow and commands

Aider is a pair programmer you steer one change at a time, not an autopilot. The loop: add the right files, agree on an approach, let it edit, review the auto-commit, repeat.

Managing context is the highest-leverage habit. Aider builds a repo map (a compact, tree-sitter-derived summary of the whole codebase) so the model understands structure cheaply, but the map is a heuristic; you still usually need to `/add` the specific files a change touches.

| Command      | What it does                                              |
| -            | -                                                         |
| `/add` file  | Put a file in the editable context                        |
| `/drop` file | Remove a file from context (do this often to save tokens) |
| `/ls`        | List files currently in context                           |
| `/tokens`    | Show how many tokens the current context is using         |

Aider has several [chat modes](https://aider.chat/docs/usage/modes.html):

| Command      | Mode           | Use it for                                       |
| -            | -              | -                                                |
| `/ask`       | Ask            | Discuss and plan; never edits files              |
| `/code`      | Code (default) | Make the edit                                    |
| `/architect` | Architect      | A reasoning model plans, an editor model applies |
| `/help`      | Help           | Questions about Aider itself                     |

The recommended rhythm is ask-then-code: strategise in `/ask` until you agree on the plan, then switch to `/code` and say "go ahead". This matters even more with local models, which plan better than they one-shot.

Git and running things:

| Command     | What it does                                                 |
| -           | -                                                            |
| `/undo`     | Revert Aider's last commit                                   |
| `/diff`     | Show what changed since the last message                     |
| `/commit`   | Commit pending changes with a generated message              |
| `/run` cmd  | Run a shell command and feed its output back to the model    |
| `/test` cmd | Run the test suite; on failure Aider can try to self-correct |
| `/lint`     | Run the linter and offer to fix issues                       |
| `/clear`    | Clear the chat history to start fresh and cut tokens         |
| `/exit`     | Quit (Ctrl-D also works)                                     |

A typical session:

```text
> /add src/parser.py
> /ask how should I add support for gzipped input?
  ... discuss the approach ...
> /code go ahead and implement that
  ... Aider edits, auto-commits ...
> /test pytest -q
  ... on failure, Aider proposes a fix ...
> /undo        # if you don't like the result
```

# Tuning Aider for local models

Local models are weaker than frontier hosted models. These habits make them behave:

- **Keep context small.** Local models degrade fast as context grows; `/add` only the files a change touches, `/drop` the rest, and `/clear` between unrelated tasks.
- **Always ask-then-code.** A local model that has agreed on a plan edits far more reliably than one asked to plan and edit in a single shot.
- **Watch the context window.** Silent truncation (see [the context-window gotcha](#the-context-window-gotcha)) is the number-one cause of weird local-model behaviour.
- **Let Aider pick the edit format.** Aider auto-selects the diff format it has benchmarked as most reliable for each model; do not override it unless you know why. If a small model produces broken diffs, the model may simply be too weak; step up a size.
- **Tune the repo map if needed.** `--map-tokens 1024` is the default; on a big repo you can raise it for more structural context, but that costs tokens the local model then has to process.

> **Note:** even well-tuned, a 30B local model will not match hosted frontier models on hard, open-ended tasks. Local Aider shines on surgical, well-scoped, privacy-sensitive, or offline edits.

# Aider troubleshooting

| Symptom                                                | Likely cause and fix                                                                                                |
| -                                                      | -                                                                                                                   |
| Connection refused / can't reach the model             | Ollama isn't running, or wrong URL; check `docker compose ps` (or the systemd service) and `OLLAMA_API_BASE`        |
| Vague or truncated answers that ignore parts of a file | Context window too small; raise `OLLAMA_CONTEXT_LENGTH` / `num_ctx`, or `/drop` unneeded files                      |
| "model not found"                                      | Model not pulled or wrong tag; `ollama list` shows the exact names, which must match the `--model` string after the prefix |
| Broken or unapplied diffs                              | Model too weak for the edit format; try a larger model and confirm the `ollama_chat/` prefix                        |
| `num_ctx` in the settings file seems ignored           | The `name:` must exactly match your `--model` string, prefix included                                               |
| Very slow responses                                    | Model larger than your RAM/VRAM comfortably holds, so it is swapping; pick a smaller model and check `ollama ps`    |
| "not a git repo" on start                              | Run Aider inside a git repository; `git init` if needed                                                             |

# Aider tips and further reading

- [Aider usage tips](https://aider.chat/docs/usage/tips.html)
- [Aider + Ollama connection docs](https://aider.chat/docs/llms/ollama.html)
- [Advanced model settings](https://aider.chat/docs/config/adv-model-settings.html) (`.aider.model.settings.yml`, `extra_params`, `num_ctx`)
- [Configuration with `.aider.conf.yml`](https://aider.chat/docs/config/aider_conf.html)
- [Chat modes](https://aider.chat/docs/usage/modes.html) and [in-chat commands](https://aider.chat/docs/usage/commands.html)
- [Code editing leaderboard](https://aider.chat/docs/leaderboards/edit.html)
- Community 2026 rankings of local coding models; informative, not independent proof: [Morph](https://www.morphllm.com/best-ollama-models), [Local AI Master](https://localaimaster.com/models/best-local-ai-coding-models), [haimaker.ai](https://haimaker.ai/blog/best-ollama-models-for-coding-agents/)

# OpenCode + Ollama

[OpenCode](https://opencode.ai/) is an open-source (MIT), model-agnostic AI coding agent for the terminal, built in TypeScript by Anomaly (the team formerly known as SST). Unlike a chat assistant it runs an agentic loop: it reads and edits files in your repository, runs shell commands (build, test, git), reads the results, and iterates until done or until it needs you. It also loads the right Language Server Protocol (LSP) servers for your project, so the agent gets real code intelligence (types, definitions, diagnostics) instead of guessing from raw text.

Where Aider is surgical and human-steered (you drive, it executes) and Claude Code is tied to Anthropic models, OpenCode is an autonomous agent you can point at any model: hosted providers via API keys, or a fully local one. OpenCode is a harness, not a model, so results are dominated by the model you plug in. With a local model nothing leaves your machine, which matters for clinical, genomic, or unpublished data.

Two built-in agents, toggled with **Tab**:

| Agent   | Access                                         |
| -       | -                                              |
| `build` | Full access; can edit files and run commands   |
| `plan`  | Read-only; analyse and explore before it edits |

> **Note:** do not confuse this OpenCode (Anomaly, [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode/), TypeScript) with Crush, the sibling Go project by Charm that continues the original codebase the two once shared. When reading third-party guides, check which one they mean.

## Install OpenCode

```console
curl -fsSL https://opencode.ai/install | bash
```

`npm install -g opencode-ai` and `brew install anomalyco/tap/opencode` also work. Verify the install:

```console
opencode --version
```

## Connect to the Docker Ollama server

Hosted providers are connected with `opencode auth login` (or `/connect` in the TUI), but a local Ollama server needs no key at all: Ollama exposes an OpenAI-compatible endpoint at `/v1`, and OpenCode reaches it through a JSON config file, either per project (`opencode.json` in the repo root) or global (`~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://127.0.0.1:11444/v1"
      },
      "models": {
        "phi4:latest": { "name": "Phi-4" }
      }
    }
  }
}
```

- `baseURL` points at your `OLLAMA_PORT` (`11444` with this repo's `.env`; use `http://<host-ip>:11444/v1` from another machine, or `11434` for a native install).
- `models` lists the Ollama models to expose in OpenCode; the keys must match the names shown by `ollama list`.

> **Note:** OpenCode requires a context length of 64k or higher, much more than the `8192` this repo's `.env` ships for Aider. A small window silently cripples the agent: it "forgets" files it just read and tool calls degrade, with no error shown. Set `OLLAMA_CONTEXT_LENGTH=65536` in `.env` and apply with `docker compose up -d`; bigger windows use more memory, so budget accordingly.

> **Note:** `phi4` (what the Docker setup pulls) is fine for light edits, but agentic coding stresses tool-calling reliability and edit discipline, exactly where smaller models wobble. For real work use a strong coding model such as `qwen2.5-coder:32b` (see [Choosing a local model](#choosing-a-local-model)) and add it to the `models` block.

On a native install you can skip the JSON entirely: `ollama launch opencode` starts OpenCode preconfigured for a chosen local model. And if you want hosted Claude in OpenCode, use an Anthropic API key; Claude Pro/Max subscription login no longer works in third-party tools since Anthropic blocked it in 2026.

## Usage

Start OpenCode from your project directory:

```console
opencode
```

Run `/models` to pick the model, then work in the same rhythm as Aider's ask-then-code: explore and agree on a plan in the read-only `plan` agent, press Tab to switch to `build`, and let it edit. Unlike Aider, OpenCode does not auto-commit; review the diff and commit yourself, though `/undo` reverts the last message and its file changes.

| Command     | What it does                                      |
| -           | -                                                 |
| `/models`   | List and switch models                            |
| `/init`     | Guided setup that creates or updates `AGENTS.md`  |
| `/undo`     | Undo the last message and revert its file changes |
| `/redo`     | Redo a previously undone message                  |
| `/compact`  | Summarise the session to cut context              |
| `/sessions` | List and switch between sessions                  |
| `/export`   | Export the conversation to Markdown               |
| `/new`      | Start a new session                               |
| `/help`     | Show the help dialog                              |
| `/exit`     | Quit                                              |

Run `/init` once per repository; it writes an `AGENTS.md` with project conventions that the agent reads every session, the equivalent of Claude Code's `CLAUDE.md`.

OpenCode is built client/server: `opencode serve` runs the headless engine (default `127.0.0.1:4096`) that the TUI, desktop app, IDE extensions, and your own scripts can all drive.

## Privacy notes

The main draw of OpenCode with a local model is that nothing leaves your machine, but that is a property of the backend, not the client. To keep it that way:

- **Use the local provider only.** Hosted providers receive your code under their own retention terms, and OpenCode Zen (the built-in curated model gateway, including its free models) routes prompts through OpenCode's own hosted infrastructure; it is not local and not zero-egress.
- **Disable session sharing.** `/share` publishes the full conversation history to a public URL until you run `/unshare`. For sensitive work set `"share": "disabled"` in `opencode.json` rather than relying on remembering not to type it.

## OpenCode further reading

- [OpenCode docs](https://opencode.ai/docs/); the authoritative, fast-moving reference, so check it before trusting third-party guides
- [Providers](https://opencode.ai/docs/providers/); current JSON syntax for local and custom OpenAI-compatible providers
- [Ollama's OpenCode integration guide](https://docs.ollama.com/integrations/opencode); the canonical local-model recipe, including the 64k+ context requirement
- [OpenCode on GitHub](https://github.com/anomalyco/opencode/); source, issues, and release notes, where breaking changes show up first
- [Crush](https://github.com/charmbracelet/crush); the sibling Go project, a strong alternative if you prefer a Charm-styled TUI

# llm + Ollama

[llm](https://llm.datasette.io/) is a command-line tool and Python library by [Simon Willison](https://simonwillison.net/) for interacting with large language models. Out of the box it talks to hosted APIs (OpenAI, Anthropic, Gemini, and others, which require API keys), and plugins add support for local models. Every prompt and response is logged to a local SQLite database, which makes it easy to search past conversations and compare models. This section sets it up against the [Docker](#docker) Ollama server.

## Install

After activating the [virtual environment](#create-python-virtual-environment):

```console
python -m pip install llm
```

(If you prefer an isolated install outside the venv: `pipx install llm`, `uv tool install llm`, or `brew install llm`.)

Ollama support comes from the [llm-ollama](https://github.com/taketwo/llm-ollama) plugin. Install it with `llm install` rather than plain `pip install`, so it lands in the same environment as `llm` itself:

```console
llm install llm-ollama
llm plugins   # confirm it is listed
```

## Connect to the Docker Ollama server

The plugin discovers models by querying an Ollama server, and like the `ollama` CLI it honours the `OLLAMA_HOST` environment variable. The Docker setup publishes the API on `OLLAMA_PORT` (`11444` in this repo's `.env`), so point `llm` there:

```bash
export OLLAMA_HOST=http://127.0.0.1:11444

# or from another machine on the network
export OLLAMA_HOST=http://<host-ip>:11444
```

No API key is needed; the Ollama API is unauthenticated (see the note in [Access from other computers](#access-from-other-computers)).

Verify that the Ollama models show up:

```console
llm models
```

Ollama models are listed with an `Ollama: ` prefix, e.g. `Ollama: phi4:latest`. Only models the server has already downloaded appear; the Docker setup pulls `phi4` automatically via `OLLAMA_PULL_MODELS`, and you can add more with `docker compose exec ollama ollama pull <model>`.

## Usage

Run a one-off prompt:

```console
llm -m phi4:latest 'Ten fun names for a pet pelican'
```

Start an interactive chat:

```console
llm chat -m phi4:latest
```

Pipe in files or command output, with `-s` setting a system prompt:

```console
cat entrypoint.sh | llm -m phi4:latest -s 'Explain this shell script'
```

Set a default model (so `-m` can be dropped) or a shorter alias:

```console
llm models default phi4:latest
llm aliases set phi phi4:latest   # then: llm -m phi 'hello'
```

Model options are passed with `-o`; for example a lower temperature, or a larger context window than the server default (`OLLAMA_CONTEXT_LENGTH` in `.env`):

```console
llm -m phi4:latest -o temperature 0.2 -o num_ctx 16384 'Summarise this...'
llm models --options   # list the options each model supports
```

Everything is logged to SQLite; browse or locate the database with:

```console
llm logs        # recent prompts and responses
llm logs path   # location of the database file
```

The plugin also supports [embeddings](https://llm.datasette.io/en/stable/embeddings/index.html) with Ollama embedding models (e.g. `mxbai-embed-large`) via `llm embed`.
