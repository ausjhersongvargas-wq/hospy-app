"""
One-time setup script — creates Menu_Items and Menu_Ingredients sheets.

Run once from the webapp folder:
    cd C:/Users/ausjh/Demos/hospy/webapp
    python create_menu_sheets.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sheets import get_spreadsheet

def create_menu_sheets():
    sh  = get_spreadsheet(write=True)
    existing = [ws.title for ws in sh.worksheets()]

    # ── Menu_Items ──────────────────────────────────────────────────────────
    if 'Menu_Items' not in existing:
        ws = sh.add_worksheet(title='Menu_Items', rows=200, cols=6)
        ws.append_row(['Dish ID', 'Dish Name', 'Category', 'Active', 'Notes'])
        ws.append_row(['D-001', 'Grilled Chicken',       'Main',  'TRUE', 'Kitchen menu item'])
        ws.append_row(['D-002', 'South American Paella', 'Main',  'TRUE', 'Signature dish'])
        ws.append_row(['D-003', 'Empanadas',             'Tapas', 'TRUE', 'Serve of 3'])
        print('✓ Created Menu_Items with 3 example dishes')
    else:
        print('— Menu_Items already exists, skipped')

    # ── Menu_Ingredients ────────────────────────────────────────────────────
    if 'Menu_Ingredients' not in existing:
        ws = sh.add_worksheet(title='Menu_Ingredients', rows=500, cols=7)
        ws.append_row(['Dish ID', 'Product ID', 'Ingredient Name', 'Qty Needed', 'Unit', 'Optional'])
        print('✓ Created Menu_Ingredients (empty — add ingredients via app or directly in Sheet)')
    else:
        print('— Menu_Ingredients already exists, skipped')

    print('\nDone. Open the Google Sheet to fill in ingredients using real Product IDs from Master_Stock.')

if __name__ == '__main__':
    create_menu_sheets()
