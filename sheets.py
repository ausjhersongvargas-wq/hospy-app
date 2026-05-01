import os
import json
import base64
import tempfile
import gspread
from google.oauth2 import service_account
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'spartan-perigee-494417-f5-18b861c72c49.json')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '10RxL-POJ-lJRMYXoSEq4TdUllcg4mw3WnKMLLhNowM8')

SCOPES_READ  = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SCOPES_WRITE = ['https://www.googleapis.com/auth/spreadsheets']

def _get_creds(write=False):
    """Load credentials — from env var (cloud) or local file (dev)."""
    scopes = SCOPES_WRITE if write else SCOPES_READ
    # Cloud: credentials stored as base64 in env var
    b64 = os.environ.get('GOOGLE_CREDENTIALS_B64')
    if b64:
        info = json.loads(base64.b64decode(b64).decode('utf-8'))
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    # Local dev: use file
    return service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)

def get_spreadsheet(write=False):
    gc = gspread.authorize(_get_creds(write=write))
    return gc.open_by_key(SPREADSHEET_ID)

# Master_Stock columns (0-indexed):
# A=0 ID, B=1 Name, C=2 Category, D=3 Provider, E=4 Unit,
# F=5 Par Level, G=6 Current Stock, H=7 Reorder Point,
# I=8 Unit Cost, J=9 Total Value, K=10 Status

def get_products():
    sh = get_spreadsheet(write=False)
    ms = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    products = []
    for row in rows[2:]:  # skip 2 header rows
        if len(row) < 8 or not row[1]:
            continue
        if row[1].strip().upper() == 'TOTAL':
            continue

        def safe_float(val):
            try:
                return float(str(val).replace(',', '').replace('$', '').strip())
            except:
                return 0.0

        current_stock = safe_float(row[6] if len(row) > 6 else 0)
        reorder_point = safe_float(row[7] if len(row) > 7 else 0)
        unit_cost = safe_float(row[8] if len(row) > 8 else 0)
        par_level = safe_float(row[5] if len(row) > 5 else 0)
        total_value = safe_float(row[9] if len(row) > 9 else current_stock * unit_cost)

        # Derive status if formula isn't computed
        raw_status = row[10].strip() if len(row) > 10 else ''
        if raw_status in ('OUT OF STOCK', 'LOW STOCK', 'OK'):
            status = raw_status
        elif current_stock == 0:
            status = 'OUT OF STOCK'
        elif current_stock <= reorder_point:
            status = 'LOW STOCK'
        else:
            status = 'OK'

        products.append({
            'id': row[0].strip(),
            'name': row[1].strip(),
            'category': row[2].strip() if len(row) > 2 else '',
            'provider': row[3].strip() if len(row) > 3 else '',
            'unit': row[4].strip() if len(row) > 4 else '',
            'par_level': par_level,
            'current_stock': current_stock,
            'reorder_point': reorder_point,
            'unit_cost': unit_cost,
            'total_value': total_value,
            'status': status,
        })

    return products

# Invoice_Log columns (0-indexed):
# A=0 Date, B=1 Invoice#, C=2 Provider, D=3 Filename,
# E=4 Items, F=5 Total, G=6 Status, H=7 Notes

def get_invoices():
    sh = get_spreadsheet(write=False)
    il = sh.worksheet('Invoice_Log')
    rows = il.get_all_values()

    def safe_float(val):
        try:
            return float(str(val).replace(',', '').replace('$', '').strip())
        except:
            return 0.0

    invoices = []
    for sheet_row, row in enumerate(rows[2:], start=3):  # skip 2 header rows; sheet_row is 1-indexed
        if not row[0] and not row[1]:
            continue

        invoices.append({
            'date': row[0].strip() if row[0] else '',
            'invoice_number': row[1].strip() if len(row) > 1 else '',
            'provider': row[2].strip() if len(row) > 2 else '',
            'filename': row[3].strip() if len(row) > 3 else '',
            'items': int(safe_float(row[4])) if len(row) > 4 else 0,
            'total': safe_float(row[5]) if len(row) > 5 else 0.0,
            'status': row[6].strip() if len(row) > 6 else '',
            '_row': sheet_row,
        })

    return invoices


