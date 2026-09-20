from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, jsonify
import sqlite3
import turso_serverless
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

app = Flask(__name__)
# Replace this with a random secret in production
app.secret_key = os.environ.get('FLASK_SECRET', 'change_this_to_a_random_secret')
# Make sessions "permanent" by default and set lifetime (e.g., 7 days)
app.permanent_session_lifetime = timedelta(days=7)

def get_db():
    db = getattr(g, '_database', None)

    if db is None:
        db = g._database = turso_serverless.connect(
            os.environ["TURSO_DATABASE_URL"],
            auth_token=os.environ["TURSO_AUTH_TOKEN"]
        )

    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)

    if db is not None:
        db.close()


class DBRow(dict):
    """SQLite Row-like object that supports both row['column'] and row[0]."""

    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)

    rows = cur.fetchall()

    if cur.description:
        columns = [column[0] for column in cur.description]
        rows = [DBRow(columns, row) for row in rows]

    cur.close()

    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    conn = get_db()

    cur = conn.execute(query, args)

    conn.commit()

    cur.close()

# Simple helper to get current user in templates
@app.context_processor
def inject_user():
    return {'current_user': session.get('username')}

# Decorator to protect routes
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            # preserve where the user wanted to go
            next_url = request.path
            return redirect(url_for('login', next=next_url))
        return f(*args, **kwargs)
    return decorated

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    next_page = request.args.get('next') or request.form.get('next') or url_for('index')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username and password are required.')
            return render_template('signup.html', next=next_page)
        # check if username exists
        existing = query_db('SELECT id FROM users WHERE username = ?', (username,), one=True)
        if existing:
            flash('Username already taken. Please choose another.')
            return render_template('signup.html', next=next_page)
        pw_hash = generate_password_hash(password)
        execute_db('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pw_hash))
        # log the user in
        user = query_db('SELECT id, username FROM users WHERE username = ?', (username,), one=True)
        session['user_id'] = user['id']
        session['username'] = user['username']
        flash('Signup successful. You are now logged in.')
        return redirect(next_page)
    return render_template('signup.html', next=next_page)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next') or request.form.get('next') or url_for('index')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username and password required.')
            return render_template('login.html', next=next_page)
        user = query_db('SELECT id, username, password_hash FROM users WHERE username = ?', (username,), one=True)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password. If you are a new user, please sign up.')
            return render_template('login.html', next=next_page)
        session['user_id'] = user['id']
        session['username'] = user['username']
        flash('Logged in successfully.')
        return redirect(next_page)
    return render_template('login.html', next=next_page)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logout')
def logout():
    # clear session so the user is logged out
    session.clear()
    flash('You have been logged out.')
    # redirect back to the site index
    return redirect(url_for('index'))

# Initialize DB
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY,
            item TEXT,
            amount REAL,
            date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY,
            detail TEXT,
            amount REAL,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

