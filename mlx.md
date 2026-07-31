# Contents

- [MLX](#mlx)
  - [How it differs from Ollama](#how-it-differs-from-ollama)
  - [Install](#install)
- [Apertus 1.5 on MLX](#apertus-15-on-mlx)
  - [Why not Ollama?](#why-not-ollama)
  - [Available conversions](#available-conversions)
  - [Generate](#generate)
  - [Chat](#chat)
  - [Server](#server)
    - [How it compares with Ollama](#how-it-compares-with-ollama)
- [Use cases](#use-cases)
  - [Bulk processing](#bulk-processing)
  - [Data that cannot leave the machine](#data-that-cannot-leave-the-machine)
  - [Offline work](#offline-work)
  - [Reproducible research](#reproducible-research)
  - [Writing and small chores](#writing-and-small-chores)
  - [Multilingual work](#multilingual-work)
  - [Through the llm CLI](#through-the-llm-cli)
    - [In-process, with llm-mlx](#in-process-with-llm-mlx)
    - [Server mode](#server-mode)
  - [What to skip](#what-to-skip)
- [Gotchas](#gotchas)
  - [The 100-token default](#the-100-token-default)
  - [Deliberation blocks](#deliberation-blocks)
  - [The Mistral regex warning](#the-mistral-regex-warning)
  - [Memory pressure](#memory-pressure)
- [Converting your own](#converting-your-own)
- [Further reading](#further-reading)

# MLX

[MLX](https://github.com/ml-explore/mlx) is Apple's array framework for Apple silicon. It runs models on the M-series GPU through the chip's *unified memory*: the CPU and GPU share one pool of RAM, so there is no separate VRAM budget and no copying of weights between them. A 16 GB Mac can load any model that fits in 16 GB minus whatever the rest of the system is using.

[`mlx-lm`](https://github.com/ml-explore/mlx-lm) is the language-model layer on top: a Python package with a CLI for generation, chat and an OpenAI-compatible server. It reads models in MLX's own safetensors layout, which is why models are republished as separate `-mlx-` repositories on Hugging Face rather than reusing the GGUF files.

## How it differs from Ollama

|                  | Ollama                          | MLX                                |
| -                | -                               | -                                  |
| Platform         | Linux, macOS, Windows           | Apple silicon only                 |
| Backend          | llama.cpp                       | MLX                                |
| Model format     | GGUF                            | MLX safetensors                    |
| Model source     | `ollama pull`, `hf.co/...`      | Hugging Face repo ID, fetched on first run |
| Serving          | Ollama API (+ OpenAI shim)      | OpenAI-compatible only             |
| Model storage    | `~/.ollama` (or the server's)   | `~/.cache/huggingface/hub`         |

The two are independent stacks. The `ollama` CLI cannot talk to an `mlx_lm.server`, and MLX cannot load GGUF files. Nothing stops you running both on the same Mac.

## Install

MLX requires Apple silicon (M1 or later) and a recent macOS. There is nothing to configure — no daemon, no service, no GPU runtime.

```console
pip install mlx-lm
```

Models are downloaded on first use into the shared Hugging Face cache, so a model pulled by `mlx-lm` is visible to any other tool using that cache.

# Apertus 1.5 on MLX

[Apertus](https://publicai.co/stories/apertus-1-5) is the Swiss AI Initiative's fully open model family — open weights, open data, Apache 2.0. Version 1.5, released 24 July 2026, adds reasoning, a 262,144-token context and multimodal input (images and audio in, text out), in 8B and 70B sizes.

## Why not Ollama?

Apertus 1.5 declares a new architecture, `Apertus1p5ForConditionalGeneration` / `model_type: apertus1p5`, with separate vision and audio tokenizer configs. llama.cpp only knows the older text-only `apertus` architecture from version 1.0, so no GGUF conversions of 1.5 exist and `ollama pull` has nothing to fetch. Everything on the Ollama side is still the September 2025 (`2509`) release:

```console
# Apertus 1.0, works today
ollama pull hf.co/unsloth/Apertus-8B-Instruct-2509-GGUF:Q4_K_M
```

MLX gets 1.5 today by sidestepping the problem. The community conversions strip the vision and audio towers, trim the embeddings back to the 131,072-token text vocabulary, and relabel the result as plain `ApertusForCausalLM`. That works because the 1.5 *text tower* is architecturally identical to 1.0 — same 32 layers, 4096 hidden size, 8 KV heads, xIELU activation, QK-norm — differing only in RoPE constants, which are config values rather than new code. The upshot is that `mlx-lm` runs Apertus 1.5 through code written for Apertus 1.0.

The cost of that trick: **these conversions are text-only**. You get 1.5's reasoning and instruction-following, not its multimodality.

## Available conversions

All three are Apache 2.0, ungated, and were published three days after the 1.5 release.

| Repo                                   | Weights | Comfortable on | Notes                          |
| -                                      | -       | -              | -                              |
| `tokimoa/apertus-v1.5-8b-mlx-4bit`     | 4.3 GB  | 8 GB Mac       | group size 64, ~4.5 bits/weight |
| `tokimoa/apertus-v1.5-8b-mlx-8bit`     | ~8.5 GB | 16 GB Mac      | best quality/size trade-off    |
| `tokimoa/apertus-v1.5-8b-mlx-bf16`     | ~16 GB  | 24 GB+ Mac     | unquantised reference          |

The packager measured cosine similarity against the bf16 reference at 0.93–0.98 for the 4-bit build versus 0.999+ for the 8-bit, and warns that the gap can compound over long reasoning chains. Top-1 token agreement held across their test prompts either way. Start at 4-bit; move to 8-bit if you see the model losing the thread on longer tasks.

These are community conversions, not official Swiss AI releases.

## Generate

A single prompt, no interaction:

```console
python -m mlx_lm generate --model tokimoa/apertus-v1.5-8b-mlx-8bit \
  --prompt "Write an R script that will generate 50 random whole numbers" \
  --max-tokens 1024 --temp 0.0
```

The first run downloads the weights; later runs start from the cache. `--temp 0.0` makes output deterministic, which is what you want when comparing models or debugging a prompt.

Piping works via `-` and pairs well with a system prompt:

```console
cat entrypoint.sh | python -m mlx_lm generate \
  --model tokimoa/apertus-v1.5-8b-mlx-8bit \
  --system-prompt 'Explain this shell script' --prompt - --max-tokens 1024
```

## Chat

An interactive session that keeps context between turns:

```console
python -m mlx_lm chat --model tokimoa/apertus-v1.5-8b-mlx-8bit
```

## Server

`mlx-lm` exposes an OpenAI-compatible HTTP API, which is how you point existing tooling at it:

```console
python -m mlx_lm.server --model tokimoa/apertus-v1.5-8b-mlx-8bit
```

It binds to `127.0.0.1:8080` by default; `--host` and `--port` change that, and `--host 0.0.0.0` exposes it to the LAN. Four endpoints are served:

| Endpoint               | Method | Purpose                                        |
| -                      | -      | -                                              |
| `/v1/chat/completions` | POST   | Chat completions, streaming or not             |
| `/v1/completions`      | POST   | Raw text completions                           |
| `/v1/models`           | GET    | Lists MLX models found in the Hugging Face cache |
| `/health`              | GET    | Liveness check                                 |

`--model` is optional. It only defines what the alias `default_model` resolves to, so a request that names no model still works:

```console
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 512}'
```

Naming a model in the request body switches to it, downloading it first if it is not already cached:

```console
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "tokimoa/apertus-v1.5-8b-mlx-4bit",
       "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 512}'
```

Aider, OpenCode and `llm` all speak this API, so a Mac running `mlx_lm.server` slots in wherever those tools expect an OpenAI base URL. Note that the server's flag for chat template arguments is `--chat-template-args`, not the `--chat-template-config` that `mlx_lm generate` uses.

### How it compares with Ollama

The mental model is much the same: one long-lived process, models loaded on demand, chosen by name per request. The differences are in the protocol and in what stays resident.

|                        | Ollama                                     | `mlx_lm.server`                            |
| -                      | -                                          | -                                          |
| Protocol               | native `/api/*` **plus** an OpenAI `/v1/*` shim | OpenAI `/v1/*` only                   |
| Default address        | `127.0.0.1:11434`                          | `127.0.0.1:8080`                           |
| List models            | `ollama list`, `GET /api/tags`             | `GET /v1/models`                           |
| Where models come from | `~/.ollama`, populated by `ollama pull`    | the Hugging Face cache, populated on first use |
| Choose model per request | yes                                      | yes                                        |
| Models resident at once | several                                   | **one** — switching evicts the previous     |
| Idle unload            | yes, via `OLLAMA_KEEP_ALIVE`               | none; the model stays loaded until swapped or the process exits |
| Pull a model ahead of time | `ollama pull`                          | `huggingface-cli download <repo>`, or just make one request |
| Authentication         | none                                       | none (`--allowed-origins` controls CORS only) |

Three consequences worth planning around:

- **`ollama` CLI commands will not work against it.** `ollama list`, `ollama run` and the `llm-ollama` plugin all speak the native API, which `mlx_lm.server` does not implement. Configure it as an OpenAI-compatible provider instead, or use [`llm-mlx`](#through-the-llm-cli).
- **Alternating between two models is expensive.** Ollama can keep several resident and switch cheaply; `mlx_lm.server` reloads from disk on every switch, which for an 8-bit 8B means re-reading roughly 8.5 GB. Group work by model rather than interleaving.
- **The model never unloads on its own.** There is no keep-alive timer, so the RAM stays occupied until you stop the server. On a laptop that is usually what you want during a work session and not what you want left running.

Neither exposes any authentication, so the note in the README's [Access from other computers](README.md#access-from-other-computers) applies here too: keep it on localhost or a trusted network.

# Use cases

An 8B model on a laptop is not a smaller frontier model. It is weak at multi-step reasoning and knows little about anything recent, but it is free per token, private, and always available. The uses that pay off follow from those three properties rather than from raw capability.

## Bulk processing

The best fit for a local model. Anything repetitive across hundreds of items — classifying, tagging, summarising, extracting structured fields from free text, normalising messy metadata — is where a hosted API gets expensive and rate-limited, and where an 8B is usually good enough because each individual task is small and tightly constrained.

The important detail is to **load the model once**. Every `python -m mlx_lm generate` invocation re-reads the full weights from disk, so a shell loop over a thousand items spends most of its time loading:

```python
from mlx_lm import load, generate

model, tokenizer = load("tokimoa/apertus-v1.5-8b-mlx-4bit")

for item in items:
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": f"...{item}..."}],
        add_generation_prompt=True,
        tokenize=False,
    )
    print(generate(model, tokenizer, prompt=prompt, max_tokens=512))
```

Alternatively run `mlx_lm.server` and drive it over HTTP from R or Python, which keeps the model resident across separate scripts.

## Data that cannot leave the machine

Unpublished results, anything under a data access agreement, draft grant text, material with identifiers in it. Here the usual objection that a small model is weaker does not apply, because the alternative is not a better model — it is doing the work by hand.

## Offline work

A Dockerised Ollama server on the LAN is unreachable the moment the laptop leaves the network. MLX is the same capability that still works on a train.

## Reproducible research

Apertus is fully open: Apache 2.0 weights, published training data, and a Hugging Face revision you can pin. If a step in an analysis involves a language model, you can state exactly which model touched the data and someone can rerun it years later. A methods section citing a hosted endpoint that has since been retired cannot offer that.

## Writing and small chores

Restating an explanation more simply, generating variants of an exercise, first-pass alt text, commit messages from a diff, regex, `awk` and `jq` one-liners, roxygen comments for an R function. Outputs are short, so even a modest tokens/sec rate is no obstacle, and the output gets edited anyway.

## Multilingual work

This is Apertus's real differentiator at this size. It is strong across German, French, Italian and English, where most 8B models are not.

## Through the llm CLI

MLX models can sit in the same `llm` install as the Ollama models, sharing the SQLite logging described in the README, so `llm models` lists both backends and `llm logs` covers everything. There are two ways to wire it up.

### In-process, with llm-mlx

The [`llm-mlx`](https://github.com/simonw/llm-mlx) plugin runs MLX inside the `llm` process — no server, no port:

```console
llm install llm-mlx
llm mlx download-model tokimoa/apertus-v1.5-8b-mlx-4bit
llm -m tokimoa/apertus-v1.5-8b-mlx-4bit 'Ten fun names for a pet pelican'
llm logs
```

The catch is that every `llm` invocation is a fresh process, so the weights are reloaded from disk each time. For an occasional one-off that is fine; for anything repeated it dominates the runtime.

### Server mode

Pointing `llm` at a running `mlx_lm.server` keeps the model resident between calls, which is the main reason to prefer it.

Start the server:

```console
python -m mlx_lm.server --model tokimoa/apertus-v1.5-8b-mlx-8bit --max-tokens 2048
```

Find the `llm` configuration directory — on macOS this is `~/Library/Application Support/io.datasette.llm`:

```console
dirname "$(llm logs path)"
```

Create `extra-openai-models.yaml` in that directory:

```yaml
- model_id: apertus-mlx
  model_name: tokimoa/apertus-v1.5-8b-mlx-8bit
  api_base: http://127.0.0.1:8080/v1
  aliases:
    - apertus
```

`model_id` is what you type after `-m`. `model_name` is what `llm` sends in the request body, so it has to be something the server can load — a Hugging Face repo id, or the literal `default_model` to always use whatever the server was started with. The `api_base` must include the `/v1` suffix.

No API key is required. In `llm`'s OpenAI plugin, setting `api_base` also sets `needs_key = None`, a deliberate safety property so that a configured OpenAI key is never sent to a local or third-party endpoint. There is no need to invent a dummy key.

Check that it registered, then use it like any other model:

```console
llm models | grep -i apertus
llm -m apertus 'Write an R script that will generate 50 random whole numbers'
llm chat -m apertus
llm logs
```

Three things to watch:

- **`max_tokens` defaults to 512** on the server, rather than the 100 that `mlx_lm generate` uses. Deliberation blocks still eat into it, so raise it per call with `-o max_tokens 2048` or start the server with a higher `--max-tokens`. See [The 100-token default](#the-100-token-default).
- **Registering several MLX models and alternating between them is slow.** The server keeps one model resident, so each switch re-reads the full weights — see [How it compares with Ollama](#how-it-compares-with-ollama).
- **Streaming works by default.** Add `can_stream: false` to the YAML only if something downstream cannot cope.

## What to skip

- **Agentic coding.** An 8B does not hold a multi-file edit plan together; Aider and OpenCode will churn. Single-file edits are fine, autonomous work is not.
- **Questions about current facts or library APIs.** It will answer confidently and be wrong.
- **The full 262K context.** The number is real, but the KV cache exhausts unified memory long before you approach it. See [Memory pressure](#memory-pressure).
- **Anything costly to get wrong that you will not check.** The right jobs are ones where verification is cheap, or where the output is explicitly a draft.

# Gotchas

## The 100-token default

`--max-tokens` defaults to **100**. That is small enough that a reasoning model can spend the whole budget thinking and emit no answer at all, which looks like a hang or a truncated reply:

```
Generation: 100 tokens, 10.173 tokens-per-sec
```

Any exact-100 generation is this. Pass `--max-tokens 1024` or more for anything that produces code. Note that the short flag `-m` means `--max-tokens`, not `--model`.

## Deliberation blocks

Apertus 1.5 reasons before answering, wrapping its working in `<|inner_prefix|>` ... `<|inner_suffix|>` before the real reply. This is normal output, not a bug — but it consumes tokens, which is what makes the 100-token default bite so hard.

The chat template gates this on `enable_thinking`, and `mlx-lm` passes no template arguments unless you ask it to, so the rendered prompt says `Deliberation: disabled` while the model often deliberates regardless. To set the flag explicitly:

```console
--chat-template-config '{"enable_thinking": false}'
```

Treat it as a hint rather than a switch, and size `--max-tokens` accordingly.

## The Mistral regex warning

On load, transformers prints:

```
[transformers] The tokenizer you are loading from '...' with an incorrect regex
pattern: https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503/discussions/84
This will lead to incorrect tokenization. You should set the `fix_mistral_regex=True`
flag when loading this tokenizer to fix this issue.
```

**Ignore it.** The pre-tokenizer regex in Apertus's `tokenizer.json` is byte-for-byte the *corrected* pattern from that discussion, not the broken one the warning is aimed at. Tokenization is already right and `fix_mistral_regex=True` would change nothing.

## Memory pressure

`mlx-lm` reports peak memory at the end of every run:

```
Peak memory: 8.658 GB
```

Because unified memory is shared with everything else on the Mac, throughput falls off sharply once that figure approaches installed RAM. The 4-bit build reaches roughly 75 tokens/sec on an M4 Max; single-digit token rates on a smaller machine are a sign the model is too large for the memory available rather than a sign the model is slow. Dropping from 8-bit to 4-bit is usually a bigger win than any sampling tweak.

For long contexts, the KV cache is the other consumer. `--max-kv-size` caps it, and `--kv-bits 8` quantises it:

```console
python -m mlx_lm generate --model tokimoa/apertus-v1.5-8b-mlx-4bit \
  --prompt "..." --max-tokens 2048 --max-kv-size 8192 --kv-bits 8
```

# Converting your own

`mlx_lm.convert` turns any supported Hugging Face model into MLX format, optionally quantising on the way:

```console
python -m mlx_lm.convert --hf-path swiss-ai/Apertus-8B-Instruct-2509 \
  --mlx-path ./apertus-8b-mlx-4bit -q --q-bits 4 --q-group-size 64
```

This works for architectures `mlx-lm` already implements — Apertus 1.0 has `mlx_lm/models/apertus.py`, which is exactly what the 1.5 conversions above reuse. Converting stock `swiss-ai/Apertus-v1.5-8B` directly will fail on the unknown `apertus1p5` architecture; the text-tower extraction has to happen first.

# Further reading

- [MLX](https://github.com/ml-explore/mlx) and [mlx-lm](https://github.com/ml-explore/mlx-lm)
- [MLX documentation](https://ml-explore.github.io/mlx/)
- [Apertus 1.5 announcement](https://publicai.co/stories/apertus-1-5)
- [swiss-ai on Hugging Face](https://huggingface.co/swiss-ai) — upstream weights (gated)
- [mlx-community](https://huggingface.co/mlx-community) — a large collection of ready-made MLX conversions
