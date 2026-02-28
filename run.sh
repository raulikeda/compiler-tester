#!/bin/bash

# Run the application inside a detached screen session silently
screen -q -S compiler-tester -dm bash -c "source env/bin/activate && python3 main.py > ./log/uvicorn-\$(date +%Y-%m-%d).log 2>&1"