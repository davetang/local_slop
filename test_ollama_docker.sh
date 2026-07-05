#!/usr/bin/env bash

python3 ollama_benchmark.py --hosts http://127.0.0.1:11444 --model phi4:latest --runs 2 --num-predict 200
