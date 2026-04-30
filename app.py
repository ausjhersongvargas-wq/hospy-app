import os
import functools
from flask import (Flask, render_template, jsonify, send_file,
                   abort, request, session, redirect, url_for)
from sheets import get_kpis, get_products, get_invoices, update_product, \
                   get_products_by_category, batch_update_stock

# ── CONFIG ───────────────────────────────────────────────────────────────────
INBOX_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'stock', 'inbox')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
APP_USER   = os.environ.get('APP_USER',     'hospy')
APP_PASS   = os.environ.get('APP_PASSWORD', 'cumbia2024')   # override in Railway

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── AUTH DECORATOR ───────────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

# ── LOGIN / LOGOUT ───────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        pw   = request.form.get('password', '')
        if user == APP_USER and pw == APP_PASS:
            session['logged_in'] = True
            return redirect(request.args.get('next') or url_for('index'))
        error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── MAIN APP ─────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/kpis')
@login_required
def api_kpis():
    try:
        return jsonify({'ok': True, 'data': get_kpis()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products')
@login_required
def api_products():
    try:
        return jsonify({'ok': True, 'data': get_products()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/invoices')
@login_required
def api_invoices():
    try:
        return jsonify({'ok': True, 'data': get_invoices()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products/update', methods=['POST'])
@login_required
def api_update_product():
    try:
        data          = request.get_json()
        product_id    = data.get('id', '').strip()
        current_stock = float(data.get('current_stock', 0))
        par_level     = float(data.get('par_level', 0))
        reorder_point = float(data.get('reorder_point', 0))
        if not product_id:
            return jsonify({'ok': False, 'error': 'Missing product id'}), 400
        row = update_product(product_id, current_stock, par_level, reorder_point)
        return jsonify({'ok': True, 'row': row})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/invoice/<path:filename>')
@login_required
def serve_invoice(filename):
    pdf_name = filename.replace('.json', '.pdf')
    pdf_path = os.path.realpath(os.path.join(INBOX_DIR, pdf_name))
    if not pdf_path.startswith(os.path.realpath(INBOX_DIR)):
        abort(403)
    if not os.path.isfile(pdf_path):
        abort(404)
    return send_file(pdf_path, mimetype='application/pdf')

# ── STOCK TOOL ───────────────────────────────────────────────────────────────
@app.route('/api/stock-tool/<category>')
@login_required
def api_stock_tool_products(category):
    allowed = {'kitchen', 'bar', 'cafe', 'cleaning', 'supplies', 'operations'}
    if category.lower() not in allowed:
        return jsonify({'ok': False, 'error': 'Invalid category'}), 400
    try:
        products = get_products_by_category(category)
        # Remove internal _row field before sending to client
        for p in products:
            p.pop('_row', None)
        return jsonify({'ok': True, 'data': products, 'category': category})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/stock-tool/save', methods=['POST'])
@login_required
def api_stock_tool_save():
    try:
        data    = request.get_json()
        updates = data.get('updates', [])
        if not updates:
            return jsonify({'ok': False, 'error': 'No updates provided'}), 400
        # Validate each entry
        clean = []
        for u in updates:
            clean.append({
                'id':            str(u.get('id', '')).strip(),
                'par_level':     float(u.get('par_level', 0)),
                'current_stock': float(u.get('current_stock', 0)),
            })
        count = batch_update_stock(clean)
        return jsonify({'ok': True, 'updated': count})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port  = int(os.environ.get('PORT', 5000))
    app.run(debug=debug, host='0.0.0.0', port=port)