def update_invoice_total(invoice_number, new_total):
    """Update the total (col F) of an Invoice_Log row, found by invoice_number (col B)."""
    sh = get_spreadsheet(write=True)
    il = sh.worksheet('Invoice_Log')
    rows = il.get_all_values()
    for idx, row in enumerate(rows[2:], start=3):   # skip 2 header rows; idx = actual sheet row
        if len(row) > 1 and row[1].strip() == str(invoice_number).strip():
            il.update([[float(new_total)]], f'F{idx}', value_input_option='USER_ENTERED')
            return idx
    raise ValueError(f'Invoice number "{invoice_number}" not found in Invoice_Log')

def fix_invoice_log_totals():
    """
    Scan Invoice_Log and correct totals that are 100x too large
    (caused by pdfplumber dropping decimal points during extraction).
    Returns list of dicts describing each fix applied.
    """
    import time as _time
    sh  = get_spreadsheet(write=True)
    il  = sh.worksheet('Invoice_Log')
    rows = il.get_all_values()

    def _safe(v):
        try:
            return float(str(v).replace(',', '').replace('$', '').strip())
        except Exception:
            return 0.0

    fixes = []
    for i, row in enumerate(rows[2:], start=3):
        if not any(row[:4]):
            continue
        total = _safe(row[5]) if len(row) > 5 else 0.0
        if total <= 0:
            continue

        items     = int(_safe(row[4])) if len(row) > 4 else 0
        provider  = row[2].strip() if len(row) > 2 else ''
        inv_num   = row[1].strip() if len(row) > 1 else ''
        filename  = row[3].strip() if len(row) > 3 else ''
        factor    = 1

        # ONLY fix rows that went through the extractor pipeline (have a .json filename).
        # Manually-entered invoices (insurance, rent, etc.) are left untouched — they
        # can be legitimately large and heuristics would wrongly alter them.
        if not filename.lower().endswith('.json'):
            continue

        # For food/bev invoices: a unit cost > $500 is impossible, so if the
        # total implies that, the decimal was dropped (100x shift).
        # items=0 means we don't know the count — skip to be safe.
        if items > 0 and (total / items) > 500:
            factor = 100
        elif total > 50000:
            factor = 100

        if factor > 1:
            new_total = round(total / factor, 2)
            il.update([[new_total]], f'F{i}', value_input_option='USER_ENTERED')
            fixes.append({
                'row': i, 'provider': provider, 'invoice_number': inv_num,
                'old_total': total, 'new_total': new_total,
            })
            _time.sleep(0.25)   # respect Sheets rate limit

    return fixes


def get_kpis():
    products = get_products()
    invoices = get_invoices()

    total_value = sum(p['total_value'] for p in products)
    out_of_stock = [p for p in products if p['status'] == 'OUT OF STOCK']
    low_stock = [p for p in products if p['status'] == 'LOW STOCK']

    # Items to order: OUT OF STOCK + LOW STOCK
    to_order = out_of_stock + low_stock

    # Invoices this month
    now = datetime.now()
    current_month = now.strftime('%m/%Y')
    invoices_this_month = [
        i for i in invoices
        if i['date'] and len(i['date']) >= 7 and i['date'][3:] == current_month
    ]

    # Categories breakdown
    categories = {}
    for p in products:
        cat = p['category'] or 'Other'
        if cat not in categories:
            categories[cat] = {'count': 0, 'value': 0.0}
        categories[cat]['count'] += 1
        categories[cat]['value'] += p['total_value']

    return {
        'total_products': len(products),
        'total_value': round(total_value, 2),
        'out_of_stock_count': len(out_of_stock),
        'low_stock_count': len(low_stock),
        'to_order_count': len(to_order),
        'invoices_this_month': len(invoices_this_month),
        'invoices_total': len(invoices),
        'categories': categories,
        'last_invoice_date': invoices[-1]['date'] if invoices else '',
    }

SECTION_CATEGORIES = {
    'kitchen': ['kitchen', 'food', 'dairy', 'produce', 'bakery', 'pastry', 'cleaning', 'supplies', 'operations'],
    'bar':     ['bar', 'cafe', 'soft drinks', 'beer', 'wine', 'spirits', 'cider', 'rtd', 'juice', 'water', 'mixers'],
}

def get_categories():
    """Return sorted list of unique non-empty categories from Master_Stock col C."""
    sh   = get_spreadsheet(write=False)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()
    cats = set()
    for row in rows[2:]:
        if len(row) > 2 and row[2].strip() and row[1].strip() and row[1].strip().upper() != 'TOTAL':
            cats.add(row[2].strip())
    return sorted(cats)


