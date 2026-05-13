# HOSPY PROJECT STATE - Restoration Document
Last Updated: 2026-04-30

## 🎯 Core Concept
Hospy es una consultora de hospitalidad en Adelaide & South Australia enfocada en
profesionalizar operaciones (Stock, Kitchen, Bar, Operations, Content) usando Claude AI
como motor interno para resultados más rápidos y de alta calidad.

**Cliente activo:** Cumbia Bar & Kitchen, Adelaide SA

---

## 🏗️ Technical Architecture
- **Location:** `C:\Users\ausjh\Demos\hospy\`
- **Core Engine:** Python + Claude AI (claude-sonnet-4-5) para extracción de PDFs
- **Storage:** Google Sheets como base de datos principal
- **Spreadsheet ID:** `10RxL-POJ-lJRMYXoSEq4TdUllcg4mw3WnKMLLhNowM8`
- **Gmail Auth:** OAuth2 con Refresh Token (info@cumbia.com.au)
- **Web App:** Flask + Jinja2 + Vanilla JS (single-page app)
- **Deploy:** Railway → https://hospy.up.railway.app

---

## 📁 File Structure
```
hospy/
├── config/
│   ├── .env.txt                          # ANTHROPIC_API_KEY
│   ├── gmail_token.json                  # OAuth2 refresh token
│   ├── oauth_credentials.json            # OAuth2 client credentials
│   └── spartan-perigee-494417-f5-...json # Google Service Account (Sheets)
├── stock/
│   ├── inbox/                            # PDFs descargados de Gmail
│   │   └── processed/                   # JSONs extraídos por Claude AI
│   ├── local_downloader.py              # Gmail → inbox/ (OAuth2)
│   ├── extractor.py                     # PDF → JSON via Claude AI
│   ├── sync_to_sheets.py               # JSON → Google Sheets
│   ├── run_all.py                       # Ejecuta los 3 scripts en secuencia
│   ├── run_hospy.bat                    # Ejecutable para Task Scheduler
│   ├── expand_stock.py                  # Agrega productos nuevos al Master Stock
│   ├── check_dupes.py                   # Verifica duplicados en Master Stock
│   ├── fix_total.py                     # Mueve fila TOTAL al final
│   └── hospy_log.txt                    # Log automático de ejecuciones
├── webapp/
│   ├── app.py                           # Flask routes + auth
│   ├── sheets.py                        # Google Sheets data layer
│   └── templates/
│       ├── index.html                   # Single-page app (1 archivo ~2100 líneas)
│       └── login.html                   # Página de login
├── Procfile                             # gunicorn para Railway
├── railway.toml                         # Config de deploy
├── requirements.txt                     # Dependencias Python
├── .gitignore                           # Excluye credentials, PDFs, logs
└── HOSPY_STATE.md                       # Este archivo
```

---

## 🌐 Web App — Estado Actual

### Login
- Usuario: `hospy` / Contraseña: `cumbia2024` (override via env var en Railway)
- Session-based auth con `@login_required` decorator
- Paleta: teal `#2A8E9D`, coral `#FF5245`, navy `#374050`, yellow `#FFC938`, fondo blanco

### 4 Tabs:

**1. Dashboard**
- KPIs en vivo: Total Value, Out of Stock, Low Stock, To Order, Invoices this month
- Categorías breakdown con valores
- Botón REFRESH para actualizar datos

**2. Products (Master Stock)**
- Tabla completa de productos: nombre, categoría, proveedor, stock, reorder, costo, valor, status
- Search, filtro por categoría, filtro por status (OK / LOW STOCK / OUT OF STOCK)
- Sort por cualquier columna
- Click en producto → Edit Drawer con steppers para Current Stock, Par Level, Reorder Point
- Guarda directo en Google Sheet

**3. Invoices**
- Lista de facturas del Invoice_Log
- Click en factura → abre el PDF en el browser (sirve el archivo local)
- Filtros por estado y proveedor

**4. Tools → Stock Tool**
- Selección de sección: Kitchen o Bar
- Lista de productos agrupados por sub-categoría con headers
- Filter chips por categoría (aparecen cuando hay múltiples sub-categorías)
- Inputs Par y Stock para editar rápidamente
- Botón **`+ Add`** → drawer para agregar producto nuevo
  - Nombre, categoría (dropdown con existentes + campo para nueva categoría)
  - Proveedor, unidad, par level, stock actual, costo
  - Guarda en Google Sheet con ID auto-generado (P-NNN)
- Botón **`×`** en cada producto → confirmación → borra fila del Sheet
- Botón **Generate Order** → guarda cambios en Sheet → muestra lista de items a pedir
- Botón **Copy to clipboard** → copia el orden agrupado por proveedor

---

## 📦 Google Sheets Structure

**5 hojas:**
- `Master_Stock` — ~83 productos únicos
  - Columnas: A=ID, B=Name, C=Category, D=Provider, E=Unit,
    F=Par Level, G=Current Stock, H=Reorder Point, I=Unit Cost, J=Total Value, K=Status
  - Fórmulas en J y K usan **punto y coma** (locale australiana)
  - Status fórmula: `=IF(G3=0;"OUT OF STOCK";IF(G3<=H3;"LOW STOCK";"OK"))`
- `Invoice_Log` — 54+ facturas procesadas
- `Daily_Order` — calcula cantidades a pedir (fórmulas con punto y coma)
- `Waste_Tracker` — registro manual
- `Dashboard` — KPIs con COUNTIF expandido a K3:K500

