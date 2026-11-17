# PolarOps

PolarOps is an expedition logistics and asset management application for polar and high-altitude missions. It brings expedition readiness, personnel, supply, transport, equipment custody, emergency response and audit history into a role-aware operations console.

## Run locally

Python 3.12 is the supported deployment runtime. The current development environment uses Python 3.14.

~~~sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_polarops
python manage.py test
python manage.py check
python manage.py runserver
~~~

Open <http://127.0.0.1:8000/>. SQLite is used by default. The database file is db.sqlite3; persistent QR images are stored in media/asset_qr/.

### Demo logins

All demo accounts use the password PolarOps-2026!

| Role | Username |
|---|---|
| Administrator | administrator |
| Expedition Leader | expedition_leader |
| Logistics Officer | logistics_officer |
| Field Member with assigned expedition | field_member |
| Additional assigned field roster | field01 through field11 |

The `seed_polarops` command is repeatable. **Every bundled person, expedition, route, reading, alert and inventory balance is simulated demonstration data**; coordinates identify real regional reference locations, but operational details are fictional. It creates three distinct expeditions, 43 region-coded assets, regional stock, personnel, transport plans, risk assessments, contingency plans, SOS events, and alerts. Assets receive persistent QR images at creation. To refresh tags after changing the public URL, set POLAROPS_PUBLIC_URL and run:

~~~sh
python manage.py generate_asset_qr --force
~~~

### Simulated regional scenarios

| Expedition | Location and operating conditions | Distinct equipment and supplies | Seeded baseline |
|---|---|---|---|
| McMurdo–South Pole Traverse | McMurdo, Antarctica (-77.8419, 166.6863), simulated December–February traverse toward the plateau; -28°C, 38 km/h wind and 24-hour summer daylight | Tracked tractors, cargo sleds, ice coring and GPR, satellite/HF communications; high-calorie rations, JP-8 and diesel, cold-chain trauma kits, generator spares | 5 people, 68 days, 15 assets; GO baseline; overdue cold-region machinery and a low spare-parts balance |
| Ny-Ålesund Polar Night Observatory | Svalbard (78.9230, 11.9230), simulated polar-night field season; -18°C, 62 km/h wind, low visibility and 0.3 hours daylight; polar-bear watch | Snowmobiles, ice-edge boats, bear deterrents, weather mast and sea-ice kits; marine diesel, flares/ammunition, desalination cartridges and preserved-sample stock | 4 people, 100 days, 14 assets; CAUTION baseline; low flare/sample stock, a cold-chain breach and an expiring polar-survival certification |
| Everest Base Camp High-Altitude Relay | Everest Base Camp region (28.0043, 86.8528), near 5,300 m; -19°C, 92 km/h wind and a 4.5-hour daylight window | Oxygen systems, storm tents, solar/battery equipment, fixed ropes, radios and portable hyperbaric chamber; bottled oxygen, kerosene, climbing gas, porter food and altitude medication | 3 people, 44 days, 14 assets; NO-GO baseline; damaged/service equipment and low food/medical stock |

The baselines are deliberately different and support dashboard presentations. On dashboard load, PolarOps requests current Open-Meteo conditions at that expedition's own coordinates and recalculates its risk assessment; the page labels the input `Live`, `Cached`, or `Manual`. If Open-Meteo is unavailable, the seeded regional baseline is used with an offline notice. Weather and derived risk can therefore differ from the static baseline table after a successful live fetch.

## PostgreSQL / Docker

Settings switch to PostgreSQL when DB_ENGINE=postgres. Configure POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and optional POSTGRES_PORT.

~~~sh
export DJANGO_SECRET_KEY='use-a-long-random-secret'
export POSTGRES_PASSWORD='use-a-strong-password'
export POLAROPS_PUBLIC_URL='https://polarops.example.org'
docker compose up --build
~~~

The compose defaults are for local evaluation only. Set a real secret, password, public URL, allowed hosts and DJANGO_DEBUG=0 before deployment. Put the app behind HTTPS, back up PostgreSQL and the media directory, and use a production WSGI server. Schedule python manage.py generate_alerts regularly (for example, daily) to scan stock, cold-chain, maintenance, medical-clearance and certification conditions.

## Roles and access

- **Administrator:** all operational screens, alert actions and audit log.
- **Expedition Leader:** manage expedition and readiness records, approve/reject requisitions, acknowledge/resolve SOS events.
- **Logistics Officer:** manage personnel, certification, assets, inventory and transport; check assets in/out; submit and fulfill approved requisitions.
- **Field Member:** view assigned expeditions/assets, submit SOS events, and check custody records for the assigned mission. Field Members receive 403 responses on management CRUD pages.

Pages and API routes require an authenticated PolarOps role. The API is under /api/; obtain a token from /api/token/ and send it as Authorization: Token <key>. Field API querysets are scoped to assigned expeditions.

## Main workflows