def get_products_by_section(section):
    """Return products whose category falls within the given section (kitchen or bar)."""
    allowed = SECTION_CATEGORIES.get(section.lower(), [])
    sh   = get_spreadsheet(write=False)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    def safe_float(val):
        try:
            return float(str(val).replace(',', '').replace('$', '').strip())
        except:
            return 0.0

    products = []
    for i, row in enumerate(rows[2:], start=3):
        if len(row) < 7 or not row[1]:
            continue
        if row[1].strip().upper() == 'TOTAL':
            continue
        if row[2].strip().lower() not in allowed:
            continue
        products.append({
            'id':            row[0].strip(),
            'name':          row[1].strip(),
            'category':      row[2].strip(),
            'provider':      row[3].strip() if len(row) > 3 else '',
            'unit':          row[4].strip() if len(row) > 4 else '',
            'par_level':     safe_float(row[5] if len(row) > 5 else 0),
            'current_stock': safe_float(row[6] if len(row) > 6 else 0),
            'reorder_point': safe_float(row[7] if len(row) > 7 else 0),
            '_row':          i,
        })
    return products


def add_product(name, category, provider, unit, par_level, current_stock, unit_cost):
    """Append a new product row to Master_Stock. Returns the new product dict."""
    sh   = get_spreadsheet(write=True)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    # Generate next ID (P-NNN)
    max_num = 0
    for row in rows[2:]:
        if row[0].strip().startswith('P-'):
            try:
                n = int(row[0].strip()[2:])
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    new_id  = f'P-{max_num + 1:03d}'
    new_row_num = len(rows) + 1  # 1-indexed sheet row

    # Formulas for J (Total Value) and K (Status) — semicolons for AU locale
    total_formula  = f'=G{new_row_num}*I{new_row_num}'
    status_formula = (
        f'=IF(G{new_row_num}=0;"OUT OF STOCK";'
        f'IF(G{new_row_num}<=H{new_row_num};"LOW STOCK";"OK"))'
    )

    ms.append_row(
        [new_id, name, category, provider, unit,
         par_level, current_stock, 0,  # reorder_point defaults to 0
         unit_cost, total_formula, status_formula],
        value_input_option='USER_ENTERED',
    )

    return {
        'id':            new_id,
        'name':          name,
        'category':      category,
        'provider':      provider,
        'unit':          unit,
        'par_level':     float(par_level),
        'current_stock': float(current_stock),
        'reorder_point': 0.0,
        'unit_cost':     float(unit_cost),
        'total_value':   float(current_stock) * float(unit_cost),
        'status':        'OUT OF STOCK' if float(current_stock) == 0 else 'OK',
    }


def update_product_category(product_id, new_category):
    """Update the category (col C) of a product by ID."""
    sh   = get_spreadsheet(write=True)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()
    for i, row in enumerate(rows[2:], start=3):
        if row and row[0].strip() == product_id:
            ms.update([[new_category]], f'C{i}', value_input_option='USER_ENTERED')
            return i
    raise ValueError(f'Product {product_id} not found')


def _ensure_archived_sheet(sh):
    """Return Archived_Stock worksheet, creating it if needed."""
    wss = {ws.title: ws for ws in sh.worksheets()}
    if 'Archived_Stock' not in wss:
        ws = sh.add_worksheet(title='Archived_Stock', rows=500, cols=12)
        ws.append_row(['Product ID', 'Name', 'Category', 'Provider', 'Unit',
                       'Par Level', 'Current Stock', 'Reorder Point', 'Unit Cost',
                       'Total Value', 'Status', 'Archived Date'])
        return ws
    return wss['Archived_Stock']


def delete_product(product_id):
    """Move product row to Archived_Stock instead of permanently deleting."""
    sh   = get_spreadsheet(write=True)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    row_num  = None
    row_data = None
    for i, row in enumerate(rows[2:], start=3):
        if row and row[0].strip() == product_id:
            row_num  = i
            row_data = list(row)
            break

    if row_num is None:
        raise ValueError(f'Product {product_id} not found in Master_Stock')

    # Archive: copy first 11 cols + today's date
    arch = _ensure_archived_sheet(sh)
    today = datetime.now().strftime('%d/%m/%Y')
    archived_row = (row_data + [''] * 12)[:11] + [today]
    arch.append_row(archived_row, value_input_option='USER_ENTERED')

    # Remove from Master_Stock
    ms.delete_rows(row_num)
    return row_num