---

## 🔄 Invoice Processing Flow
```
Factura PDF llega a info@cumbia.com.au
→ python run_all.py   (o doble click en run_hospy.bat)
→ local_downloader.py  (descarga PDFs, últimos 30 días)
→ extractor.py         (Claude AI extrae datos, evita duplicados por Invoice#)
→ sync_to_sheets.py    (actualiza Master_Stock + Invoice_Log)
```

**Ejecutar manualmente:**
```cmd
cd C:\Users\ausjh\Demos\hospy\stock
python run_all.py
```

**Proveedores bloqueados (internos):**
- `cumbianas`, `cumbia` → skip automático en extractor, sync y expand

---

## ⚙️ Flask Web App — Rutas API

| Método | Ruta | Función |
|--------|------|---------|
| GET | `/` | Dashboard (index.html) |
| GET/POST | `/login` | Login |
| GET | `/logout` | Logout |
| GET | `/api/kpis` | KPIs aggregados |
| GET | `/api/products` | Lista completa de productos |
| GET | `/api/invoices` | Lista de facturas |
| POST | `/api/products/update` | Actualiza stock/par/reorder de 1 producto |
| POST | `/api/products/add` | Agrega producto nuevo al Sheet |
| POST | `/api/products/delete` | Borra producto del Sheet |
| GET | `/api/categories` | Lista de categorías únicas |
| GET | `/api/stock-tool/section/<section>` | Productos por sección (kitchen/bar) |
| POST | `/api/stock-tool/save` | Guarda par+stock de múltiples productos |
| GET | `/invoice/<filename>` | Sirve PDF de invoice |

---

## 🔑 Seguridad
- Credentials en `config/` → excluidos de git por `.gitignore`
- Google Sheets credentials en Railway como variable `GOOGLE_CREDENTIALS_B64` (base64)
- `APP_PASSWORD` en Railway como variable de entorno
- Debug mode OFF en producción (lee `FLASK_DEBUG` env var)
- Path traversal protection en `/invoice/<filename>`
- Headers `Cache-Control: no-store` en todas las respuestas

---

## 🚀 Deploy en Railway
- URL: https://hospy.up.railway.app
- **Para deployar cambios:**
  ```cmd
  cd C:\Users\ausjh\Demos\hospy
  git add -A
  git commit -m "descripción del cambio"
  git push
  ```
- Railway redeploya automáticamente en ~2 minutos

---

## 🏪 Proveedores Activos
Paramount Liquor, Nievole Distributors, Options Wine Merchants, Siena Foods,
Bidfood, International Oyster & Seafoods, Eustralis Food SA, Chesser Chemicals,
Packaging Specialists, OG Rolls Bakery, Skala Trading, Bleasdale Vineyards

---

## ✅ Completado
- [x] OAuth2 Gmail con info@cumbia.com.au
- [x] Pipeline de invoices: download → extract → sync (Claude AI)
- [x] Task Scheduler (8:00 AM diario en PC local)
- [x] Anti-duplicados por Invoice Number
- [x] Google Sheet con 5 hojas y fórmulas automáticas
- [x] Fórmulas corregidas para locale australiana (punto y coma)
- [x] Productos de Cumbianas (catering interno) bloqueados
- [x] **Web App completa desplegada en Railway**
- [x] Login/logout con sesión
- [x] Tab Dashboard con KPIs en vivo
- [x] Tab Products con Master Stock (search, filter, sort, edit drawer)
- [x] Tab Invoices con PDF viewer (click para abrir PDF)
- [x] Tab Tools → Stock Tool
- [x] Stock Tool: secciones Kitchen y Bar
- [x] Stock Tool: grupos por categoría + filter chips
- [x] Stock Tool: agregar producto nuevo (drawer con auto-ID)
- [x] Stock Tool: borrar producto (con confirmación)
- [x] Stock Tool: Generate Order + Copy to clipboard
- [x] Seguridad auditada antes del deploy
- [x] Headers no-cache en respuestas Flask

---

## ⚠️ Pendientes Inmediatos
- [ ] **Deploy pendiente:** los últimos cambios (Stock Tool v2) están solo en local — hacer `git push`
- [ ] **Soft Drinks faltantes:** Coca Cola, Sprite y otros de Bidfood no están en Master Stock → agregarlos via Tools → Stock → Bar → `+ Add` (categoría: `Soft Drinks`)
- [ ] Completar Par Level y Stock actual de productos con valores en 0

## 📋 Pendientes Futuros
- [ ] Mover pipeline de invoices a la nube (actualmente depende de la PC local)
- [ ] Mejorar matching de productos en sync (fuzzy matching)
- [ ] Kitchen flow: recipe cards, prep lists
- [ ] Bar flow: drinks recipes, mise en place
- [ ] Reportes de waste y costo por plato

---

## 🆘 How to Restore this Session
Proporcioná este archivo al AI y decí:
**"Restore Hospy project state. Continuamos con el desarrollo."**

## 💻 Correr en Local
```cmd
cd C:\Users\ausjh\Demos\hospy\webapp
python app.py
```
Luego abrir: http://127.0.0.1:5000

## 📧 Correr pipeline de invoices
```cmd
cd C:\Users\ausjh\Demos\hospy\stock
python run_all.py
```