# Example: protect add_sale route
@app.route('/add_sale', methods=['GET', 'POST'])
@login_required
def add_sale():
    if request.method == "POST":
        item = request.form["item"]
        amount = float(request.form["amount"])
        date = request.form["date"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO sales(item, amount, date) VALUES (?, ?, ?)", (item, amount, date))
        conn.commit()
        conn.close()
        flash("✅ Sale added successfully!", "success")
        return redirect("/add_sale")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales")
    sales = cur.fetchall()
    conn.close()
    return render_template("add_sale.html", sales=sales)

@app.route("/delete_sale/<int:sale_id>")
@login_required
def delete_sale(sale_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    conn.commit()
    conn.close()
    flash("🗑️ Sale deleted.", "danger")
    return redirect("/add_sale")


@app.route("/add_expense", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        detail = request.form["detail"]
        amount = float(request.form["amount"])
        date = request.form["date"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO expenses(detail, amount, date) VALUES (?, ?, ?)", (detail, amount, date))
        conn.commit()
        conn.close()
        flash("✅ Expense added successfully!", "success")
        return redirect("/add_expense")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses")
    expenses = cur.fetchall()
    conn.close()
    return render_template("add_expense.html", expenses=expenses)


@app.route("/delete_expense/<int:expense_id>")
@login_required
def delete_expense(expense_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    flash("🗑️ Expense deleted.", "danger")
    return redirect("/add_expense")


@app.route('/api/expenses', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_expenses():
    """Simple JSON API for expenses.
    GET  /api/expenses?month=YYYY-MM  -> list expenses for month
    POST /api/expenses (json)         -> add expense {detail, amount, date}
    DELETE /api/expenses?month=YYYY-MM -> delete all expenses for month
    """
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'GET':
        month = request.args.get('month')
        if month:
            cur.execute("SELECT id, detail, amount, date FROM expenses WHERE substr(date,1,7)=?", (month,))
        else:
            cur.execute("SELECT id, detail, amount, date FROM expenses")
        rows = cur.fetchall()
        conn.close()
        result = [{'id': r[0], 'detail': r[1], 'amount': float(r[2]), 'date': r[3]} for r in rows]
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json() or request.form
        detail = data.get('detail', '')
        try:
            amount = float(data.get('amount', 0))
        except Exception:
            amount = 0
        date = data.get('date') or datetime.now().strftime('%Y-%m-%d')
        cur.execute("INSERT INTO expenses(detail, amount, date) VALUES (?, ?, ?)", (detail, amount, date))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    if request.method == 'DELETE':
        month = request.args.get('month')
        if not month:
            conn.close()
            return jsonify({'error': 'month required'}), 400
        cur.execute("DELETE FROM expenses WHERE substr(date,1,7)=?", (month,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})


@app.route("/report")
@login_required
def report():
    # Accept month in format YYYY-MM (from <input type="month">). Default to current month.
    selected_month = request.args.get('month')
    if not selected_month:
        selected_month = datetime.now().strftime('%Y-%m')

    # Sorting: support sort_by (date|amount) and order (asc|desc)
    sort_by = request.args.get('sort_by', 'date')
    if sort_by not in ('date', 'amount'):
        sort_by = 'date'
    # Always sort ascending
    order = 'asc'

    conn = get_db()
    cur = conn.cursor()

    # Totals and lists for the selected month (using prefix YYYY-MM of date column which is stored as YYYY-MM-DD)
    cur.execute("SELECT SUM(amount) FROM sales WHERE substr(date,1,7)=?", (selected_month,))
    total_sales = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(amount) FROM expenses WHERE substr(date,1,7)=?", (selected_month,))
    total_expenses = cur.fetchone()[0] or 0

    cur.execute(f"SELECT id, item, amount, date FROM sales WHERE substr(date,1,7)=?", (selected_month,))
    sales_list = cur.fetchall()
    cur.execute(f"SELECT id, detail, amount, date FROM expenses WHERE substr(date,1,7)=?", (selected_month,))
    expenses_list = cur.fetchall()

    # Build a combined ledger (list of dicts) and sort in Python according to sort_by/order
    ledger = []
    for s in sales_list:
        # s => (id, item, amount, date)
        ledger.append({'date': s[3], 'type': 'Sale', 'description': s[1], 'amount': float(s[2])})
    for e in expenses_list:
        # e => (id, detail, amount, date)
        ledger.append({'date': e[3], 'type': 'Expense', 'description': e[1], 'amount': float(e[2])})

    if sort_by == 'date':
        ledger.sort(key=lambda x: x['date'], reverse=(order == 'desc'))
    else:
        ledger.sort(key=lambda x: x['amount'], reverse=(order == 'desc'))

    ledger_list = ledger

    # Compute last month's profit and percentage change
    try:
        year, month = map(int, selected_month.split('-'))
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        prev_month_str = f"{prev_year:04d}-{prev_month:02d}"
    except Exception:
        prev_month_str = None

    last_month_profit = 0
    last_month_label = ""
    profit_change_pct = None
    if prev_month_str:
        cur.execute("SELECT SUM(amount) FROM sales WHERE substr(date,1,7)=?", (prev_month_str,))
        last_sales = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(amount) FROM expenses WHERE substr(date,1,7)=?", (prev_month_str,))
        last_expenses = cur.fetchone()[0] or 0
        last_month_profit = last_sales - last_expenses
        # Month label (e.g., September 2025)
        import calendar
        last_month_label = f"{calendar.month_name[prev_month]} {prev_year}"
        # Percentage change
        if last_month_profit != 0:
            profit_change_pct = ((total_sales - total_expenses) - last_month_profit) / abs(last_month_profit) * 100
        else:
            profit_change_pct = None

    # Prepare calendar-year months (Jan..Dec) for the selected year
    try:
        sel_year = int(selected_month.split('-')[0])
        sel_month_num = int(selected_month.split('-')[1])
    except Exception:
        sel_year = datetime.now().year
        sel_month_num = datetime.now().month

    import calendar
    months_labels = [f"{calendar.month_abbr[m]} {sel_year}" for m in range(1, 13)]
    monthly_profits = []
    for m in range(1, 13):
        month_str = f"{sel_year:04d}-{m:02d}"
        cur.execute("SELECT SUM(amount) FROM sales WHERE substr(date,1,7)=?", (month_str,))
        s = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(amount) FROM expenses WHERE substr(date,1,7)=?", (month_str,))
        e = cur.fetchone()[0] or 0
        monthly_profits.append(s - e)

    # Prepare paired list for template: [(label, profit), ...]
    monthly_summary = list(zip(months_labels, monthly_profits))

    # selected month label for display (e.g., 'Oct 2025')
    selected_month_label = f"{calendar.month_name[sel_month_num]} {sel_year}"

    conn.close()

    return render_template("report.html",
                           total_sales=total_sales,
                           total_expenses=total_expenses,
                           sales_list=sales_list,
                           expenses_list=expenses_list,
                           selected_month=selected_month,
                           selected_month_label=selected_month_label,
                           last_month_profit=last_month_profit,
                           last_month_label=last_month_label,
                           profit_change_pct=profit_change_pct,
                           months=months_labels,
                           monthly_profits=monthly_profits,
                           monthly_summary=monthly_summary,
                           sort_by=sort_by,
                           order=order,
                           ledger_list=ledger_list)

@app.route('/Budget')
@login_required
def budget():
    return render_template('Budget.html')

def is_safe_url(target):
    host_url = request.host_url
    test_url = urljoin(host_url, target)
    return urlparse(test_url).netloc == urlparse(host_url).netloc

if __name__ == "__main__":
    app.run(debug=True)
