# CLAUDE.md

Guidance for Claude Code in this repo. **Kept deliberately short**: it holds current facts and load-bearing gotchas only. History, measurements and "why it changed" stories live in git history (`git log -p CLAUDE.md`) and in the roadmap. Don't re-grow it with verification logs or dated narratives — record the *rule*, not the story.

## Project overview

"Taku Monky" — system for a taquería, two halves sharing one **Supabase** project:

- **Flet (Python) desktop admin panel** for the owner: menu CRUD, tables catalog, AI agent, ad generator, stats.
- **Static public site** (plain HTML/CSS/JS at repo root, FTP'd to Hostinger as-is, no build step): public menu (`index.html` + 3 `menu-*.html`) and the staff sales tool (`mesas.html`). No Python serves it.

Images live in **Cloudflare R2** (never Supabase Storage — keep it at zero buckets). The system is also being turned into a **resellable white-label template** rented semi-annually to other restaurants (one Supabase project per client).

**The phased roadmap lives in `planes/Hey Claude Code, read this file..txt`, and the current panel redesign plan in `planes/plan panel.txt` (the whole `planes/` folder is gitignored) — read them at the start of a session.** Status: Phases 1–7 done. Only **Fase 8** remains (the owner's own visual pass on the public site; Inicio's fake numbers are gone since the 29/09 redesign).

**Layout**: the whole Flet panel lives in **`panel/`** (`main.py`, `controllers/`, `views/`, `models/`, `herramientas/`, its own `assets/`, the generated `biblioteca/`). **Every panel path in this file (`views/…`, `models/…`, `assets/…`, `herramientas/…`) is relative to `panel/`.** The repo root holds only the static site (+ its own `assets/`: `frames/`, `logomonky.png`, `sin-foto.png`, …), `cloudflare/`, `panel_licencias/`, the shared `.env` and `requirements.txt`. `logomonky.png`/`sin-foto.png` exist in both `assets/` folders on purpose (each half is self-contained). `panel/main.py` `os.chdir`s to its own folder, so relative paths (Flet and Pillow) work no matter where it's launched from; the models load `.env` from the repo root (`parents[2]`).

Roles: the chat user is the **developer**; "el dueño"/"the owner" in docs is the client (Ary). The name "Ary" appears in greetings; gender unknown — keep copy neutral.

## Secrets & repo safety

- **The repo is PUBLIC** (`github.com/mateo777g/proyectotaku`). Before every commit check `.gitignore` still covers `.env`, `planes/`, `EJEMPLOS 2/`, `biblioteca/`, `clientes.json`, `panel/config.json`.
- `.env` (real `KEY=value`): `SUPABASE_URL`, `SUPABASE_PROJECT_REF`, `SUPABASE_ANON_KEY`, `SUPABASE_ACCESS_TOKEN` (Management API PAT, DDL only), `SUPABASE_ADMIN_EMAIL`, `OPENAI_API_KEY`, optional `OPENAI_MODEL`, `CLOUDFLARE_WORKER_URL`, `CLOUDFLARE_R2_PUBLIC_BASE`, plus admin-only `CLOUDFLARE_API_TOKEN`/`_ACCOUNT_ID`/`_R2_BUCKET`. Never print/log/copy values; reference via env vars.
- **No service_role key, ever.** If a write fails, check the admin session — never add service_role or loosen `anon` policies.
- Passwords (owner + developer licence user) are in the roadmap `.txt` under "AUTENTICACIÓN DEL PANEL". Use them for real end-to-end tests (read them from the file in Python, not on a command line). Never copy them into `.env`, a tracked file, or console output. Cloudflare redeploy recipe is also there ("ACCESO A CLOUDFLARE").
- `EJEMPLOS/` was deleted for good (mentions of it are provenance only). `EJEMPLOS 2/` (Anxie Store's Flet+Pillow app) is reference-only: never import, run, edit, or copy keys from it.

## Supabase

Project `BDTakuMonky`, ref **`yiafxeibhqyghrkwvmju`**. Other refs are dead. DDL goes through `POST https://api.supabase.com/v1/projects/{ref}/database/query` with the PAT.

**Auth users** (public signup disabled — keep it so):
- **Owner/waiters**: `takumonky5@gmail.com`, UID `3c4d9de3-bb5f-459b-94a2-2300bab8b376`. All admin RLS policies are scoped to this **UID** (not the `authenticated` role). Never recreate this user — 20 policies hardcode the UID; rename instead. The email is hardcoded in 4 places that must move together: `.env` `SUPABASE_ADMIN_EMAIL`, `mesas.js` `ADMIN_EMAIL`, the Worker's `ADMIN_EMAIL` binding (forgetting it breaks photo uploads with "no autorizado"), and docs.
- **Developer licence user**: `matthewsantreys13@gmail.com`, UID `31157a27-bb56-4415-88dd-ef4098940b2e` — only used by `panel_licencias/`.

**Tables** (all RLS on):
- `platillos` — `id, nombre, descripcion, categoria` (CHECK `Platillos`/`Bebidas`/`Postres`), `precio, visible, image_url, image_url_recortada, orden, created_at, updated_at`. `anon` may only SELECT `visible = true`; admin UID has full CRUD. `updated_at` bumped by trigger `trg_platillos_updated_at` (shared function `public.set_updated_at()`). Delete is a real physical DELETE (no soft-delete).
- `ventas` — `id, mesa` (free-text snapshot, **not** an FK), `estado` (`abierta`/`cerrada`), `total, created_at, updated_at, cerrada_at`.
- `venta_items` — `id, venta_id` (FK cascade), `platillo_id` (FK set null), `nombre, precio_unitario` (snapshots), `cantidad, created_at`.
- `mesas` — `id, nombre` UNIQUE, `orden, ...` — owner-managed table catalog. `mesas.html` matches it to open `ventas` client-side by trimmed/lowercased name.
- `configuracion_negocio` — exactly one row: `nombre, fecha_inicio, fecha_fin, activo`. **Licence kill-switch.** Owner has SELECT only; licence UID has SELECT+UPDATE only. Dates are reference-only; only `activo` matters.
- `ventas`/`venta_items`/`mesas`/`configuracion_negocio` have **zero `anon` policies**.

**Licence lock**: right after a successful login, `views/sesion_view.py` (`ConfiguracionNegocioDAO.licencia_activa()`) and `mesas.js` (`licenciaActiva()`) read `activo`; if false — or if the query errors (**fail closed**) — they sign out and stay on the login screen. It's deterrence, not DRM; the hard lever is disabling the client's Auth user.

**Sessions are never persisted** (panel and `mesas.js` `persistSession: false`) — a business decision: every app start must hit `signInWithPassword`, which is the point where a lapsed rental gets cut off. Don't bring persistence back without an explicit product decision. `mesas.js` keeps `autoRefreshToken` on so an open tab survives a shift.

**RLS silent-failure gotcha**: an UPDATE/DELETE blocked by RLS returns HTTP 200 with `data: []`. Every DAO write method (`actualizar`/`eliminar`/`cambiar_visibilidad`/...) must `if not respuesta.data: raise EscrituraSinEfecto(...)`. Keep this in any new write method.

**Timezone trap**: the Supabase dashboard shows UTC (`+00`); the app converts to local time (Mexico, UTC-6). A "date mismatch" between them is usually not a bug.

**MS Store Python trap**: `%LOCALAPPDATA%` is virtualized for Python here (lands under `...\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\Local\`). Check files written by Python *from Python*.

## Cloudflare (R2 + Worker)

Bucket `takumonky`, Worker `taku-monky-uploads` (on `takumonky5.workers.dev`). Source in `cloudflare/index.js` (no secrets; reads `env.*` bindings). Worker owns all R2 writes, auth = admin's Supabase `access_token` + `ADMIN_EMAIL` check. To change only bindings use `PATCH .../workers/scripts/taku-monky-uploads/settings`; full `PUT` redeploy when code changes. Public R2 URLs (e.g. `image_url_recortada`) can be read with plain `httpx.get`, no credentials.

## Design rules (Flet panel — non-negotiable)

**Never redesign, re-theme or "modernize" existing screens** unless the developer asks. When wiring data, change only the data source. If a design question isn't answered by an existing view, ask.

**The panel is moving to the "manchas + vidrio" design** (approved 28/09, born in the AI agent view; views are ported one by one on request). Its rules live in `planes/plan panel.txt` ("DISEÑO MANCHAS + VIDRIO") — read them before touching any view; the approved mockup is in `panel/diseno/maquetas-agente-ia/` (keep it). Pieces in `views/diseno.py` (`vidrio`, `texto`, `etiqueta`, `icono` from `assets/iconos/*.svg`, `boton`, `boton_cuadro`, `selector`, `campo`, `apagar`, and for dialogs `ventana`/`caja_error`/`confirmar`), colors in `views/tema.py` namespace `D` (incl. `D.acento`: logo orange `#E8622A` in light, logo blue `#1355E8` in dark; plus the fixed `VERDE`), fonts Plus Jakarta Sans by weight (`Jakarta400`…`Jakarta800`) + JetBrains Mono (`Mono400/500`). The animated dither background (`assets/fondo-manchas-{claro,oscuro}.webp`, `herramientas/generar_fondo_manchas.py`, shown with `filter_quality=NONE`) is **exclusive to the AI agent view** (developer's rule): `MainController.cambiar_vista` puts it behind the floating glass sidebar only there; for every other view it moves the view's own `bgcolor`/`gradient` to a full-window layer behind the sidebar, so the glass takes that view's background. The sidebar's outer margin lives on a non-blurred wrapper (on the glass itself Flet blurs the margin too → a halo). Ported so far: the AI agent, Inicio (plain `D.suelo` background, approved mockup https://claude.ai/artifact/1FWmGuBQ5hqeKU8ddtqgqg) and Mi menú + its dialogs (mockup https://claude.ai/artifact/34WRAVdMDwSU8NpLctykoe). Not yet ported (still `C.*` and the older palette below): Mesas, Crear contenido, Mi biblioteca, Ajustes, login, Perfil.

- **Palette** (hex inline on controls, no theme file): `#fbf5e9` page bg · `#f8f1de` card/row · `#eee5cf` table header · `#eadfca` borders · `#0d0905` sidebar/primary button · `#1c1610`/`#18120d` text · `#f4ca83` gold · `#ffa200`/`#e8aa3a` warm · `#bf571d`/`#c86a28` orange · `#5e5449`/`#7c7267`/`#8a7e72`/`#806f61` muted · `#b58a6d` eyebrow · `#7d8545` green ok · `#d9534f` red destructive. Error box: `#f7e4e3` bg / `#d9534f` border / `#a33c39` text.
- **Type**: headings `font_family="Georgia", italic=True` (~40–48 page titles). Eyebrows `size=11–13, weight="bold"` in `#b58a6d`/`#806f61`. Body default font 12–15.
- **Shapes**: pill buttons radius 30, cards 14–16, badges 12, icon buttons 30×30 radius 15 `ink=True`.
- **Spacing**: views pad `left=36, right=36, top=42, bottom=36`; vertical gaps via `ft.Container(height=N)`.
- Loading = gold `ProgressRing` (except the AI agent, see below). No separate "success banner" language — success is shown inline on the button (green check, ~1.6 s).
- UI copy, comments and identifiers are in **Spanish**.

## Flet gotchas (learned the hard way)

- **Flet ≥ 0.85** (panel and `panel_licencias/`). The lowercase helper modules are gone: use `ft.Padding.symmetric/only/all`, `ft.Margin.*`, `ft.Border.*`, `ft.BorderRadius.*` — never `ft.padding.*`/`ft.margin.*`/`ft.border.*`/`ft.border_radius.*` (crashes with `AttributeError` at construction).

- `AlertDialog(modal=True)` blocks barrier-tap and Escape → every dialog needs an explicit **X close button**. Keep both.
- Dialogs with a `_ocupado` guard: success paths must call `_set_cargando(False)` **before** `_cerrar()`.
- **Mutating `ft.Icon.name` on a mounted icon does nothing** (no error). Replace the icon control instead (`.content = _icono(...)`).
- Reading `.page` on an unmounted control raises `RuntimeError` — use a `_montada` flag.
- A filled `TextField` paints over its wrapping Container's border → in the agent's input box, `filled=False` and the Container paints the background.
- Programmatic `focus()` does **not** fire `on_focus`; disabling a field **does** fire `on_blur`. `focus()` doesn't work in the web client.
- `ft.Image(src=...)` needs forward slashes (a Windows backslash path won't load). `src` resolves relative to the app folder (`panel/`) regardless of `assets_dir`; `main.py` keeps `assets_dir="."`.
- `scroll_to()` doesn't work on `ListView`/`GridView`; needs `auto_scroll=False`.
- `on_size_change` on a `Container` that also has `top/left/...` breaks it as a `Stack` child (the view renders grey): put it on an inner Container.
- File/folder pickers use **Tkinter** (`filedialog`, hidden `tk.Tk()` root), never Flet's `FilePicker` (owner preference), always via `asyncio.to_thread`.
- Blocking calls (Supabase, R2, OpenAI, Pillow) live in `models/` and are called from views via `asyncio.to_thread`. DAOs don't catch exceptions; views do. Never swallow an exception silently — log with `traceback.print_exc()`.
- `ft.Screenshot(...).capture(pixel_ratio=1.0)` — must be a float or it hangs. That's the way to screenshot the real native window for verification; keyboard tests go through the web client (`FLET_FORCE_WEB_SERVER=1`, `assets_dir="assets"`) + Playwright.

## Panel screens (`views/`)

- `sesion_view.py` — login, always first on launch (not routed through `cambiar_vista`, no sidebar button). Runs the licence check.
- `home_view.py` — Inicio (manchas + vidrio, no dither background). Top glass bar ("en vivo" chip, last-read time, Actualizar, Crear contenido, Nuevo platillo) + big glass card with the date and the time-based greeting (`models/tiempo.py` + Perfil name — **the date and greeting are the view's non-negotiables**) and 4 real figures, "Mesas ahora", the 4 "¿Qué hacemos hoy?" shortcuts, "Lo más vendido" (Hoy/Semana/Mes) and "Lo último de tu menú" (3 rows max, Nuevo vs Editado by `created_at == updated_at`, photo or `sin-foto.png`). Everything is real: sales/tables from `models/resumen_inicio.py` (reuses `ia_controller.py`'s helpers so Inicio and the agent never disagree: closed sales only, 6:00→6:00 business day, products by `platillo_id`), "EN VENTA" from `PlatilloDAO.obtener_estadisticas()` (only `visible = true` — intentionally differs from Menú's counter), "CONTENIDO" = files in `biblioteca/` modified this month. Loads run **one after another** (concurrent threads on the one Supabase client failed with WinError 10035). The old fake cards (visitas, producto más visto, SUGERENCIA DE HOY) were removed — don't bring back numbers without a data source.
- `menu_view.py` + `components/dialogo_platillo.py` — platillo CRUD (manchas + vidrio). Top bar: chip "N de M a la vista", white **Ocultar varios** (→ Cancelar), black Nuevo platillo. Glass card: search + category `selector` (both filter in memory) and the solid table: PLATILLO (thumb + name) · DESCRIPCIÓN · CATEGORÍA · PRECIO (mono, `_formatear_precio`) · VISIBILIDAD (filled/hollow dot, no red/green) · eye / pencil. **Ocultar varios** mode: a checkbox per row (already-hidden rows disabled), a tinta bar at the bottom hides the chosen ones in one query (`PlatilloDAO.ocultar_varios`, raises `EscrituraSinEfecto` unless every row changed). Inicio's "Marcar un platillo como agotado" opens Mi menú in that mode (`cambiar_vista(..., ocultar_varios=True)`). The dialog uses `diseno.ventana` (solid card, X, mono step label, category as a segmented selector); delete confirms with `diseno.confirmar`, which replaces the edit dialog and reopens it on Cancel or to show "ELIMINANDO...". Missing photo → `assets/sin-foto.png` (a **plain black** image on purpose — don't replace with a food photo).
- **Photo upload order** (in `dialogo_platillo.py`): create = upload → insert (delete photo if insert fails); edit = upload new → update → delete old; delete = delete row → delete photo. `cloudflare_storage.eliminar_imagen()` never swallows failures: logs, **appends** to `%LOCALAPPDATA%\TakuMonky\huerfanos_r2.json`, raises `LimpiezaImagenFallida`; post-success cleanup failures are surfaced via `on_guardado(aviso)`. Photos are compressed to WebP, 1600 px max side, q80; originals up to 15 MB accepted.
- `mesas_view.py` + `components/dialogo_mesa.py` — table catalog CRUD. Reuses the OLD-style `_confirmar` from `dialogo_platillo.py` (also used by Mi biblioteca; keep it until those views are ported).
- `agenteIA_view.py` — AI agent (see below).
- `contenido_view.py` → `biblioteca_view.py` → `ajustes_view.py` — ad generator, gallery, settings (see Fase 7 below).
- Views are rebuilt from scratch on every navigation; no caching anywhere in the panel.

## AI agent (`models/ia_controller.py`, `models/saludo_ia.py`, `models/venta_dao.py`, `views/agenteIA_view.py`)

- OpenAI SDK, default model **`gpt-4o`** for the conversation (override `OPENAI_MODEL`); the welcome greeting uses **`gpt-4o-mini`** (`models/saludo_ia.py`, override `OPENAI_MODEL_SALUDO`). No Anthropic key needed.
- Each question re-reads `platillos`/`mesas`/`ventas`/`venta_items`, flattens them into the system prompt with local-time dates. `VentaDAO` is read-only, capped at 500 ventas.
- **Python does all arithmetic** (`_resumen_calculado`: totals per period/table/day/product, per period incl. this month, plus a `TOTAL POR PRODUCTO` line). The prompt tells the model to copy numbers, never re-sum. Don't remove this — the model mis-summed real data. Only closed sales count; open tabs reported separately. Business day runs 6:00→6:00 (`_HORA_CORTE_DEL_DIA = 6`).
- Normalization: table names unified case-insensitively (catalog name wins); products grouped by `platillo_id` (names collide), falling back to name only for deleted platillos.
- **Scope rule stays at the top of the prompt**: only this business; off-topic → one-line refusal, no "just this once" overrides.
- The three "Ideas para ti" shortcut prompts (today/week/month, by product, never by table) say the total goes **below** the table, not as a table row — otherwise the model sums a column wrongly.
- Welcome greeting lives entirely in `models/saludo_ia.py` (`redactar()` (random form + tone, gender-neutral filter `_MARCA_GENERO`, one retry, silent local fallback — never a red banner). Pre-written: the same module keeps ONE greeting in reserve (requested at app start on the login screen — it needs no session — again in `mostrar_panel()`, and each time the view takes one), discarded if the nickname or time of day changed; the view shows it from the first frame, or the local fallback instantly if none is ready (never a blank, never swapped afterwards).
- UI (the "manchas + vidrio" design, see Design rules): top glass bar (title, "en vivo" chip, Historial = this session's conversations in `router.conversaciones`, Nueva conversación) + two states: welcome (centered glass card: date, two-line greeting split after the name by `_partir_saludo`, input box with Hoy/Semana/Mes selector — the period is appended to the question only as a fallback —, 3 idea cards) / chat (glass panel with messages and the box anchored bottom, plus the "LO QUE LEÍ PARA RESPONDER" card fed by `IAController.ultima_lectura`). Enter sends, Shift+Enter newline. Answers render with `ft.Markdown` (GFM, `soft_line_break=True`) in Jakarta 16 / 1.6; table header rows are uppercased for display only (`_para_pintar`). Under each answer: Copiar, plus the idea's two follow-ups. Answers reveal line by line (`_partir_en_renglones`/`_revelar`; tables/code/quotes as one block), then are swapped for one `ft.Markdown` so selection works. "Pensando..." uses the animated `D.logo_pensando` (`assets/logo-pensando-{naranja,azul}.webp`, regenerate with `python panel/herramientas/generar_logo_pensando.py` from `assets/fragmentless.png`): the same thick logo, color and 42 px slot as the logo beside each answer (`_logo_saludo`, `HUECO_LOGO_RESPUESTA`), breaking into its 7 pieces; frame 0 is the whole logo so the swap to the answer doesn't jump. Never a Python-driven frame timer. `_quitar_indicador()` removes the thinking row only if present — keep it.

## Content creation (Fase 7 — done)

Flow: template → platillo (only those with `image_url_recortada`, category Platillos, max 5) → text → format (post 1080×1350 / story 1080×1920) → generate.

- `models/plantillas.py` — the only reader of `assets/taku-plantillas/zones.json`. 4 templates (`01-topografico` headline only, `02-naranja`/`03-blanca` headline+subline, `04-negra` `headline_stack` repeated 7×). `campos_texto` tells the form which fields to show.
- `models/generador_anuncios.py` — `generar_anuncio(...)` composes background → logo → text → photo with Pillow and writes straight to `biblioteca/` (`RUTA_BIBLIOTECA`), returning a forward-slash path. Backgrounds are pre-rasterized at **2×** in `png-final/` (`herramientas/generar_fondos_plantillas.py`, constant `ESCALA`). The logo box is trimmed below the pre-painted spark (`_caja_logo_bajo_destello`). Text is uppercased and shrunk to fit `max_w`. Photos cached in memory — always return `.copy()`.
- Ad font is **League Spartan Black** (`assets/fuentes/`, OFL) as a stand-in for Lovelo (not bundled: personal-use licence). Georgia is the panel font, never the ads'. Wordmark PNGs: `assets/logo-wordmark-{blanco,naranja}.png` (`herramientas/generar_wordmark.py`); emblem: `assets/logo-emblema.png` (`logomonky.png` stays untouched for the sidebar). `assets/img1-4.png` are the finished mockups of the 4 templates (used as thumbnails).
- `models/config_usuario.py` — owns **`panel/config.json`** (gitignored in `panel/.gitignore`, Anxie-style): `ruta_exportacion` (fallback `~/Downloads`), `nombre_completo`/`como_llamarte` (`models/perfil.py`), `tema` (`views/tema.py`). Everyone writes through `guardar_config()`, which only changes its own keys. Migrates once from the old `%LOCALAPPDATA%\TakuMonky\config.json` (left in place).
- `ajustes_view.py`'s bottom card is **Tema** (Oscuro/Claro `interruptor` from `views/piezas.py`) → `router.cambiar_tema()` saves and rebuilds Ajustes. "Cerrar sesión" lives only in the sidebar (`views/barra_lateral.py`).
- `herramientas/` = one-off scripts the developer runs by hand; nothing the app imports.

## Public menu site (`index.html`, `menu-*.html`, `style.css`, `catalogo.css`, `catalogo.js`, `menu.js`, `carrusel.js`, `carta.js`, `hero-animacion.js`)

> **The owner is polishing its visuals by hand — don't redesign it unprompted.** Data layer is final. If you change CSS/markup on request, keep the ids/classes the JS uses (grep the JS before renaming anything).

- Script order: index → `catalogo.js`, `carrusel.js` (desktop ≥1024 3D carousel), `carta.js` (mobile <1024 carta, uses `image_url_recortada`), `hero-animacion.js` (hero taco animation on a sticky scroll wrapper). Category pages → `style.css` + `catalogo.css`, `catalogo.js` + `menu.js`. `catalogo.js` must load first (others use its globals).
- `catalogo.js`: Supabase client with `persistSession/autoRefreshToken/detectSessionInUrl: false` (keep — prevents a known auth-reinit query storm); `obtenerCatalogo({forzar})` = one query for the whole visible catalog, explicit columns (never `select('*')`), `sessionStorage` cache `taku_monky_catalogo_v1`, **TTL 30 s**; `iniciarAutoRefresco()` always passes `forzar: true` (otherwise a tick equal to the TTL skips refreshes). The panel cannot invalidate a customer's browser cache.
- `NUMERO_WHATSAPP` in `catalogo.js` is a deliberate placeholder (`5215500000000`). Don't use `sidebar.py`'s number (that's the developer's support line).
- Breakpoints duplicated in CSS and JS must stay in sync: 1024 px (`style.css` ↔ `_CARRUSEL_BREAKPOINT`), 640 px (`catalogo.css` ↔ `esMovil()`).
- Carousel: palette exception on purpose (own dark/gold values — don't "fix"), max 2 per category / 6 cards, interleaved. Its sticky pin: the `position: sticky` rule must come **after** `.tk-carrusel-seccion`'s base rule in `style.css`.
- Decorative leaves: exactly 4 (hero pair + desktop carousel pair). The owner twice rejected leaves on mobile section 2 — don't add them. Tuning notes live in `style.css` comments.
- Category pages: `.tk-cat-header` (not the index navbar), 4 cards/row via flex-wrap (numbers are load-bearing), 4:3 photos, sort "Recomendado" = panel `orden`, search covers the whole catalog (accent-insensitive, deep links `#platillo-<id>`), modals injected by `menu.js`.
- Mobile footer is a separate `.tk-footer-movil` (native `<details>` accordions; "Legales" says "Próximamente." — don't invent legal copy).
- Preview locally with `python -m http.server 8123` (not `file://`).

## Staff sales tool (`mesas.html` / `mesas.css` / `mesas.js`)

Self-contained (own Supabase client, shares nothing with `catalogo.js`/`style.css`). Login → table cards from `mesas` showing Disponible / Ocupada · $total → order view (add items from all platillos, hidden ones labelled "(oculto)", cached per page load) → close sale. `ventas.total` is recomputed and written by the client on every change. Neutral black/white/zinc palette (it's the resellable template); the amber `--ambar` is used **only** for "Ocupada".

## Licence panel (`panel_licencias/`)

Developer-only Flet app (`python panel_licencias/main.py`), not reachable from the owner's panel, no login screen. Logs into every client's Supabase in parallel from `%LOCALAPPDATA%\PanelLicencias\clientes.json` (`{nombre, url, anon_key, correo, password}`), shows dates/remaining days and toggles `activo`. **Imports nothing from `models/`/`views/`/`controllers/`** — keep it liftable. Each row fails independently.

## Architecture

- `main.py` → `ft.run(main, assets_dir=".")` → `controllers/main_controller.py` `MainController` (the `router`): `mostrar_login()` / `mostrar_panel()` / `cerrar_sesion()` and `cambiar_vista(vista, abrir_dialogo_nuevo=False)` — the only navigation; rebuilds the view and the `Sidebar`. Views: `"home"`, `"menu"`, `"mesas"`, `"agente_financiero"`, `"contenido"`, `"biblioteca"`, `"ajustes"`.
- View pattern: `class XView(ft.Container)`, `__init__(self, router)`, `expand=True`, `bgcolor="#fbf5e9"`, content built in `__init__`.
- `models/`: `supabase_client.py` (shared anon client; writes rely on the active session), `platillo_dao.py`, `mesa_dao.py`, `venta_dao.py`, `configuracion_negocio_dao.py`, `cloudflare_storage.py`, `ia_controller.py`, `tiempo.py`, `plantillas.py`, `generador_anuncios.py`, `config_usuario.py`. DAOs never `select('*')`. New platillos get `orden = max + 1`.
- New screen: add `views/x_view.py`, import + `elif` in `cambiar_vista`, button in `views/components/sidebar.py`.
- `panel/flet_logo.py` is unused reference code.

## Running

```bash
pip install -r requirements.txt
python panel/main.py
```

`herramientas/` scripts are run as `python panel/herramientas/<script>.py`.

No build, linter or tests. Verify phases end-to-end in the real app with the real admin login, then check results out-of-band (SQL via Management API / Cloudflare API).
