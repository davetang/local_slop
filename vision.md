# Contents

- [Identifying images](#identifying-images)
  - [Four different tasks](#four-different-tasks)
  - [From classifiers to describers](#from-classifiers-to-describers)
  - [What the projector layer is](#what-the-projector-layer-is)
  - [What a VLM is good and bad at](#what-a-vlm-is-good-and-bad-at)
- [Is a model multimodal?](#is-a-model-multimodal)
  - [Before pulling](#before-pulling)
  - [After pulling](#after-pulling)
- [Getting qwen3.8:27b](#getting-qwen3827b)
- [Using it with plot.png](#using-it-with-plotpng)
  - [The CLI](#the-cli)
  - [The API](#the-api)
  - [Python](#python)
  - [Structured output](#structured-output)
  - [llm](#llm)
- [Gotchas](#gotchas)
  - [Bare filenames are silently ignored](#bare-filenames-are-silently-ignored)
  - [Which machine reads the file](#which-machine-reads-the-file)
  - [Images cost context](#images-cost-context)
  - [Thinking is on by default](#thinking-is-on-by-default)
  - [Speed](#speed)
- [Further reading](#further-reading)

# Identifying images

## Four different tasks

"Identify this image" hides four jobs that computer vision keeps separate, because they need different models and are scored differently:

| Task | Question answered | Output |
|----------------|--------------------------------------|-------------------------------|
| Classification | What is this a picture of? | one label, or a ranked list |
| Detection | What is in it, and where? | labels + bounding boxes + scores |
| Segmentation | Which pixels belong to what? | a per-pixel mask |
| Description/VQA| Describe it; answer a question about it | free text |

A vision-language model (VLM) like `qwen3.8:27b` does the fourth job, and does the first three only by talking about them. This distinction is the whole practical story: ask it what a figure shows and it is a good tool; ask it for the pixel coordinates of the third point in a scatter plot and it will answer confidently and be wrong.

## From classifiers to describers

The short version of how the field arrived at models like this:

- **Hand-crafted features** (SIFT, HOG) fed into a classifier such as an SVM. A human decided what an edge or a corner was worth.
- **Convolutional networks** learned the features instead. AlexNet's 2012 ImageNet win is the usual landmark, and the R-CNN family and YOLO turned the same idea into detectors that draw boxes in real time.
- **Vision transformers** (2020) dropped the convolution and cut the image into fixed patches, each treated like a token in a sentence, which made image models architecturally the same shape as language models.
- **Contrastive pretraining** (CLIP, 2021) trained an image encoder and a text encoder against 400M image-caption pairs until an image and its caption landed at the same point in a shared space. This is where open-vocabulary recognition comes from: no fixed label list.
- **Vision-language models** (LLaVA, 2023 onward) bolted a CLIP-style encoder onto a pretrained LLM through a small trained adapter, so images could be fed into a model that already knew how to reason and write.

`qwen3.8:27b` is the last of these: an LLM that has been given eyes.

## What the projector layer is

That adapter is not an abstraction, it is a file. An Ollama model is a set of layers, and a multimodal one ships two weight blobs instead of one:

```console
curl -s https://registry.ollama.ai/v2/library/qwen3.8/manifests/27b | jq -r '.layers[] | "\(.mediaType)\t\(.size)"'
```

```
application/vnd.ollama.image.projector      931146016
application/vnd.ollama.image.model        16810714464
application/vnd.ollama.image.license            11345
application/vnd.ollama.image.params               114
```

The 931 MB `projector` is the vision tower plus the adapter that follows it. The pipeline is: the image is resized and cut into patches, the vision encoder turns those patches into embeddings, and the projector maps those embeddings into the same space the language model uses for word tokens. After that step the model does not know it is looking at a picture, it just sees a run of tokens in the prompt like any other. Everything downstream, the reasoning, the writing, the tool calls, is the ordinary text model.

Two useful consequences fall out of this:

- A model with no `projector` layer cannot take images, whatever the prompt says. `qwen3.5:27b` has no projector; `qwen3.6:27b` and `qwen3.8:27b` do.
- An image is spent as tokens out of your context window, so image size is a cost, not just a quality knob.

## What a VLM is good and bad at

Worth doing:

- Describing a figure, and reading its axis labels, legend, title and annotations.
- Answering questions about a document, screenshot or diagram, including OCR of reasonably sized text.
- Sanity-checking a plot against what you expected it to show, which catches swapped axes, an unlabelled log scale, or a legend that does not match the caption.
- Extracting fields into a fixed schema, using the structured output described below.

Not worth doing:

- Bounding boxes, pixel coordinates, or anything you intend to measure. Use a real detector (YOLO, DETR) or classical CV.
- Counting more than a handful of objects. Accuracy falls off quickly.
- Reading values off a chart to any precision. It infers plausible numbers rather than measuring them.
- Anything that needs a calibrated confidence. A number the model writes after the word "confidence" is generated text, not a probability.
- Small print, dense scatter plots, and low-contrast detail, which are the classic hallucination triggers.

# Is a model multimodal?

## Before pulling

The manifest answers it without downloading 18 GB, by checking for the projector layer:

```console
curl -s https://registry.ollama.ai/v2/library/qwen3.8/manifests/27b | jq -r '.layers[].mediaType' | grep projector
```

The model's page on [ollama.com](https://ollama.com/library/qwen3.8) shows the same thing as capability badges (`vision`, `tools`, `thinking`) and an input column reading `Text, Image`.

## After pulling

Ask the server, which reports capabilities per model:

```console
ollama show qwen3.8:27b
```

The `Capabilities` table lists `vision` for a multimodal model. Over the API:

```console
curl -s http://127.0.0.1:11444/api/show -d '{"model": "qwen3.8:27b"}' | jq .capabilities
```

```json
["completion", "vision", "tools", "thinking"]
```

# Getting qwen3.8:27b

18 GB, a 256K context window, Q4_K_M. Against the [Docker](README.md#docker) server:

```console
docker compose exec ollama ollama pull qwen3.8:27b
```

Or from the host CLI, pointed at the published port:

```bash
export OLLAMA_HOST=http://127.0.0.1:11444
ollama pull qwen3.8:27b
```

# Using it with plot.png

## The CLI

The prompt takes the path inline:

```console
ollama run qwen3.8:27b "Describe what this plot shows ./plot.png"
```

The CLI prints `Added image './plot.png'` when it recognises the path, which is the confirmation to look for. In an interactive session the same thing works at the `>>>` prompt, and you can keep asking follow-up questions about an image already in the conversation.

## The API

The API takes base64, never a path, so the file has to be encoded into the request. `images` is an array on the message:

```console
curl -s http://127.0.0.1:11444/api/chat -d "$(jq -n \
  --arg img "$(base64 -w0 plot.png)" \
  '{model: "qwen3.8:27b",
    stream: false,
    think: false,
    messages: [{role: "user",
                content: "What does this figure show? Read the axis labels.",
                images: [$img]}]}')" | jq -r .message.content
```

On macOS `base64 -w0` is `base64 -i plot.png` (BSD base64 does not wrap by default).

`/api/generate` takes the same data, but with `images` at the top level of the request rather than on a message:

```console
curl -s http://127.0.0.1:11444/api/generate -d "$(jq -n \
  --arg img "$(base64 -w0 plot.png)" \
  '{model: "qwen3.8:27b", stream: false, prompt: "Describe this figure.", images: [$img]}')" | jq -r .response
```

## Python

The Python client will accept a path, raw bytes, or a base64 string in `images`, and does the encoding for you:

```python
from ollama import Client

client = Client(host='http://127.0.0.1:11444')

response = client.chat(
    model='qwen3.8:27b',
    think=False,
    messages=[{
        'role': 'user',
        'content': 'What does this figure show? Read the axis labels and the legend.',
        'images': ['plot.png'],
    }],
)

print(response.message.content)
```

Install with `python -m pip install ollama` inside the [virtual environment](README.md#create-python-virtual-environment).

## Structured output

Free text is awkward to check. Passing a JSON schema as `format` constrains the reply, which turns a description into something a script can consume, and makes the answer far easier to compare across models or across runs:

```python
from pydantic import BaseModel
from ollama import Client


class PlotDescription(BaseModel):
    plot_type: str
    x_label: str
    y_label: str
    n_series: int
    title: str | None = None
    takeaway: str


client = Client(host='http://127.0.0.1:11444')

response = client.chat(
    model='qwen3.8:27b',
    format=PlotDescription.model_json_schema(),
    options={'temperature': 0},
    think=False,
    messages=[{
        'role': 'user',
        'content': 'Describe this plot. Leave fields empty if you cannot read them.',
        'images': ['plot.png'],
    }],
)

print(PlotDescription.model_validate_json(response.message.content))
```

The schema constrains the shape of the answer, not its truth. A field it cannot read is a field it may invent, so the instruction to leave unreadable fields empty is doing real work.

## llm

The [llm-ollama](https://github.com/taketwo/llm-ollama) plugin set up in [llm + Ollama](README.md#llm--ollama) passes images through as attachments, with `-a` taking a path or a URL:

```console
llm -m qwen3.8:27b 'Describe this plot' -a plot.png
```

Because `llm` logs every prompt and response to SQLite, this is the convenient option when you want to compare several models on the same figure afterwards:

```console
llm logs -n 5
```

# Gotchas

## Bare filenames are silently ignored

The CLI finds image paths with a regex that requires a leading `./`, `/` or `\`, and an extension of `.jpg`, `.jpeg`, `.png`, `.webp` or `.wav`. So this works:

```console
ollama run qwen3.8:27b "Describe ./plot.png"
```

and this quietly sends a text-only prompt:

```console
ollama run qwen3.8:27b "Describe plot.png"
```

There is no warning, and the model answers anyway by guessing from the filename, which is the most confusing possible failure. Look for the `Added image` line. The file type is checked by sniffing the content rather than trusting the extension, and there is a 100 MB limit.

## Which machine reads the file

The CLI reads and encodes the image itself, then sends base64 over the API. So a host path is resolved on the host, and works fine against the container:

```bash
export OLLAMA_HOST=http://127.0.0.1:11444
ollama run qwen3.8:27b "Describe ./plot.png"   # host path, container server: fine
```

But `docker compose exec ollama ollama run ...` runs the CLI *inside* the container, where `./plot.png` is a container path that almost certainly does not exist. Either run the CLI on the host as above, or mount the directory into the container.

## Images cost context

An image becomes tokens, roughly in proportion to its pixel count, so a full-resolution screenshot can cost hundreds to a few thousand tokens before you have said anything. This repo's `.env` sets `OLLAMA_CONTEXT_LENGTH=8192`, and Ollama does not error when a request overflows the window, it silently truncates (see [The context-window gotcha](README.md#the-context-window-gotcha)). With images that truncation can drop part of the picture rather than part of the text.

Raise `OLLAMA_CONTEXT_LENGTH` in `.env` and restart, or set `num_ctx` per request, and downscale images to the smallest size that keeps the text legible. A 4K screenshot of a plot rarely tells the model anything a 1024px version does not.

## Thinking is on by default

Qwen3.8 has thinking enabled by default, so an unadorned request spends tokens reasoning before it answers. Turn it off with `think: false` in the API, `think=False` in Python, or `--think=false` on the CLI. The API also accepts a level rather than a boolean, `"low"`, `"medium"`, `"high"` or `"max"`, and the CLI flag takes `low`/`medium`/`high`, which is the more useful knob for a hard figure.

Default sampling parameters shipped with the model are `temperature 1`, `top_k 20`, `top_p 0.95`, `min_p 0`. For description work that you intend to check or diff, set `temperature 0`.

## Speed

Every 27B model in `ollama_benchmark_table.md` runs at about 1.67 tok/s with GPU at 0%, i.e. CPU-only, with a ~30 s cold load and around 17.7 GB resident. Prefill for that size measures ~260 tok/s, so an image costs a few extra seconds before the first token, on top of a generation rate that takes minutes for a paragraph. Usable for a handful of figures, painful for a batch. `qwen3.6:27b` also has a projector and is the same speed, so it is the cheaper thing to test the plumbing against if it is already pulled.

Note that `ollama_model_benchmark.py` sends text only. Benchmarking the vision path would mean adding `images` to the request it builds, and the prefill numbers it reports would then include the image tokens.

# Further reading

- [Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md) — the `images` field on `/api/chat` and `/api/generate`
- [ollama-python examples](https://github.com/ollama/ollama-python/tree/main/examples) — `multimodal-chat.py` and `structured-outputs-image.py`
- [Structured outputs in Ollama](https://ollama.com/blog/structured-outputs)
- [qwen3.8 on ollama.com](https://ollama.com/library/qwen3.8)
- [llm-ollama](https://github.com/taketwo/llm-ollama) — image attachments through the `llm` CLI
- [CLIP](https://openai.com/research/clip) and [LLaVA](https://llava-vl.github.io/) — the contrastive encoder and the projector-into-an-LLM recipe that most open VLMs follow
