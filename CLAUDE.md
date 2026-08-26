# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Taku Monky" is an admin panel for a taquería (taco restaurant), built with **Flet** (Python wrapping Flutter). It is one piece of a larger, two-part system:

- **This repo (Python/Flet)**: a desktop admin app for the business owner — manage the menu, view stats, generate content, use an AI agent, etc.
- **Public-facing site (separate, static HTML)**: customer-facing menu page and a table/seating system (`mesas.html`), deployed to Hostinger. It is *not* built from this Python code — `index.html`, `mesas.html`, `style.css`, and `mesas.css` in this repo are currently empty placeholders for that separate static site.

**The phased build plan lives in `Hey Claude Code, read this file..txt` at the repo root — read it at the start of a session to know what's done and what's next.** (The owner clears context often; that file is the running roadmap, this file is the stable reference.)

Both halves are meant to share the same data by reading/writing the same **Supabase** project (Postgres + REST API). Menu images are intended to be stored in **Cloudflare** (not Supabase Storage). Supabase Auth (login + persisted session, see `models/` below and `views/sesion_view.py`) is wired up as of Phase 2.0. `menu_view.py` reads real rows from `public.platillos` via `models/platillo_dao.py` as of Phase 2.1-2.5 (loading/empty/error states, async fetch), and as of Phase 2.6 the panel can create/edit/delete/hide platillos too — see `models/`/Architecture below. As of Phase 2.7, `home_view.py`'s menu-dependent cards (the platillo/category count, the recent-changes list, and the "add new dish" shortcut) are wired to real data too — see the dedicated `home_view.py` section under Design rules below. Still not wired: Cloudflare image upload and the AI agent.

Credentials live in `.env` at the repo root. Never print, log, or copy these values into other files — read `.env` only when you need to wire up a specific integration, and reference values via environment variables in code, not by hardcoding.

**Supabase project**: `BDTakuMonky`, ref **`yiafxeibhqyghrkwvmju`** (us-east-1, Postgres 17) — the only project on the account. Any older ref (`jayxntvpiduxvgvluaky`, `cyeeshiaivevomjotvsr`) is dead; `jayxntvpiduxvgvluaky` belongs to Anxie Store / `EJEMPLOS`. `.env` is written in real `KEY=value` format and holds `SUPABASE_URL`, `SUPABASE_PROJECT_REF`, `SUPABASE_ANON_KEY` and `SUPABASE_ACCESS_TOKEN` (a Management API PAT, used only for DDL — never from the app itself). Schema changes go through `POST https://api.supabase.com/v1/projects/{ref}/database/query` with that PAT.

The menu table exists: **`public.platillos`** (lowercase — `.from_("platillos")` in code) with `id, nombre, descripcion, categoria, precio, visible, image_url, orden, created_at, updated_at`. `categoria` carries a CHECK constraint limiting it to `Platillos` / `Bebidas` / `Postres`. RLS is on: `anon` may only `SELECT` rows where `visible = true`; `authenticated` has full read/write. It is seeded with the 10 placeholder dishes that `menu_view.py` used to hardcode (one has since been deleted during Phase 2.6 testing — 9 remain). **Images are Cloudflare's job — do not enable or use Supabase Storage.**

`updated_at` (timestamptz, `DEFAULT now()`, `NOT NULL`) was added in Phase 2.7 via the Management API, together with a trigger — function `public.set_updated_at()` plus `trg_platillos_updated_at BEFORE UPDATE ON platillos FOR EACH ROW` — that bumps it to `now()` on every UPDATE (including `cambiar_visibilidad`, not just `actualizar`). Existing rows were backfilled to `updated_at = created_at` *before* the trigger was created, so pre-existing platillos correctly read as untouched instead of "just edited." `home_view.py`'s "Lo último de tu menú" card derives its Nuevo/Editado label by comparing `created_at == updated_at` at display time, not from a separate column — see the dedicated section below.

**Auth model** — the Flet panel signs in through Supabase Auth (same pattern as `EJEMPLOS/lilshop.html`); the JWT from that login is what grants write access, not the key. Admin user is `matthewsantreys13@gmail.com`, UID `3c4d9de3-bb5f-459b-94a2-2300bab8b376`. The four write policies are scoped to that UID specifically, **not** to the bare `authenticated` role — a blanket `authenticated` policy would let anyone who managed to sign up edit the menu. Public signup is disabled (`disable_signup: true`); don't re-enable it.

