import os
import functools
from flask import (Flask, render_template, jsonify, send_file,
                   abort, request, session, redirect, url_for)
from sheets import get_kpis, get_products, get_invoices, update_product, \
                   get_products_by_category, batch_update_stock, \
                   get_categories, get_products_by_section, add_product, delete_product, \
                   update_product_category, get_archived_products, restore_product, \
                   fix_invoice_log_totals, update_invoice_total, \
                   get_menu_items, get_menu_item_detail, add_menu_item, \
                   add_menu_ingredient, delete_menu_ingredient

# ── CONFIG ───────────────────────────────────────────────────────────────────
INBOX_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'stock', 'inbox')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
APP_USER   = os.environ.get('APP_USER',     'hospy')
APP_PASS   = os.environ.get('APP_PASSWORD', 'cumbia2024')   # override in Railway

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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

@app.route('/api/invoices/update-total', methods=['POST'])
@login_required
def api_update_invoice_total():
    try:
        data      = request.get_json()
        sheet_row = int(data.get('row', 0))
        new_total = float(data.get('total', 0))
        if sheet_row < 3:
            return jsonify({'ok': False, 'error': 'Invalid row'}), 400
        update_invoice_total(sheet_row, new_total)
        return jsonify({'ok': True, 'row': sheet_row, 'total': new_total})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/invoices/fix-totals', methods=['POST'])
@login_required
def api_fix_invoice_totals():
    try:
        fixes = fix_invoice_log_totals()
        return jsonify({'ok': True, 'fixed': len(fixes), 'details': fixes})
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
@app.route('/api/categories')
@login_required
def api_categories():
    try:
        return jsonify({'ok': True, 'data': get_categories()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/stock-tool/section/<section>')
@login_required
def api_stock_tool_section(section):
    allowed = {'kitchen', 'bar'}
    if section.lower() not in allowed:
        return jsonify({'ok': False, 'error': 'Invalid section'}), 400
    try:
        products = get_products_by_section(section)
        for p in products:
            p.pop('_row', None)
        return jsonify({'ok': True, 'data': products, 'section': section})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/stock-tool/<category>')
@login_required
def api_stock_tool_products(category):
    allowed = {'kitchen', 'bar', 'cafe', 'cleaning', 'supplies', 'operations'}
    if category.lower() not in allowed:
        return jsonify({'ok': False, 'error': 'Invalid category'}), 400
    try:
        products = get_products_by_category(category)
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

@app.route('/api/products/add', methods=['POST'])
@login_required
def api_add_product():
    try:
        data = request.get_json()
        name     = str(data.get('name', '')).strip()
        category = str(data.get('category', '')).strip()
        if not name or not category:
            return jsonify({'ok': False, 'error': 'Name and category are required'}), 400
        product = add_product(
            name          = name,
            category      = category,
            provider      = str(data.get('provider', '')).strip(),
            unit          = str(data.get('unit', '')).strip(),
            par_level     = float(data.get('par_level', 0)),
            current_stock = float(data.get('current_stock', 0)),
            unit_cost     = float(data.get('unit_cost', 0)),
        )
        return jsonify({'ok': True, 'product': product})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products/category', methods=['POST'])
@login_required
def api_update_product_category():
    try:
        data       = request.get_json()
        product_id = str(data.get('id', '')).strip()
        category   = str(data.get('category', '')).strip()
        if not product_id or not category:
            return jsonify({'ok': False, 'error': 'id and category are required'}), 400
        row = update_product_category(product_id, category)
        return jsonify({'ok': True, 'row': row})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products/delete', methods=['POST'])
@login_required
def api_delete_product():
    try:
        data       = request.get_json()
        product_id = str(data.get('id', '')).strip()
        if not product_id:
            return jsonify({'ok': False, 'error': 'Missing product id'}), 400
        row = delete_product(product_id)
        return jsonify({'ok': True, 'row': row})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products/archived')
@login_required
def api_archived_products():
    try:
        return jsonify({'ok': True, 'data': get_archived_products()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/products/restore', methods=['POST'])
@login_required
def api_restore_product():
    try:
        data       = request.get_json()
        product_id = str(data.get('id', '')).strip()
        if not product_id:
            return jsonify({'ok': False, 'error': 'Missing product id'}), 400
        row = restore_product(product_id)
        return jsonify({'ok': True, 'row': row})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── MENU ─────────────────────────────────────────────────────────────────────
@app.route('/api/menu/items')
@login_required
def api_menu_items():
    try:
        return jsonify({'ok': True, 'data': get_menu_items()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/menu/item/<dish_id>')
@login_required
def api_menu_item(dish_id):
    try:
        return jsonify({'ok': True, 'data': get_menu_item_detail(dish_id)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/menu/items/add', methods=['POST'])
@login_required
def api_menu_items_add():
    try:
        data     = request.get_json()
        name     = str(data.get('name', '')).strip()
        category = str(data.get('category', '')).strip()
        notes    = str(data.get('notes', '')).strip()
        if not name:
            return jsonify({'ok': False, 'error': 'Dish name is required'}), 400
        dish = add_menu_item(name, category, notes)
        return jsonify({'ok': True, 'dish': dish})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/menu/ingredients/add', methods=['POST'])
@login_required
def api_menu_ingredients_add():
    try:
        data            = request.get_json()
        dish_id         = str(data.get('dish_id', '')).strip()
        product_id      = str(data.get('product_id', '')).strip()
        ingredient_name = str(data.get('ingredient_name', '')).strip()
        qty_needed      = float(data.get('qty_needed', 0))
        unit            = str(data.get('unit', '')).strip()
        optional        = bool(data.get('optional', False))
        if not dish_id or not product_id:
            return jsonify({'ok': False, 'error': 'dish_id and product_id are required'}), 400
        add_menu_ingredient(dish_id, product_id, ingredient_name, qty_needed, unit, optional)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/menu/ingredients/delete', methods=['POST'])
@login_required
def api_menu_ingredients_delete():
    try:
        data       = request.get_json()
        dish_id    = str(data.get('dish_id', '')).strip()
        product_id = str(data.get('product_id', '')).strip()
        if not dish_id or not product_id:
            return jsonify({'ok': False, 'error': 'dish_id and product_id are required'}), 400
        delete_menu_ingredient(dish_id, product_id)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port  = int(os.environ.get('PORT', 5000))
    app.run(debug=debug, host='0.0.0.0', port=port)