def get_archived_products():
    """Return list of archived products from Archived_Stock sheet."""
    sh  = get_spreadsheet(write=False)
    wss = {ws.title: ws for ws in sh.worksheets()}
    if 'Archived_Stock' not in wss:
        return []
    rows = wss['Archived_Stock'].get_all_values()
    products = []
    for i, row in enumerate(rows[1:], start=2):   # 1 header row
        if len(row) < 2 or not row[1].strip():
            continue
        products.append({
            'id':            row[0].strip() if row[0] else '',
            'name':          row[1].strip(),
            'category':      row[2].strip() if len(row) > 2 else '',
            'provider':      row[3].strip() if len(row) > 3 else '',
            'unit':          row[4].strip() if len(row) > 4 else '',
            'archived_date': row[11].strip() if len(row) > 11 else '',
            '_row':          i,
        })
    return products


def restore_product(product_id):
    """Move a product from Archived_Stock back to Master_Stock."""
    sh  = get_spreadsheet(write=True)
    wss = {ws.title: ws for ws in sh.worksheets()}
    if 'Archived_Stock' not in wss:
        raise ValueError('Archived_Stock sheet does not exist')

    arch = wss['Archived_Stock']
    rows = arch.get_all_values()

    row_num  = None
    row_data = None
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0].strip() == product_id:
            row_num  = i
            row_data = list(row)
            break

    if row_num is None:
        raise ValueError(f'Product {product_id} not found in Archived_Stock')

    # Restore: append first 11 cols back to Master_Stock
    ms_row = (row_data + [''] * 11)[:11]
    sh.worksheet('Master_Stock').append_row(ms_row, value_input_option='USER_ENTERED')

    # Remove from archive
    arch.delete_rows(row_num)
    return row_num


def get_products_by_category(category):
    """Return products filtered by category, with only fields needed for Stock tool."""
    sh   = get_spreadsheet(write=False)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    def safe_float(val):
        try:
            return float(str(val).replace(',', '').replace('$', '').strip())
        except:
            return 0.0

    products = []
    for i, row in enumerate(rows[2:], start=3):
        if len(row) < 7 or not row[1]:
            continue
        if row[1].strip().upper() == 'TOTAL':
            continue
        if row[2].strip().lower() != category.strip().lower():
            continue
        products.append({
            'id':            row[0].strip(),
            'name':          row[1].strip(),
            'category':      row[2].strip(),
            'provider':      row[3].strip() if len(row) > 3 else '',
            'unit':          row[4].strip() if len(row) > 4 else '',
            'par_level':     safe_float(row[5] if len(row) > 5 else 0),
            'current_stock': safe_float(row[6] if len(row) > 6 else 0),
            'reorder_point': safe_float(row[7] if len(row) > 7 else 0),
            '_row':          i,   # sheet row number, used for batch update
        })
    return products


def batch_update_stock(updates):
    """
    Save par_level + current_stock for multiple products in one Sheets API call.
    updates = [{'id': 'P-101', 'par_level': 5, 'current_stock': 3}, ...]
    Returns number of rows updated.
    """
    sh   = get_spreadsheet(write=True)
    ms   = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    # Build id → row_number map
    id_to_row = {}
    for i, row in enumerate(rows[2:], start=3):
        if row[0].strip():
            id_to_row[row[0].strip()] = i

    cell_updates = []
    updated = 0
    for u in updates:
        pid = u.get('id', '').strip()
        if pid not in id_to_row:
            continue
        r = id_to_row[pid]
        cell_updates.append({'range': f'F{r}', 'values': [[u['par_level']]]})
        cell_updates.append({'range': f'G{r}', 'values': [[u['current_stock']]]})
        updated += 1

    if cell_updates:
        ms.batch_update(cell_updates, value_input_option='USER_ENTERED')

    return updated


# Master_Stock columns: F=5 Par Level, G=6 Current Stock, H=7 Reorder Point
def update_product(product_id, current_stock, par_level, reorder_point):
    """Find product row by ID (col A) and update stock fields."""
    sh = get_spreadsheet(write=True)
    ms = sh.worksheet('Master_Stock')
    rows = ms.get_all_values()

    row_num = None
    for i, row in enumerate(rows[2:], start=3):
        if row[0].strip() == product_id:
            row_num = i
            break

    if row_num is None:
        raise ValueError(f'Product {product_id} not found in Master_Stock')

    ms.batch_update([
        {'range': f'F{row_num}', 'values': [[par_level]]},
        {'range': f'G{row_num}', 'values': [[current_stock]]},
        {'range': f'H{row_num}', 'values': [[reorder_point]]},
    ], value_input_option='USER_ENTERED')

    return row_num


