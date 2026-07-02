#!/usr/bin/env bash

python3 ollama_benchmark.py \
    --hosts http://192.168.0.5:11434 http://192.168.0.31:11434 http://127.0.0.1:11434 http://192.168.0.168:11434 \
    --model llama3.1 \
    --runs 5 \
    --num-predict 200
