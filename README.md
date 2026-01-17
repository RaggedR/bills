# Bills

A bank statement analyzer with AI-powered transaction categorization. Import CSV bank statements, get automatic expense category suggestions via Claude AI, and visualize spending with interactive charts.

![Reconciliation View](screenshot2.jpg)

## Features

- **CSV Import**: Upload bank statements in CSV format (DD/MM/YYYY date format)
- **AI Categorization**: Automatic transaction categorization using Claude API
- **Merchant Learning**: Remembers your category corrections for future imports
- **Reconciliation Workflow**: Review and confirm AI suggestions one-by-one or accept all
- **Spending Analysis**: Interactive donut/pie/bar charts showing expenses by category
- **Category Management**: Create and manage expense/income categories

## Screenshots

| Account Codes | Reconciliation | Analysis |
|---------------|----------------|----------|
| ![Account Codes](screenshot.jpg) | ![Reconciliation](screenshot2.jpg) | ![Analysis](screenshot3.jpg) |

## Setup

### Prerequisites

- Python 3.10+
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd bills

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Running

```bash
python app.py
```

The app runs at http://localhost:5001 (port 5001 is used because macOS reserves 5000 for AirPlay).

## Usage

### 1. Set Up Categories

Navigate to **Account Codes** to create expense categories:

- `100` - Groceries
- `200` - Dining/Takeaway
- `300` - Transport
- `500` - Other
- `1000` - Income

Each category has a code, name, type (fixed/variable), and category type (Expense/Income/Asset).

### 2. Import Bank Statement

1. Go to **Bank Statement Reconciliation**
2. Click **Upload CSV** and select your bank export
3. The AI will automatically categorize all transactions

### 3. Reconcile Transactions

- Review each transaction and its AI-suggested category
- Click to select a different category if needed
- Click **Reconcile Transaction** to confirm
- Or click **Reconcile All** to accept all AI suggestions at once

The system learns from your corrections - next time you import a transaction from the same merchant, it will use your category choice.

### 4. Analyze Spending

Go to **Analysis** to see:

- Donut/pie chart of spending by category
- Bar chart comparison
- Click any segment to see individual transactions
- Filter by expenses, income, or all transactions

## CSV Format

The app expects CSV files in this format:

```
DD/MM/YYYY,"-amount","MERCHANT DESCRIPTION",""
```

Example:
```
02/01/2026,"-52.63","COLES 0645 OAKLEIGH 03",""
02/01/2026,"+2703.70","AUTO PAYMENT - THANK YOU",""
```

- Negative amounts = expenses
- Positive amounts = income
- 4th column is ignored

## Data Storage

All data is stored as JSON files in the `data/` directory:

- `categories.json` - Expense category definitions
- `transactions.json` - Imported transactions with reconciliation status
- `merchant_cache.json` - Learned merchant-to-category mappings

## Tech Stack

- **Backend**: Flask (Python)
- **AI**: Claude API (claude-sonnet-4-20250514)
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **Charts**: Chart.js
- **Storage**: JSON files (no database required)

## License

MIT
