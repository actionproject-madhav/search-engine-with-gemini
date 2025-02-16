# Gemini Search Engine 🔍

[![CI/CD](https://github.com/actionproject-madhav/gemini-search-engine/actions/workflows/python-app.yml/badge.svg)](https://github.com/actionproject-madhav/gemini-search-engine/actions)

A privacy-focused search engine for the Gemini protocol.

## Features
- Gemini protocol crawler
- Full-text search capabilities
- Web proxy for Gemini content
- SQLite-based storage

## Quick Start
```bash
git clone https://github.com/actionproject-madhav/gemini-search-engine
cd gemini-search-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start crawler
python crawler/crawler.py

# Start web interface
python app/app.py