`SUPABASE_ANON_KEY` is used by both the panel and the public HTML — it is world-readable once embedded in a page, and on its own it can only read rows where `visible = true`. **Never loosen the `anon` policies.** There is deliberately **no service_role key in `.env`**: it bypasses RLS entirely, and the panel doesn't need it. If something can't write, the fix is to check that the admin session is alive — never to add the service_role key or widen `anon`.

Both `.env` and `Hey Claude Code, read this file..txt` contain live credentials and are listed in `.gitignore`. **The repo is on GitHub at `https://github.com/mateo777g/proyectotaku` and it is PUBLIC** — re-check `.gitignore` still covers those two files before every commit, and never move a real key into a tracked file. `EJEMPLOS/lilshop.html` and `EJEMPLOS/supabase-config.js` do carry Anxie Store's `anon` key, which is public by design (it is already embedded in that project's live HTML) and is not this project's key.

## EJEMPLOS/ — reference implementations

`EJEMPLOS/` holds working files copied from **"Anxie Store"**, a previous project by the same owner with the same architecture (static HTML on Hostinger + Supabase + Cloudflare R2 + an AI agent). These are the patterns to follow — read the relevant one before building the equivalent feature here. They are reference only: do not import, edit, or run them as part of this app.

| File | What it demonstrates |
| --- | --- |
| `supabase-config.js` | Shared Supabase client for **public** pages. Uses `persistSession/autoRefreshToken/detectSessionInUrl: false` — the comment explains why (browser tracking prevention blocking `localStorage` caused ~312 redundant `pg_timezone_names` queries, 67% of DB time). |
| `catalog-cache.js` | `sessionStorage` cache layer (5 min TTL) so public pages don't re-`select()` on every visit, plus `clearCatalogCache()` that the admin **must** call after any write. Also shows the rule: `select()` only the columns the UI actually renders, never `select('*')`. |
| `lilshop.html` | The full **admin CRUD** reference — Supabase Auth login, list/insert/update/delete against the `Cuentas` table, client-side WebP conversion before upload, and careful rollback ordering (delete the orphaned R2 image if the row insert fails; only delete the old image *after* the row update succeeds). |
| `index.js` | The **Cloudflare Worker** that owns R2 writes. Static pages have no backend, so the Worker holds the R2 binding and validates the caller's Supabase Auth token against `ADMIN_EMAIL` before touching the bucket. No R2 credentials ever reach the client. |
| `index.html`, `catalogo.html` | The public storefront pages consuming `supabase-config.js` + `catalog-cache.js`. |
| `ia_controller.py` | The **AI agent** pattern in Python: pull real rows via a DAO, flatten them into a text block, inject that into a system prompt, then call the LLM. Note it uses `openai` / `gpt-4o` — this project should use Claude via the `anthropic` SDK instead unless the owner says otherwise. |

Key differences to keep in mind when porting these to this project: here the admin is a **Flet desktop app**, not `lilshop.html`, so image upload/delete goes through Python (`requests`/`httpx`) to a Worker rather than through browser `fetch` + `<canvas>`; WebP conversion needs a Python equivalent (e.g. Pillow). The `sessionStorage` cache in `catalog-cache.js` only applies to the public HTML side.

## Design rules (non-negotiable)

This project's visual identity is already established. **Never redesign, re-theme, or "modernize" existing screens while adding functionality.** When wiring up data, change only the data source — the layout, spacing, typography, and colors stay exactly as they are.

When you build something *new* (a dialog, a form, an empty state, an error toast), it must look like it was always part of the app — reuse the same palette, radii, and text styles from the surrounding view:

- **Palette** (hardcoded hex inline on controls; no theme file — keep it that way):
  - `#fbf5e9` page background · `#f8f1de` card/row surface · `#eee5cf` table header · `#eadfca` borders
  - `#0d0905` sidebar / primary button · `#1c1610` and `#18120d` primary text
  - `#f4ca83` gold accent · `#ffa200` and `#e8aa3a` warm accent · `#bf571d` / `#c86a28` orange highlight
  - `#5e5449`, `#7c7267`, `#8a7e72`, `#806f61` muted text · `#b58a6d` section eyebrow labels
  - Status: `#7d8545` green (visible/ok) · `#d9534f` red (destructive)