# ── MENU ─────────────────────────────────────────────────────────────────────
# Menu_Items columns (0-indexed):
# A=0 Dish ID, B=1 Dish Name, C=2 Category, D=3 Active, E=4 Notes
#
# Menu_Ingredients columns (0-indexed):
# A=0 Dish ID, B=1 Product ID, C=2 Ingredient Name,
# D=3 Qty Needed, E=4 Unit, F=5 Optional

def _menu_safe_float(val):
    try:
        return float(str(val).replace(',', '').strip())
    except:
        return 0.0


def _load_menu_sheets():
    """Open spreadsheet and return (mi_rows, ming_rows, ms_rows) in one session."""
    sh  = get_spreadsheet(write=False)
    wss = {ws.title: ws for ws in sh.worksheets()}
    for name in ('Menu_Items', 'Menu_Ingredients', 'Master_Stock'):
        if name not in wss:
            raise ValueError(
                f'Sheet "{name}" not found. '
                'Run: python webapp/create_menu_sheets.py'
            )
    mi_rows   = wss['Menu_Items'].get_all_values()
    ming_rows = wss['Menu_Ingredients'].get_all_values()
    ms_rows   = wss['Master_Stock'].get_all_values()
    return mi_rows, ming_rows, ms_rows


def _build_product_lookup(ms_rows):
    """Return dict {product_id: {...}} from Master_Stock rows."""
    products = {}
    def sf(v): return _menu_safe_float(v)
    for row in ms_rows[2:]:                     # skip 2 header rows
        if len(row) < 7 or not row[0].strip():
            continue
        if row[1].strip().upper() == 'TOTAL':
            continue
        pid = row[0].strip()
        cur = sf(row[6] if len(row) > 6 else 0)
        reo = sf(row[7] if len(row) > 7 else 0)
        raw_status = row[10].strip() if len(row) > 10 else ''
        if raw_status in ('OUT OF STOCK', 'LOW STOCK', 'OK'):
            status = raw_status
        elif cur == 0:
            status = 'OUT OF STOCK'
        elif cur <= reo:
            status = 'LOW STOCK'
        else:
            status = 'OK'
        products[pid] = {
            'name':          row[1].strip(),
            'unit':          row[4].strip() if len(row) > 4 else '',
            'par_level':     sf(row[5] if len(row) > 5 else 0),
            'current_stock': cur,
            'reorder_point': reo,
            'status':        status,
        }
    return products


def _parse_dish_row(row):
    if len(row) < 2 or not row[0].strip() or not row[1].strip():
        return None
    return {
        'id':       row[0].strip(),
        'name':     row[1].strip(),
        'category': row[2].strip() if len(row) > 2 else '',
        'active':   row[3].strip().upper() in ('TRUE', '1', 'YES') if len(row) > 3 else True,
        'notes':    row[4].strip() if len(row) > 4 else '',
    }


def _worst_status(statuses):
    if 'OUT OF STOCK' in statuses:
        return 'OUT OF STOCK'
    if 'LOW STOCK' in statuses:
        return 'LOW STOCK'
    return 'OK'


def _calculate_can_make(ingredients):
    """Return (can_make_int_or_None, limiting_ingredient_name_or_None)."""
    min_portions   = None
    limiting_name  = None
    for ing in ingredients:
        if ing.get('optional'):
            continue
        qty = ing.get('qty_needed', 0)
        if not qty or qty <= 0:
            continue
        stock    = ing.get('current_stock', 0) or 0
        possible = int(stock / qty)
        if min_portions is None or possible < min_portions:
            min_portions  = possible
            limiting_name = ing.get('ingredient_name', '')
    return min_portions, limiting_name


