"""
Populates Menu_Items from both Cumbia menus (Breakfast + Lunch/Dinner).
Creates Menu_Items and Menu_Ingredients sheets if they don't exist.
Clears any existing dish rows before inserting.

Run from webapp folder:
    cd C:/Users/ausjh/Demos/hospy/webapp
    python populate_menu.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sheets import get_spreadsheet

# ── DISH DATA ────────────────────────────────────────────────────────────────
# Format: [Dish ID, Dish Name, Category, Active, Notes]

BREAKFAST_DISHES = [
    # ── Breakfast mains ──
    ['D-001', 'Cumbia Breakfast',              'Breakfast',       'TRUE', 'gf, veg · Poached eggs on cornbread with smashed avo & grilled tomatoes'],
    ['D-002', 'Vegetarian Breakfast',          'Breakfast',       'TRUE', 'gf, veg · Fried eggs, haloumi, beans, mushroom, grilled tomato, cornbread'],
    ['D-003', 'Eggs Benedict',                 'Breakfast',       'TRUE', 'gf · Poached eggs, bacon, mushroom, tomato, cornbread, hollandaise'],
    ['D-004', 'Scrambled Eggs',                'Breakfast',       'TRUE', 'gf, veg · Cornbread topped with free range scrambled eggs'],
    ['D-005', 'Bacon & Eggs',                  'Breakfast',       'TRUE', 'Fried eggs and bacon with sourdough bread'],
    ['D-006', 'Haloumi Stack',                 'Breakfast',       'TRUE', 'gf · Grilled haloumi, poached eggs on corn fritters with hollandaise'],
    ['D-007', 'Empanadas (Breakfast)',         'Breakfast',       'TRUE', 'gf · 3x serve — cheese, beef, chicken'],
    ['D-008', 'Big Breakfast',                 'Breakfast',       'TRUE', 'Fried eggs, bacon, beans ragout, cherry tomatoes, mushrooms, toast'],
    ['D-009', 'Seaside',                       'Breakfast',       'TRUE', 'gf · Crab meat with soft scrambled eggs over homemade cornbread'],
    ['D-010', 'South American Breakfast Bowl', 'Breakfast',       'TRUE', 'gf · Fried eggs, grilled chorizo, rice, beans, tomato salsa, grilled arepa'],
    ['D-011', 'Bacon & Egg Roll',              'Breakfast',       'TRUE', 'Classic roll'],
    ['D-012', 'Corn Fritters',                 'Breakfast',       'TRUE', 'Smoked salmon, rocket, poached egg, hollandaise'],
    ['D-013', 'Ham & Cheese Fritters',         'Breakfast',       'TRUE', ''],
    ['D-014', 'Granola',                       'Breakfast',       'TRUE', 'gf, veg · Almond milk, seasonal fruit'],
    # ── Breakfast arepas ──
    ['D-015', 'Arepa Pollo',                   'Breakfast Arepa', 'TRUE', 'gf · Grilled chicken, salsa criolla, sour cream'],
    ['D-016', 'Arepa Belly',                   'Breakfast Arepa', 'TRUE', 'gf · Smashed avocado, pork belly, spiced salsa'],
    ['D-017', 'Arepa Vegio',                   'Breakfast Arepa', 'TRUE', 'gf, veg · Roasted pumpkin, feta, rocket, pomegranate syrup'],
    ['D-018', 'Arepa con Guacamole',           'Breakfast Arepa', 'TRUE', 'gf, veg · Guacamole, feta cheese, crispy potato'],
    ['D-019', 'Arepa Aprawns',                 'Breakfast Arepa', 'TRUE', 'gf · Guacamole, garlic prawns, crispy potatoes, citrus salsa'],
]

LUNCH_DISHES = [
    # ── Shared Plates / Tapas ──
    ['D-020', 'Empanadas',                     'Tapas',    'TRUE', 'gf · Serve of 3, various fillings'],
    ['D-021', 'Corn Ribs',                     'Tapas',    'TRUE', 'veg, gf · Latin spices, roasted garlic aioli, feta, pickled jalapeno'],
    ['D-022', 'Brazilian Meat Balls (Kibes)',  'Tapas',    'TRUE', 'Free range pork, SA spices, criolla sauce & fresh bread'],
    ['D-023', 'Nachos',                        'Tapas',    'TRUE', 'veg, gf · Bean ragout, guacamole, jalapeno, sour cream, tomato salsa'],
    ['D-024', 'Patatas Bravas',                'Tapas',    'TRUE', 'veg, gf, df · Roasted potatoes, criolla sauce & chipotle mayo'],
    ['D-025', 'Lamb Skewers',                  'Tapas',    'TRUE', 'gf, df · Grilled lamb, butter bean purée, chimichurri, smoked paprika'],
    ['D-026', 'Roasted Broccoli',              'Tapas',    'TRUE', 'gf, veg · Butter bean purée, toasted sesame oil, crushed pistachios'],
    ['D-027', 'Halloumi Brushchetta',          'Tapas',    'TRUE', 'gf, veg · Grilled haloumi, chopped veg, balsamic glaze, honey'],
    ['D-028', 'Peruvian Ceviche',              'Tapas',    'TRUE', "gf, df · SA king fish, citrus juice, aji amarillo, leche de tigre"],
    ['D-029', 'Grilled Calamari',              'Tapas',    'TRUE', 'gf, df · Local squid, lemon, chilli oil, KI honey'],
    ['D-030', 'Shark Bay Scallops — Nikkei',   'Tapas',    'TRUE', 'gf · Wakame, crisp prosciutto, wasabi aioli'],
    ['D-031', 'Shark Bay Scallops — Lima',     'Tapas',    'TRUE', "gf · Cream sauce, spicy 'nduja, parsley & lemon"],
    ['D-032', "Black Mussels — Buenos Aires",  'Tapas',    'TRUE', 'White wine, butter, oregano & parsley, served with bread'],
    ['D-033', 'Black Mussels — Peruvian',      'Tapas',    'TRUE', 'White wine, garlic, coconut cream, rocoto chilli, served with bread'],
    ['D-034', "Black Mussels — Fusion",        'Tapas',    'TRUE', "Cream sauce, spicy 'nduja, red onion, white wine, served with bread"],
    # ── Main Fare ──
    ['D-035', 'South American Paella',         'Main',     'TRUE', 'gf · Saffron rice, chorizo, chicken, SA herbs & spices'],
    ['D-036', 'Deluxe Paella',                 'Main',     'TRUE', 'gf · Chicken, Adelaide Hills chorizo, local prawns, Port Lincoln mussels'],
    ['D-037', 'Chilli Crabs & Prawns',         'Main',     'TRUE', 'Crab meat & prawns, aji amarillo, Peruvian chilli sauce, linguine'],
    ['D-038', 'Pork Belly',                    'Main',     'TRUE', 'gf · Oven roasted free range pork belly, butter bean purée, bbq sauce'],
    ['D-039', 'Argentinian Steak',             'Main',     'TRUE', 'gf · 400g grain fed scotch fillet, Latin spices, chimichurri'],
    ['D-040', 'Burrito Bowl',                  'Main',     'TRUE', 'gf · Peruvian grilled chicken, avocado, tomatoes, rice, beans, corn chips'],
    ['D-041', 'Fresh Seafood Chowder',         'Main',     'TRUE', 'Local seafood, coconut milk, rocoto chilli, served with rice'],
    ['D-042', 'Grilled Chicken',               'Main',     'TRUE', 'gf · Peruvian marinated free range leg fillet, salsa verde, potatoes'],
    ['D-043', 'Mexicana Bowl',                 'Main',     'TRUE', 'gf, veg · Mixed beans, rice, avocado, macadamian feta, jalapeno, fresh corn'],
    ['D-044', 'Lomo Saltado',                  'Main',     'TRUE', 'Peruvian beef stir-fry, onions, tomatoes, soy sauce, fluffy rice'],
    # ── Arepas ──
    ['D-045', 'Arepa Pollo',                   'Arepa',    'TRUE', 'gf · Grilled chicken, salsa criolla, sour cream'],
    ['D-046', 'Arepa Belly',                   'Arepa',    'TRUE', 'gf · Smashed avocado, pork belly, spiced salsa'],
    ['D-047', 'Arepa Vegio',                   'Arepa',    'TRUE', 'gf, veg · Roasted pumpkin, feta, pomegranate syrup'],
    ['D-048', 'Arepa Guacamole',               'Arepa',    'TRUE', 'gf, veg · Guacamole, feta cheese, crispy potatoes'],
    ['D-049', 'Arepa Prawns',                  'Arepa',    'TRUE', 'gf · Guacamole, SA king prawns, crushed potatoes, citrus dressing'],
    # ── Sides ──
    ['D-050', 'Sourdough Bread',               'Side',     'TRUE', 'House made dukkah, olive oil & aged balsamic glaze'],
    ['D-051', 'Green Salad',                   'Side',     'TRUE', 'veg, gf'],
    ['D-052', 'Grilled Arepa',                 'Side',     'TRUE', 'gf · Serve of 2 — Colombian grilled cheese bread'],
    ['D-053', 'Fried Potato',                  'Side',     'TRUE', 'With chipotle mayo'],
    # ── Desserts ──
    ['D-054', 'Churros with Dulce de Leche',   'Dessert',  'TRUE', ''],
    ['D-055', 'Pecan Pie',                     'Dessert',  'TRUE', ''],
    ['D-056', 'Cheese Pastel with KI Honey',   'Dessert',  'TRUE', 'gf'],
    ['D-057', 'Flourless Lemon & White Choc Cake', 'Dessert', 'TRUE', 'gf'],
    ['D-058', 'Guava & Caramel Pie',           'Dessert',  'TRUE', ''],
]

ALL_DISHES = BREAKFAST_DISHES + LUNCH_DISHES

# ── MAIN ─────────────────────────────────────────────────────────────────────
def populate():
    sh  = get_spreadsheet(write=True)
    wss = {ws.title: ws for ws in sh.worksheets()}

    # Create Menu_Items if missing
    if 'Menu_Items' not in wss:
        mi = sh.add_worksheet(title='Menu_Items', rows=300, cols=6)
        print('Created Menu_Items sheet')
    else:
        mi = wss['Menu_Items']
        print('Menu_Items already exists — clearing dish rows...')

    # Create Menu_Ingredients if missing
    if 'Menu_Ingredients' not in wss:
        sh.add_worksheet(title='Menu_Ingredients', rows=1000, cols=7)
        wss2 = {ws.title: ws for ws in sh.worksheets()}
        ming = wss2['Menu_Ingredients']
        ming.append_row(['Dish ID', 'Product ID', 'Ingredient Name', 'Qty Needed', 'Unit', 'Optional'])
        print('Created Menu_Ingredients sheet')
    else:
        print('Menu_Ingredients already exists — skipped')

    # Clear existing data (keep row 1 as header)
    existing = mi.get_all_values()
    if len(existing) > 1:
        mi.delete_rows(2, len(existing))
        print(f'Cleared {len(existing) - 1} existing rows')

    # Write header if sheet was empty
    if not existing:
        mi.append_row(['Dish ID', 'Dish Name', 'Category', 'Active', 'Notes'])

    # Insert all dishes in one batch
    mi.append_rows(ALL_DISHES, value_input_option='USER_ENTERED')

    print(f'\n✓ Added {len(ALL_DISHES)} dishes:')
    print(f'  · {len(BREAKFAST_DISHES)} breakfast dishes (D-001 to D-019)')
    print(f'  · {len(LUNCH_DISHES)} lunch/dinner dishes (D-020 to D-058)')
    print(f'\nCategories added:')
    cats = {}
    for d in ALL_DISHES:
        cats[d[2]] = cats.get(d[2], 0) + 1
    for cat, count in sorted(cats.items()):
        print(f'  · {cat}: {count} dishes')
    print('\nDone. Open the app and go to Tools → Kitchen → Menu to see the dishes.')
    print('Add ingredients via Google Sheet Menu_Ingredients using Product IDs from Master_Stock.')

if __name__ == '__main__':
    populate()
