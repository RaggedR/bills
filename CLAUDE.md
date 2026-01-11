# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bank statement analyzer with AI-powered transaction categorization. Flask web app that imports CSV bank statements, uses Claude API to automatically suggest expense categories, and visualizes spending with charts.

## Development Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run development server (port 5001 - macOS uses 5000 for AirPlay)
python app.py
```

App runs at http://localhost:5001

## Architecture

**Single-file Flask app** (`app.py`) with JSON file storage:

- `data/categories.json` - Expense category definitions (code, name, type)
- `data/transactions.json` - Imported transactions with reconciliation status
- `data/merchant_cache.json` - Learned merchant → category mappings (improves AI suggestions over time)

**Key flows:**

1. **CSV Import** (`/api/upload-csv`): Parses bank CSV (DD/MM/YYYY date format, signed amounts), generates unique transaction IDs, calls `categorize_transactions_batch()` to get AI suggestions in a single API call
2. **AI Categorization**: Batches all uncached transactions into one Claude API prompt, checks merchant cache first for previously-learned mappings
3. **Reconciliation**: User confirms/corrects AI suggestions; corrections are saved to merchant cache for future imports
4. **Analysis**: Aggregates reconciled transactions by category for Chart.js visualization

**Frontend**: Jinja2 templates with vanilla JS, Chart.js for donut/bar charts. No build step.

## Configuration

Requires `.env` file with:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## CSV Format Expected

```
DD/MM/YYYY,"-amount","MERCHANT DESCRIPTION",""
```
- Negative amounts = expenses, positive = income
- 4th column unused