- **Typography**: display headings use `font_family="Georgia", italic=True` (sizes ~40–48 for page titles, ~15–19 inline). Small uppercase eyebrow labels are `size=11-13, weight="bold"` in `#b58a6d`/`#806f61`. Body text is default font, `size=12-15`.
- **Shapes**: pill buttons `border_radius=30`, cards `border_radius=14-16`, badges `border_radius=12`, icon buttons 30×30 with `border_radius=15` and `ink=True`.
- **Spacing**: views pad `left=36, right=36, top=42, bottom=36`; vertical gaps use `ft.Container(height=N)` spacers rather than margins.

If a design decision isn't already answered by an existing view, ask rather than inventing a new style.

### `menu_view.py` column mapping (fixed as of Phase 2.1-2.5 — don't re-break it)

The header row and `_crear_fila(platillo: dict)` are in sync. `_crear_fila` now takes the full row dict from `PlatilloDAO.obtener_todos()` instead of positional strings:

| Header | expand | Renders as |
| --- | --- | --- |
| PLATILLO | 3 | 38×38 thumbnail (`image_url`, falls back to `assets/taco.jpg` while it's `NULL`) + Georgia-italic `nombre` |
| DESCRIPCIÓN | 2 | plain text, `size=12`, `#5e5449` — `descripcion` |
| CATEGORÍA | 1 | the gold pill badge (`bgcolor="#f7b84d"`, text `#684c16`) — `categoria`. No fixed `width` on the chip (removed; `"Platillos"` didn't fit in the old `width=58`) — it hugs its text now, the one layout change Phase 2 was allowed to make |
| PRECIO | 1 | bold text, `size=13`, `#1c1610` — `precio` formatted by `_formatear_precio()` (no decimals when the value is whole, e.g. `$150`) |
| VISIBILIDAD | 1 | outlined pill: 7×7 dot + label, built by `_badge_visibilidad(visible)`. `visible=True` → green `#7d8545`/"VISIBLE" (unchanged). `visible=False` → same outline-only pill shape, recolored to red `#d9534f` border+dot and `#a33c39` text (the muted-red already established by `sesion_view.py`'s error box), label "OCULTO". The row itself is never removed or dimmed — only the badge changes |
| *(actions)* | 108px | eye (toggles `visible`) / pencil (opens `DialogoPlatillo` in edit mode) / `…` — the `…` is deliberately still inert, see below |

The gold badge is the **category chip**, not a description tag. Don't move it back to the description column.

### `views/components/dialogo_platillo.py` (Phase 2.6 — the add/edit form)

`DialogoPlatillo(router, on_guardado, platillo=None)` is a class, not a view — it builds and owns an `ft.AlertDialog` and is opened via `.abrir()` from `menu_view.py`'s "Agregar platillo" button and pencil icons. `platillo=None` → create mode; `platillo=<dict>` → edit mode, prefilled, with an extra red "Eliminar platillo" button (opens a second stacked confirm dialog before actually deleting — Flet supports stacking `show_dialog()` calls). Follows the same card language as `sesion_view.py` (420-wide card, same field styling, same `tight=True` Column gotcha) and the same red error-box styling used there and in `menu_view.py`.

Two things worth knowing if you touch this file:
- **The dialog has an explicit `X` close button (`boton_cerrar`, top-right, positioned via `ft.Stack`).** `AlertDialog(modal=True)` blocks both barrier-tap-to-dismiss and Escape in this Flet version — without an explicit close control there is *no* way to cancel the form once opened. Don't remove it or drop `modal=True` as "simpler"; both are needed together.
- **`_ocupado`/`_set_cargando()` guards `_cerrar()`** so the X can't cut off an in-flight save/delete. Because of that guard, every success path (`_guardar`, `_eliminar_async`) must call `self._set_cargando(False)` *before* `self._cerrar()`, not after — this was a real bug caught during Fase 2.6 verification (the guard was added first, and the success paths silently forgot to clear it, which would have made a successful save appear to hang since `_cerrar()` refused to close). If you add another exit path, keep that ordering.

### `models/platillo_dao.py` write methods — the RLS silent-failure gotcha

`crear`/`actualizar`/`eliminar`/`cambiar_visibilidad` were added in Phase 2.6. **All three of `actualizar`/`eliminar`/`cambiar_visibilidad` explicitly check that Supabase returned a non-empty `data` and raise `EscrituraSinEfecto` if not — this is load-bearing, not defensive fluff.** Unlike `INSERT`, a Postgres `UPDATE`/`DELETE` blocked by RLS doesn't raise an error: it just matches zero rows and returns HTTP 200 with `data: []`. This was caught live during Fase 2.6 verification — with a session that had no write grant, `cambiar_visibilidad()` returned success and the UI flipped a row's badge to "OCULTO" while the row was still `visible=true` in the real database. If you add another write method here, it needs the same `if not respuesta.data: raise EscrituraSinEfecto(...)` check, or a caller can end up trusting a write that never happened.

New platillos always get `orden = PlatilloDAO._siguiente_orden()` (max existing `orden` + 1) so they land at the *end* of the list — `orden` defaults to 0 in the table, so an insert that omits it would jump to the top.

**Delete is physically real, and that was audited (2026-08-25)** — the owner asked, having been burned by a previous project. Verified with direct SQL through the Management API (which bypasses PostgREST entirely, so it can't be fooled by an API-layer illusion): the table has **no soft-delete column**, **no DELETE trigger**, and **no rewrite RULE** — `platillos_admin_delete` is a plain RLS policy, and `eliminar()` issues a real `DELETE`. `pg_stat_user_tables` showed `n_tup_del = 5` with gaps in the `id` sequence, i.e. rows the owner deleted from the panel are genuinely gone from Postgres. Edits are equally real: rows the owner edited show `updated_at > created_at`. There is also **no caching anywhere in the panel** — every view refetches on navigation. The one cache that will exist is `sessionStorage` in the *public* HTML (Phase 4, `EJEMPLOS/catalog-cache.js`, 5 min TTL); when that page exists, every write path here must call its invalidation, or the public menu serves deleted dishes for up to 5 minutes. Dead tuples (38 at audit time, table 64 kB) are ordinary Postgres MVCC and get reclaimed by autovacuum — not a leak, and not worth acting on at this size.

### `home_view.py` (Phase 2.7 — menu-dependent cards are real now; the rest is still placeholder)

Most of the Inicio screen is still hardcoded and **not** backed by anything — don't treat it as real, and don't invent data sources for it. This is Phase 7 territory, explicitly out of scope until there's a visits/sales/content-generation table:

- Fake, staying fake: `"347 veces"` / `"+12% vs ayer"`, `"Tacos al Pastor" / "48 órdenes"`, `"12 Posts"`, the whole black `SUGERENCIA DE HOY` card, and the greeting `"Buenos días, Ary"` (fixed string — doesn't change with time of day).
- Genuinely wired since before Phase 2.7: the date line at the top (`datetime.now()`) and the navigation `on_click`s.
- Wired for real in Phase 2.7 — the three pieces that depend on the menu:
  - **`PRODUCTOS EN VENTA`** (built by `_crear_tarjeta_productos_en_venta()`): real count from `PlatilloDAO.obtener_estadisticas()`, which counts **only `visible = true`** — the card says "en venta", and a hidden dish isn't being sold. **This deliberately differs from `menu_view.py`'s title counter**, which counts everything because that screen is the full inventory the owner administers, hidden rows included. Two different questions ("what do I manage" vs "what am I selling"); don't unify them. The `visible` filter is explicit in the query rather than left to RLS, because the admin's own session *can* see hidden rows — without it the number would be inflated for the one person who uses the panel. `_texto_platillos()`/`_texto_categorias()` handle singular/plural.
  - **`Lo último de tu menú`**: real feed from `PlatilloDAO.obtener_recientes(3)`, capped at 3 rows — verified by screenshot to fit the card's fixed `height=185` without crowding or overflowing; don't raise that cap without re-checking it fits. Each row compares `created_at == updated_at` to label itself "Nuevo" (green dot `#7d8545`) or "Editado" (orange dot `#c86a28`), and `_tiempo_relativo()` renders "hace N minutos/horas", "ayer", or "el D de mes" — it converts Supabase's UTC timestamp to local time before comparing calendar days, so "ayer" lines up with the owner's actual day, not UTC's.
  - **`"Agregar un producto nuevo"`** shortcut: now calls `cambiar_vista(ruta, abrir_dialogo_nuevo=True)` instead of just `cambiar_vista("menu")` — see `cambiar_vista` in Architecture below.

Both dynamic cards load async (`page.run_task` + `asyncio.to_thread`, mirroring `menu_view.py`), each in its own try/except so one card's failure doesn't blank the rest of Inicio — same loading/error visual language as the rest of the project (gold `ProgressRing`, `#f7e4e3`/`#d9534f`/`#a33c39` for errors), just a compact icon+text row instead of a full bordered box since these cards are small. Nothing needs manual invalidation when a platillo changes: `HomeView` has no cache and is rebuilt from scratch on every navigation like every other view, so navigating back to Inicio after an add/edit/hide already re-fetches for free.

`_crear_tarjeta_stat(titulo, valor, subtitulo, icono)` (unchanged, still used by the 3 fake cards) and `_crear_boton_atajo(titulo, subtitulo, icono, color_icono, ruta, abrir_dialogo_nuevo=False)` (gained that last param) remain the two general-purpose builders.

**Schema**: `public.platillos` gained `updated_at` + `trg_platillos_updated_at` in Phase 2.7 specifically so this card could detect edits, not just additions — see the schema paragraph earlier in this file. This was a deliberate owner decision, asked and confirmed before the DDL ran, not an assumption.

## Running the app

```bash
python main.py
```

This launches the Flet desktop app (`ft.run(main, assets_dir=".")` in `main.py`), which opens a maximized native window titled "Taku Monky - Panel" — showing `SesionView` (login) if there's no valid saved session, or the usual Sidebar+panel if there is. See `models/sesion.py`.

There is no build step, linter, formatter, or test suite configured in this repo (no `pyproject.toml`, no test files). Dependencies are pinned in `requirements.txt` (`flet`, `supabase`, `python-dotenv`, `httpx`, `pillow`) and installed in the active Python environment — install with `pip install -r requirements.txt` if a fresh environment is missing any of them (`supabase`/`python-dotenv` in particular aren't part of a bare Python install).

## Architecture

**MVC-ish structure, single window, no real routing:**

- `main.py` — entry point; creates the Flet `Page` and hands it to `MainController`.
- `controllers/main_controller.py` — `MainController` acts as the app's router/state holder (referred to as `router` throughout the view/component code). It owns:
  - `self.vista_actual` — name of the currently active view (`"home"`, `"menu"`, `"agente_financiero"`, `"contenido"`, `"ajustes"`, `"biblioteca"`).
  - `self.view_switcher` — an `ft.AnimatedSwitcher` that swaps view content with a scale transition.
  - `cambiar_vista(vista: str, abrir_dialogo_nuevo: bool = False)` — the *only* navigation mechanism: instantiates the matching view class, sets it as the switcher's content, and rebuilds the `Sidebar` so its active-button highlighting stays in sync. There is no separate router/state-management library. `abrir_dialogo_nuevo` (added Phase 2.7) is a one-shot, non-persisted flag forwarded straight into `MenuView`'s constructor when `vista == "menu"` — it exists only so `home_view.py`'s "Agregar un producto nuevo" shortcut can land on Menú with the add dialog already open. Every other caller (the sidebar, the other atajo, every `cambiar_vista("contenido")` call) omits it and gets the unchanged default behavior — there's no router-level state that could leak into a later, unrelated navigation.
- `views/*.py` — one file per screen (`home_view.py`, `menu_view.py`, `agenteIA_view.py`, `contenido_view.py`, `ajustes_view.py`, `biblioteca_view.py`). Every view follows the same shape:
  ```python
  class SomeView(ft.Container):
      def __init__(self, router):
          super().__init__()
          self.router = router
          self.expand = True
          self.height = float("inf")
          self.bgcolor = "#fbf5e9"
          self.content = ft.Column(...)  # built inline in __init__
  ```
  Views are rebuilt from scratch on every navigation (no persistent state between visits) and call back into the app only through `self.router` (e.g. `self.router.cambiar_vista(...)`, `self.router.page`).
- `views/components/sidebar.py` — `Sidebar(router)` is the persistent left nav (also takes `router` and reads `router.vista_actual` to highlight the active item). Includes a hardcoded WhatsApp support link.
- `views/components/dialogo_platillo.py` — `DialogoPlatillo`, the add/edit form dialog used by `menu_view.py` (Phase 2.6). See the dedicated section under Design rules above — it's not just a form, it has two non-obvious gotchas (the explicit close button, and the `_ocupado` ordering) worth reading before touching it.
- `models/` — the data layer:
  - `supabase_client.py` — the one shared `Client`, created with `SUPABASE_ANON_KEY` via `create_client()`. Write access comes from whatever session is active on `client.auth`, not from the key. Also exposes `SUPABASE_ADMIN_EMAIL` (read from `.env`) so `SesionView` can prefill the email field.
  - `sesion.py` — `guardar`/`cargar`/`borrar`/`restaurar` persist the session (access_token, refresh_token, expires_at only — never the password) to `%LOCALAPPDATA%\TakuMonky\sesion.json`, outside the repo. `restaurar(client)` calls `client.auth.set_session(...)`, which refreshes the token itself if it expired; a failure there clears the saved file and returns `False`.
  - `platillo_dao.py` — `PlatilloDAO`, a DAO class following the `VentaDAO` pattern from `EJEMPLOS/ia_controller.py`. `obtener_todos()` (Phase 2.1-2.5): a blocking `client.from_("platillos").select(...)` call, `select()`-ing only the columns `menu_view.py` paints (`id, nombre, descripcion, categoria, precio, visible, image_url` — never `select('*')`, same rule as `EJEMPLOS/catalog-cache.js`), ordered by `orden` then `id`. `crear`/`actualizar`/`eliminar`/`cambiar_visibilidad` (Phase 2.6) round out the CRUD — see the dedicated "RLS silent-failure gotcha" note under Design rules above before touching any of them. `obtener_estadisticas()` and `obtener_recientes()` (Phase 2.7) back `home_view.py`'s two dynamic cards — the former makes 4 `count="exact", head=True` requests (1 total + 1 per fixed category), all filtered to `visible = true`, and never downloads row data; the latter selects `id, nombre, created_at, updated_at` ordered by `updated_at desc` and leaves the Nuevo/Editado interpretation to the view, not the DAO. None of the methods in this file catch exceptions themselves; failures are left to rise to the caller (`menu_view.py`/`dialogo_platillo.py`/`home_view.py`, via `asyncio.to_thread`), same division of labor as `sign_in_with_password` in `sesion_view.py`.
- `assets/` — images referenced by views/sidebar (e.g. `logomonky.png`) via relative `assets/...` paths, since `assets_dir="."` in `main.py`.

**Adding a new screen** means: create `views/new_view.py` following the pattern above, import it in `main_controller.py`, add an `elif` branch in `cambiar_vista`, and add a nav button in `sidebar.py` via `self._crear_boton_menu(...)`.

**Exception — the login screen** (`views/sesion_view.py`, built in Phase 2.0): it is a *startup* screen, not a section of the panel, so it does **not** go through `cambiar_vista` and gets no sidebar button. `MainController.__init__` calls `models/sesion.py`'s `restaurar()` and decides between `mostrar_login()` (page holds only `SesionView`, full window, no `Sidebar`) and `mostrar_panel()` (builds `Sidebar` + content `Row` — this assembly now lives inside `mostrar_panel()` itself, not `__init__`, so it never exists unless there's a session). This means the app skips straight to the panel on relaunch as long as the saved session is still valid — that's intentional (see the roadmap's "Sesión viva"), not a bug; forcing a fresh login every launch would need an explicit product decision to change it. `cerrar_sesion()` (clears the saved session + signs out + calls `mostrar_login()`) exists on the router already but has no caller yet — it's meant to be wired to a button in `ajustes_view.py` (Phase 7). `cambiar_vista` itself stays unchanged.

**Styling convention**: colors are hardcoded hex strings inline on controls (no theme/constants file) — the recurring palette is cream background `#fbf5e9`, near-black sidebar `#0d0905`, and gold/accent `#f4ca83`. `font_family="Georgia"` with `italic=True` is used for display headings. Match this convention rather than introducing `ft.Theme` or a separate style module unless asked.

**Language**: UI copy, comments, and variable/method names throughout the codebase are in Spanish (e.g. `cambiar_vista`, `vista_actual`, `_crear_boton_menu`). Follow this convention for consistency when adding code.
