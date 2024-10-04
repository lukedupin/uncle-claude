#!/usr/bin/zsh

cd ~/Development/uncle-claude
source venv/bin/activate
python uncle_claude.py ~/.claude "$(printf "%q " "$@")"
