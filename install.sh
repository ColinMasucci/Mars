#!/bin/bash

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e .

echo "MARS installed"
echo "Activate with: source .venv/bin/activate"
echo "Run with: mars run file.mars"