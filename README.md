# Run LLMs locally

[Install Ollama](https://ollama.com/download):

```console
curl -fsSL https://ollama.com/install.sh | sh
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