def get_menu_items():
    """Return all active dishes with a computed status field."""
    mi_rows, ming_rows, ms_rows = _load_menu_sheets()
    products = _build_product_lookup(ms_rows)

    # Build required-ingredient status per dish
    required_by_dish = {}   # dish_id → [product_id, ...]
    for row in ming_rows[1:]:
        if len(row) < 2 or not row[0].strip():
            continue
        did  = row[0].strip()
        pid  = row[1].strip()
        opt  = row[5].strip().upper() == 'TRUE' if len(row) > 5 else False
        if not opt:
            required_by_dish.setdefault(did, []).append(pid)

    dishes = []
    for row in mi_rows[1:]:
        dish = _parse_dish_row(row)
        if not dish or not dish['active']:
            continue
        pids = required_by_dish.get(dish['id'], [])
        if not pids:
            dish['status'] = 'N/A'
        else:
            statuses = [products.get(p, {}).get('status', 'OK') for p in pids]
            dish['status'] = _worst_status(statuses)
        dishes.append(dish)
    return dishes


def get_menu_item_detail(dish_id):
    """Return one dish with full ingredient list (joined with Master_Stock) + can_make."""
    mi_rows, ming_rows, ms_rows = _load_menu_sheets()
    products = _build_product_lookup(ms_rows)

    # Find dish
    dish = None
    for row in mi_rows[1:]:
        d = _parse_dish_row(row)
        if d and d['id'] == dish_id:
            dish = d
            break
    if dish is None:
        raise ValueError(f'Dish {dish_id!r} not found in Menu_Items')

    # Build ingredients
    ingredients = []
    for row in ming_rows[1:]:
        if len(row) < 2 or not row[0].strip():
            continue
        if row[0].strip() != dish_id:
            continue
        pid  = row[1].strip()
        name = row[2].strip() if len(row) > 2 else ''
        qty  = _menu_safe_float(row[3] if len(row) > 3 else 0)
        unit = row[4].strip() if len(row) > 4 else ''
        opt  = row[5].strip().upper() == 'TRUE' if len(row) > 5 else False

        prod = products.get(pid, {})
        ingredients.append({
            'product_id':      pid,
            'ingredient_name': name,
            'qty_needed':      qty,
            'unit':            unit,
            'current_stock':   prod.get('current_stock', 0),
            'par_level':       prod.get('par_level', 0),
            'reorder_point':   prod.get('reorder_point', 0),
            'status':          prod.get('status', 'N/A') if pid in products else 'N/A',
            'optional':        opt,
        })

    can_make, limiting = _calculate_can_make(ingredients)
    return {
        **dish,
        'ingredients':        ingredients,
        'can_make':           can_make,       # int or None
        'limiting_ingredient': limiting,
    }


def add_menu_item(name, category, notes=''):
    """Append a new dish to Menu_Items. Returns the new dish dict."""
    sh  = get_spreadsheet(write=True)
    wss = {ws.title: ws for ws in sh.worksheets()}
    mi  = wss['Menu_Items']
    rows = mi.get_all_values()

    # Generate next D-NNN id
    max_num = 0
    for row in rows[1:]:
        if row[0].strip().startswith('D-'):
            try:
                n = int(row[0].strip()[2:])
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    new_id = f'D-{max_num + 1:03d}'
    mi.append_row([new_id, name, category, 'TRUE', notes],
                  value_input_option='USER_ENTERED')
    return {'id': new_id, 'name': name, 'category': category,
            'active': True, 'notes': notes, 'status': 'N/A'}


def add_menu_ingredient(dish_id, product_id, ingredient_name, qty_needed, unit, optional=False):
    """Link an ingredient to a dish in Menu_Ingredients."""
    sh   = get_spreadsheet(write=True)
    wss  = {ws.title: ws for ws in sh.worksheets()}
    ming = wss['Menu_Ingredients']
    ming.append_row(
        [dish_id, product_id, ingredient_name,
         qty_needed, unit, 'TRUE' if optional else 'FALSE'],
        value_input_option='USER_ENTERED'
    )


def delete_menu_ingredient(dish_id, product_id):
    """Remove ingredient row matching dish_id + product_id from Menu_Ingredients."""
    sh   = get_spreadsheet(write=True)
    wss  = {ws.title: ws for ws in sh.worksheets()}
    ming = wss['Menu_Ingredients']
    rows = ming.get_all_values()

    row_num = None
    for i, row in enumerate(rows[1:], start=2):
        if row[0].strip() == dish_id and row[1].strip() == product_id:
            row_num = i
            break
    if row_num is None:
        raise ValueError(f'Ingredient {product_id!r} not found for dish {dish_id!r}')
    ming.delete_rows(row_num)
    return row_num
