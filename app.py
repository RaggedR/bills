import os
import json
import csv
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
import anthropic

load_dotenv()

app = Flask(__name__)

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CATEGORIES_FILE = os.path.join(DATA_DIR, 'categories.json')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.json')
MERCHANT_CACHE_FILE = os.path.join(DATA_DIR, 'merchant_cache.json')

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


def load_json(filepath):
    """Load data from a JSON file."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return [] if 'categories' in filepath or 'transactions' in filepath else {}


def save_json(filepath, data):
    """Save data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def extract_merchant_name(description):
    """Extract a clean merchant name from transaction description."""
    # Remove common suffixes and clean up
    desc = description.strip()
    # Remove location info (usually after multiple spaces)
    desc = re.split(r'\s{2,}', desc)[0]
    # Remove trailing numbers and codes
    desc = re.sub(r'\s+\d+$', '', desc)
    desc = re.sub(r'\s+[A-Z]{2,3}$', '', desc)  # Remove state codes
    return desc.strip()


def categorize_transactions_batch(transactions, categories):
    """Categorize multiple transactions using AI in a single batch call."""
    merchant_cache = load_json(MERCHANT_CACHE_FILE)

    # Separate cached vs uncached transactions
    uncached_transactions = []
    for t in transactions:
        merchant = extract_merchant_name(t['description'])
        if merchant.lower() in merchant_cache:
            cached = merchant_cache[merchant.lower()]
            t['ai_suggested_code'] = cached['category_code']
            t['ai_confidence'] = 'high'
            t['ai_from_cache'] = True
        else:
            uncached_transactions.append(t)

    if not uncached_transactions:
        return transactions

    # Build category list for prompt
    category_list = "\n".join([
        f"- {c['code']}: {c['name']} ({c['category_type']})"
        for c in categories
    ])

    # Build transaction list for prompt
    transaction_list = "\n".join([
        f"{i+1}. [{t['date']}] {t['description']} | ${abs(float(t['amount'])):.2f} ({'expense' if float(t['amount']) < 0 else 'income'})"
        for i, t in enumerate(uncached_transactions)
    ])

    prompt = f"""Categorize these bank transactions. For each transaction, determine the best category.

Available categories:
{category_list}

Transactions to categorize:
{transaction_list}

Respond with ONLY a JSON array, one object per transaction in order:
[{{"id": 1, "category_code": "XXX", "confidence": "high/medium/low"}}, ...]

Rules:
- Positive amounts (income) should use category "1000"
- MONTHLY FEE = "500" (other)
- Groceries (Coles, Woolworths, etc) = "100"
- Restaurants/cafes/takeaway = "200"
- Transport (Uber, Myki, parking) = "300"
- Software/tech (GitHub, Claude, AWS, OpenAI) = "600"
- Pharmacy/medical = "700"
- Entertainment (museums, cinemas) = "800"
- Phone/utilities (Optus) = "900"
- If unsure, use "500" with low confidence"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()
        # Extract JSON array from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            results = json.loads(json_match.group())
            for i, result in enumerate(results):
                if i < len(uncached_transactions):
                    uncached_transactions[i]['ai_suggested_code'] = result.get('category_code', '500')
                    uncached_transactions[i]['ai_confidence'] = result.get('confidence', 'low')
                    uncached_transactions[i]['ai_from_cache'] = False
    except Exception as e:
        print(f"AI batch categorization error: {e}")
        # Fallback: mark all as "other"
        for t in uncached_transactions:
            t['ai_suggested_code'] = '500'
            t['ai_confidence'] = 'low'
            t['ai_from_cache'] = False

    return transactions


@app.route('/')
def index():
    return redirect(url_for('reconciliation'))


@app.route('/accounts')
def accounts():
    categories = load_json(CATEGORIES_FILE)
    return render_template('accounts.html', categories=categories)


@app.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    categories = load_json(CATEGORIES_FILE)

    if request.method == 'POST':
        data = request.json
        # Check for duplicate code
        if any(c['code'] == data['code'] for c in categories):
            return jsonify({'error': 'Category code already exists'}), 400

        categories.append({
            'code': data['code'],
            'name': data['name'],
            'type': data.get('type', 'variable'),
            'category_type': data.get('category_type', 'Expense')
        })
        save_json(CATEGORIES_FILE, categories)
        return jsonify({'success': True})

    return jsonify(categories)


@app.route('/api/categories/<code>', methods=['PUT', 'DELETE'])
def api_category(code):
    categories = load_json(CATEGORIES_FILE)

    if request.method == 'DELETE':
        categories = [c for c in categories if c['code'] != code]
        save_json(CATEGORIES_FILE, categories)
        return jsonify({'success': True})

    if request.method == 'PUT':
        data = request.json
        for c in categories:
            if c['code'] == code:
                c['name'] = data.get('name', c['name'])
                c['type'] = data.get('type', c['type'])
                c['category_type'] = data.get('category_type', c['category_type'])
                break
        save_json(CATEGORIES_FILE, categories)
        return jsonify({'success': True})

    return jsonify({'error': 'Method not allowed'}), 405


@app.route('/reconciliation')
def reconciliation():
    categories = load_json(CATEGORIES_FILE)
    transactions = load_json(TRANSACTIONS_FILE)
    return render_template('reconciliation.html',
                         categories=categories,
                         transactions=transactions)


@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Read CSV
        content = file.read().decode('utf-8')
        reader = csv.reader(content.splitlines())

        transactions = load_json(TRANSACTIONS_FILE)
        categories = load_json(CATEGORIES_FILE)
        existing_ids = {t.get('id') for t in transactions}

        new_transactions = []
        for row in reader:
            if len(row) >= 3:
                date_str, amount_str, description = row[0], row[1], row[2]

                # Parse date (DD/MM/YYYY format)
                try:
                    date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                    date_formatted = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    date_formatted = date_str

                # Parse amount (remove quotes and +/- signs for storage)
                amount = float(amount_str.replace('"', '').replace(',', ''))

                # Create unique ID
                trans_id = f"{date_formatted}_{abs(amount)}_{hash(description) % 10000}"

                if trans_id not in existing_ids:
                    new_transactions.append({
                        'id': trans_id,
                        'date': date_formatted,
                        'amount': amount,
                        'description': description.strip(),
                        'category_code': None,
                        'reconciled': False
                    })

        # AI categorize new transactions
        if new_transactions:
            new_transactions = categorize_transactions_batch(new_transactions, categories)
            transactions.extend(new_transactions)
            # Sort by date descending
            transactions.sort(key=lambda x: x['date'], reverse=True)
            save_json(TRANSACTIONS_FILE, transactions)

        return jsonify({
            'success': True,
            'imported': len(new_transactions),
            'transactions': transactions
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def api_transactions():
    transactions = load_json(TRANSACTIONS_FILE)
    filter_type = request.args.get('filter', 'all')

    if filter_type == 'unreconciled':
        transactions = [t for t in transactions if not t.get('reconciled')]
    elif filter_type == 'reconciled':
        transactions = [t for t in transactions if t.get('reconciled')]

    return jsonify(transactions)


@app.route('/api/transactions/<trans_id>', methods=['PUT'])
def api_transaction(trans_id):
    transactions = load_json(TRANSACTIONS_FILE)
    data = request.json

    for t in transactions:
        if t['id'] == trans_id:
            if 'category_code' in data:
                t['category_code'] = data['category_code']
            if 'reconciled' in data:
                t['reconciled'] = data['reconciled']
            if 'note' in data:
                t['note'] = data['note']

            # Update merchant cache if user changed category
            if data.get('category_code') and data.get('update_cache', True):
                merchant = extract_merchant_name(t['description'])
                merchant_cache = load_json(MERCHANT_CACHE_FILE)
                merchant_cache[merchant.lower()] = {
                    'category_code': data['category_code'],
                    'confidence': 'high',
                    'learned_from': trans_id
                }
                save_json(MERCHANT_CACHE_FILE, merchant_cache)

            break

    save_json(TRANSACTIONS_FILE, transactions)
    return jsonify({'success': True})


@app.route('/api/reconcile', methods=['POST'])
def reconcile_transaction():
    """Reconcile a single transaction."""
    data = request.json
    trans_id = data.get('transaction_id')
    category_code = data.get('category_code')

    if not trans_id or not category_code:
        return jsonify({'error': 'Missing transaction_id or category_code'}), 400

    transactions = load_json(TRANSACTIONS_FILE)

    for t in transactions:
        if t['id'] == trans_id:
            t['category_code'] = category_code
            t['reconciled'] = True

            # Update merchant cache
            merchant = extract_merchant_name(t['description'])
            merchant_cache = load_json(MERCHANT_CACHE_FILE)
            merchant_cache[merchant.lower()] = {
                'category_code': category_code,
                'confidence': 'high',
                'learned_from': trans_id
            }
            save_json(MERCHANT_CACHE_FILE, merchant_cache)
            break

    save_json(TRANSACTIONS_FILE, transactions)
    return jsonify({'success': True})


@app.route('/api/reconcile-all', methods=['POST'])
def reconcile_all():
    """Reconcile all unreconciled transactions using AI suggestions."""
    transactions = load_json(TRANSACTIONS_FILE)
    merchant_cache = load_json(MERCHANT_CACHE_FILE)
    reconciled_count = 0

    for t in transactions:
        if not t.get('reconciled') and t.get('ai_suggested_code'):
            t['category_code'] = t['ai_suggested_code']
            t['reconciled'] = True
            reconciled_count += 1

            # Update merchant cache
            merchant = extract_merchant_name(t['description'])
            merchant_cache[merchant.lower()] = {
                'category_code': t['ai_suggested_code'],
                'confidence': 'high',
                'learned_from': t['id']
            }

    save_json(TRANSACTIONS_FILE, transactions)
    save_json(MERCHANT_CACHE_FILE, merchant_cache)
    return jsonify({'success': True, 'reconciled': reconciled_count})


@app.route('/analysis')
def analysis():
    categories = load_json(CATEGORIES_FILE)
    transactions = load_json(TRANSACTIONS_FILE)
    return render_template('analysis.html',
                         categories=categories,
                         transactions=transactions)


@app.route('/api/analysis')
def api_analysis():
    """Get analysis data for charts."""
    transactions = load_json(TRANSACTIONS_FILE)
    categories = load_json(CATEGORIES_FILE)

    # Filter for reconciled expenses only
    transaction_type = request.args.get('type', 'expenses')

    if transaction_type == 'expenses':
        filtered = [t for t in transactions if t.get('reconciled') and t['amount'] < 0]
    elif transaction_type == 'income':
        filtered = [t for t in transactions if t.get('reconciled') and t['amount'] > 0]
    else:
        filtered = [t for t in transactions if t.get('reconciled')]

    # Group by category
    category_totals = {}
    category_transactions = {}

    for t in filtered:
        code = t.get('category_code', '500')
        amount = abs(t['amount'])

        if code not in category_totals:
            category_totals[code] = 0
            category_transactions[code] = []

        category_totals[code] += amount
        category_transactions[code].append(t)

    # Build response with category names
    category_map = {c['code']: c for c in categories}

    result = []
    for code, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        cat = category_map.get(code, {'name': 'Unknown', 'type': 'variable'})
        result.append({
            'code': code,
            'name': cat['name'],
            'type': cat['type'],
            'total': round(total, 2),
            'transactions': category_transactions[code]
        })

    return jsonify(result)


@app.route('/api/clear-transactions', methods=['POST'])
def clear_transactions():
    """Clear all transactions (for testing)."""
    save_json(TRANSACTIONS_FILE, [])
    return jsonify({'success': True})


@app.route('/api/clear-data', methods=['POST'])
def clear_data():
    """Clear all transactions and merchant cache."""
    save_json(TRANSACTIONS_FILE, [])
    save_json(MERCHANT_CACHE_FILE, {})
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5001)