- **Mission control:** responsive, session-scoped dashboard with a clearly labelled **All expeditions** overview and per-expedition scope. The scope filters status tiles, readiness, risk badge and factor bars, live weather, camp/depot map, supply chart, maintenance watch, transport, alerts and SOS banners. The top-bar risk badge and Go/No-Go panel use the same latest assessment. Expedition detail, inventory, asset, transport and report views/exports also honor the active scope. The Leaflet camp/depot map uses Terrain and Esri Satellite layers; the former interactive SVG map is retained as an offline tile fallback.
- **Regional appearance:** Antarctica, Arctic, Himalaya/high altitude, Subantarctic/sea voyage and Greenland/tundra. Administrator theme preview is available in the top bar. Theme colors are checked against WCAG AA contrast targets.
- **Operations records:** searchable, filterable and paginated list/detail/create/edit/delete pages with validated forms for expeditions, personnel, certifications, assets, inventory, stock movements, transport, contingency plans and risk assessments. Delete actions require confirmation.
- **Personnel readiness:** medical-clearance and certification expiry records. Expired or missing medical clearance blocks expedition team assignment and asset checkout.
- **Asset custody:** checkout records the recipient, expedition, handover condition and time; check-in records return condition, damage notes and added use/cold-exposure hours. Maintenance-condition, damaged and already-out assets cannot be checked out. Every asset has a persistent QR image, detail page and printable tag; scanning the tag opens its asset record.
- **Supply and inventory:** region-adjusted supply calculator with editable consumption rates and safety buffer. A calculated requirement can be turned into a Draft requisition, submitted by Logistics, approved/rejected by a Leader, and fulfilled into stock movements and inventory quantities. Requisitions have PDF export.
- **Risk / weather:** manual operational assessment with rule-based score, contributing factors and GO/CAUTION/NO-GO verdict. Risk entry can fetch Open-Meteo temperature, wind, visibility and daylight readings; successful samples are cached with timestamps. Timeout, provider errors and offline use fall back to the cached sample or manual entry with a visible notice.
- **Emergency response:** high-contrast field SOS form with camp coordinates prefilled and editable, automatic timestamp, immediate leader/admin dashboard alert, acknowledge/resolve actions and status history. Contingency route and station information appears on expedition details.
- **Notifications:** unread count and recent-alert dropdown, per-user read receipts, notification filters by type/severity/status, and 30/14/7-day medical and certification alerts. Alert scans run through generate_alerts.
- **Audit and reports:** Administrator-only combined history log with model/user filters. CSV and PDF exports are available for operations reports; requisitions also have a dedicated PDF.

## Presentation walkthrough

1. Sign in as administrator. Change the top-bar expedition selector through McMurdo–South Pole, Ny-Ålesund and Everest to show the session scope, regional theme, map focus, live weather and expedition-specific dashboard widgets; choose **All expeditions** for the global overview. The administrator theme preview remains available with `/?theme=subantarctic` or `/?theme=greenland`.
2. Sign in as logistics_officer, open **Supply calculator**, calculate for a region/team/duration, then create a Draft requisition from the result.
3. As Logistics, submit the requisition. Sign in as expedition_leader, approve it. Return as Logistics and fulfill it to see the generated inventory movements.
4. As Logistics, open an assigned asset such as ANT-TRK-002, check it out to an eligible member of its expedition, and print the tag. Scan its QR with a phone on the same reachable PolarOps URL to open the asset record.
5. Sign in as field_member, open **Send SOS**, confirm the prefilled camp coordinates and submit. As an Expedition Leader, acknowledge and resolve the new dashboard banner.
6. Sign in as administrator and open **Audit log** to review the actor, model, object, action and time for records changed during the walkthrough.

For a deployed demo, set POLAROPS_PUBLIC_URL to the reachable HTTPS app URL before generating QR tags. Localhost QR URLs are only scannable on a device that can reach that local server.

## Architecture and checks

- polarops/: environment-based settings, root routing, ASGI and WSGI.
- core/crud.py, domain service modules and app view modules: forms, role checks and business rules.
- accounts/, core/, expeditions/, personnel/, assets/, inventory/, transport/, risk/, emergency/, reports/: domain boundaries and migrations.
- Django templates and static/css/polarops.css: responsive operations UI, five theme palettes, toasts, button loading feedback and persistent gloved-use mode.
- django-simple-history: change history on principal operational records; SOS also has explicit status events.
- Django REST Framework token/session authentication; ReportLab PDF output; qrcode/Pillow image generation.
- Chart.js, Tailwind and Alpine are available for UI enhancement. The camp/depot map uses Leaflet with OpenTopoMap terrain and Esri World Imagery satellite tiles; an interactive SVG remains available when network tiles are unavailable.

Run:

~~~sh
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py check
~~~

## Remaining deployment considerations

Live weather depends on external Open-Meteo reachability; cached/manual fallback remains available. Schedule the alert command in the deployment environment and retain the media directory when deploying or restoring backups. Bundled demo records and credentials are synthetic and must not be used for real deployments.
