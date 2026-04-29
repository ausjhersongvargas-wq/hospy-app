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

    invoices = []
    for row in rows[2:]:  # skip 2 header rows
        if not row[0] and not row[1]:
            continue

        def safe_float(val):
            try:
                return float(str(val).replace(',', '').replace('$', '').strip())
            except:
                return 0.0

        invoices.append({
            'date': row[0].strip() if row[0] else '',
            'invoice_number': row[1].strip() if len(row) > 1 else '',
            'provider': row[2].strip() if len(row) > 2 else '',
            'filename': row[3].strip() if len(row) > 3 else '',
            'items': int(safe_float(row[4])) if len(row) > 4 else 0,
            'total': safe_float(row[5]) if len(row) > 5 else 0.0,
            'status': row[6].strip() if len(row) > 6 else '',
        })

    return invoices

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
