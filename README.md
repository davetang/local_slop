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
