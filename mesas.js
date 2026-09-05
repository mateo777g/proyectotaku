// ================================================================
// mesas.js — Fase 5, sistema de mesas (registro de ventas)
// Solo lo usa mesas.html. Es una herramienta de STAFF, no una página
// pública: por eso este archivo NO comparte nada con catalogo.js (ni
// el cliente de Supabase, ni el caché, ni iniciarNavbar()) — necesita
// sesión real y persistida, justo lo que catalogo.js desactiva a
// propósito (ver la nota de persistSession:false ahí). El patrón de
// referencia es EJEMPLOS/lilshop.html (login con Supabase Auth +
// CRUD directo desde el navegador), no las páginas del menú público.
// ================================================================

const SUPABASE_URL = "https://yiafxeibhqyghrkwvmju.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlpYWZ4ZWliaHF5Z2hya3d2bWp1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc2NTQwNzUsImV4cCI6MjEwMzIzMDA3NX0.9y0KMot1CllL5ix_PRv5ouaVXJ-engikGbUsbI4OKWg";
// La anon key es pública a propósito (igual que en catalogo.js) — por
// sí sola no puede leer ni escribir NADA en ventas/venta_items (esas
// tablas no tienen ninguna política para el rol anon). El acceso de
// verdad lo da la sesión de Supabase Auth que se abre abajo.
const ADMIN_EMAIL = "matthewsantreys13@gmail.com";

const { createClient } = supabase;
// A diferencia de catalogo.js, AQUÍ SÍ se necesita sesión persistida
// (el mesero no debería tener que loguearse cada vez que recarga) —
// por eso se usan las opciones por defecto de createClient en vez de
// desactivar auth como hace el menú público.
const _supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ----------------------------------------------------------------
// Utilidades — mismas que ya usa catalogo.js, copiadas aquí a
// propósito (ver nota de arriba: este archivo no importa nada de
// catalogo.js).
// ----------------------------------------------------------------
function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto == null ? "" : String(texto);
  return div.innerHTML;
}

function formatearPrecio(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return "$0";
  if (Number.isInteger(numero)) return `$${numero.toLocaleString("es-MX")}`;
  return `$${numero.toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function tiempoRelativo(fechaIso) {
  const ms = Date.now() - new Date(fechaIso).getTime();
  const min = Math.max(0, Math.round(ms / 60000));
  if (min < 1) return "justo ahora";
  if (min < 60) return `hace ${min} min`;
  const horas = Math.round(min / 60);
  return `hace ${horas} h`;
}

// Toast simple — mismo papel que mostrarMensaje() en lilshop.html.
const toastEl = document.getElementById("tk-mesas-toast");
let toastTimeoutId = null;
function mostrarToast(texto, tipo) {
  if (toastTimeoutId) clearTimeout(toastTimeoutId);
  if (!toastEl) return;
  toastEl.textContent = texto;
  toastEl.className = "tk-mesas-toast tk-mesas-toast--" + (tipo || "error");
  toastEl.hidden = false;
  toastTimeoutId = setTimeout(() => { toastEl.hidden = true; }, 4000);
}

// ----------------------------------------------------------------
// 1. LOGIN / SESIÓN
// ----------------------------------------------------------------
const elLogin = document.getElementById("tk-mesas-login");
const elApp = document.getElementById("tk-mesas-app");
const formLogin = document.getElementById("tk-mesas-form-login");
const campoPassword = document.getElementById("tk-mesas-password");
const zonaErrorLogin = document.getElementById("tk-mesas-login-error");
const botonEntrar = document.getElementById("tk-mesas-boton-entrar");

window.addEventListener("load", async () => {
  const { data: { session } } = await _supabase.auth.getSession();
  if (session) {
    mostrarApp();
  } else {
    elLogin.hidden = false;
  }
});

formLogin.addEventListener("submit", async (e) => {
  e.preventDefault();
  zonaErrorLogin.hidden = true;
  botonEntrar.disabled = true;
  botonEntrar.textContent = "Entrando...";

  const { error } = await _supabase.auth.signInWithPassword({
    email: ADMIN_EMAIL,
    password: campoPassword.value,
  });

  if (error) {
    zonaErrorLogin.textContent = "Contraseña incorrecta. Intenta de nuevo.";
    zonaErrorLogin.hidden = false;
    botonEntrar.disabled = false;
    botonEntrar.textContent = "Entrar";
    return;
  }

  campoPassword.value = "";
  mostrarApp();
});

function mostrarApp() {
  elLogin.hidden = true;
  elApp.hidden = false;
  botonEntrar.disabled = false;
  botonEntrar.textContent = "Entrar";
  mostrarVistaLista();
}

document.getElementById("tk-mesas-cerrar-sesion").addEventListener("click", async () => {
  await _supabase.auth.signOut();
  elApp.hidden = true;
  _ventaActual = null;
  elLogin.hidden = false;
});

// ----------------------------------------------------------------
// 2. VISTA LISTA — mesas abiertas + abrir/reanudar una mesa
// ----------------------------------------------------------------
const vistaLista = document.getElementById("tk-mesas-vista-lista");
const vistaOrden = document.getElementById("tk-mesas-vista-orden");
const contenedorLista = document.getElementById("tk-mesas-lista");

// Catálogo de mesas (public.mesas, Fase 5.1) de la última carga — id -> fila.
// Se necesita en memoria para que abrirMesaNueva() sepa el nombre real sin
// tener que meterlo en el onclick como texto (mismo motivo que
// cuentasPorId en EJEMPLOS/lilshop.html: un nombre con comilla simple
// rompería el atributo onclick si se interpolara directo).
let _mesasCache = [];

async function mostrarVistaLista() {
  vistaOrden.hidden = true;
  vistaLista.hidden = false;
  _ventaActual = null;
  await cargarMesas();
}

async function cargarMesas() {
  contenedorLista.innerHTML = '<div class="tk-mesas-estado"><div class="tk-mesas-spinner"></div><p>Cargando mesas...</p></div>';
  try {
    // Dos consultas en paralelo: el catálogo fijo de mesas (Fase 5.1,
    // administrado desde el panel de Flet) y qué ventas están abiertas
    // ahorita — se cruzan del lado del cliente para pintar cada mesa como
    // "Disponible" u "Ocupada", sin necesitar una vista/join en Supabase
    // para algo tan chico (5-10 mesas).
    const [{ data: mesas, error: errorMesas }, { data: abiertas, error: errorAbiertas }] =
      await Promise.all([
        _supabase.from("mesas").select("id, nombre, orden").order("orden").order("id"),
        _supabase.from("ventas").select("id, mesa, total, updated_at").eq("estado", "abierta"),
      ]);
    if (errorMesas) throw errorMesas;
    if (errorAbiertas) throw errorAbiertas;

    _mesasCache = mesas || [];

    if (_mesasCache.length === 0) {
      contenedorLista.innerHTML = '<div class="tk-mesas-vacio">Todavía no hay ninguna mesa configurada.<br>Se agregan desde el panel de Flet, sección "Mesas".</div>';
      return;
    }

    // mesa (texto libre en ventas) vs nombre (catálogo fijo) se comparan
    // sin distinguir mayúsculas/espacios — mismo criterio que ya usaba el
    // "reanudar" del campo libre que existía antes de esta lista fija.
    const abiertaPorNombre = new Map(
      (abiertas || []).map((v) => [v.mesa.trim().toLowerCase(), v])
    );

    contenedorLista.innerHTML = _mesasCache.map((m) => {
      const abierta = abiertaPorNombre.get(m.nombre.trim().toLowerCase());
      if (abierta) {
        return `
          <button class="tk-mesas-tarjeta tk-mesas-tarjeta--ocupada" onclick="abrirVentaExistente(${abierta.id})">
            <span class="tk-mesas-tarjeta-mesa">${escapeHtml(m.nombre)}</span>
            <span class="tk-mesas-tarjeta-estado tk-mesas-tarjeta-estado--ocupada">Ocupada · ${formatearPrecio(abierta.total)}</span>
            <span class="tk-mesas-tarjeta-tiempo">${tiempoRelativo(abierta.updated_at)}</span>
          </button>
        `;
      }
      return `
        <button class="tk-mesas-tarjeta" onclick="abrirMesaNueva(${m.id})">
          <span class="tk-mesas-tarjeta-mesa">${escapeHtml(m.nombre)}</span>
          <span class="tk-mesas-tarjeta-estado tk-mesas-tarjeta-estado--disponible">Disponible</span>
        </button>
      `;
    }).join("");
  } catch (err) {
    console.error("Error al cargar mesas:", err);
    contenedorLista.innerHTML = '<div class="tk-mesas-error">No se pudieron cargar las mesas. Revisa tu conexión e intenta de nuevo.</div>';
  }
}

async function abrirMesaNueva(mesaId) {
  const mesa = _mesasCache.find((m) => m.id === mesaId);
  if (!mesa) return;
  try {
    const { data: nueva, error } = await _supabase
      .from("ventas")
      .insert([{ mesa: mesa.nombre }])
      .select()
      .single();
    if (error) throw error;
    await abrirVentaExistente(nueva.id);
  } catch (err) {
    console.error("Error al abrir mesa:", err);
    mostrarToast("No se pudo abrir la mesa: " + (err.message || "error desconocido"), "error");
  }
}

// ----------------------------------------------------------------
// 3. VISTA ORDEN — la mesa actual: items, total, agregar/quitar, cerrar
// ----------------------------------------------------------------
let _ventaActual = null; // { id, mesa, total, items: [...] }

async function abrirVentaExistente(ventaId) {
  try {
    const { data: venta, error: errorVenta } = await _supabase
      .from("ventas")
      .select("id, mesa, total, estado")
      .eq("id", ventaId)
      .single();
    if (errorVenta) throw errorVenta;

    const { data: items, error: errorItems } = await _supabase
      .from("venta_items")
      .select("id, platillo_id, nombre, precio_unitario, cantidad")
      .eq("venta_id", ventaId)
      .order("created_at", { ascending: true });
    if (errorItems) throw errorItems;

    _ventaActual = { ...venta, items: items || [] };
    vistaLista.hidden = true;
    vistaOrden.hidden = false;
    renderOrden();
  } catch (err) {
    console.error("Error al abrir la mesa:", err);
    mostrarToast("No se pudo abrir esa mesa: " + (err.message || "error desconocido"), "error");
  }
}

function calcularTotal() {
  return _ventaActual.items.reduce((acc, it) => acc + it.precio_unitario * it.cantidad, 0);
}

async function guardarTotal() {
  _ventaActual.total = calcularTotal();
  const { error } = await _supabase
    .from("ventas")
    .update({ total: _ventaActual.total })
    .eq("id", _ventaActual.id);
  if (error) console.error("No se pudo actualizar el total:", error);
}

function renderOrden() {
  document.getElementById("tk-mesas-orden-titulo").textContent = _ventaActual.mesa;

  const cont = document.getElementById("tk-mesas-orden-items");
  if (_ventaActual.items.length === 0) {
    cont.innerHTML = '<div class="tk-mesas-vacio">Todavía no hay productos. Toca "Agregar producto" para empezar.</div>';
  } else {
    cont.innerHTML = _ventaActual.items.map((it) => `
      <div class="tk-mesas-item">
        <div class="tk-mesas-item-info">
          <span class="tk-mesas-item-nombre">${escapeHtml(it.nombre)}</span>
          <span class="tk-mesas-item-precio">${formatearPrecio(it.precio_unitario)} c/u</span>
        </div>
        <div class="tk-mesas-item-controles">
          <button type="button" class="tk-mesas-paso" onclick="cambiarCantidad(${it.id}, -1)">−</button>
          <span class="tk-mesas-item-cantidad">${it.cantidad}</span>
          <button type="button" class="tk-mesas-paso" onclick="cambiarCantidad(${it.id}, 1)">+</button>
          <span class="tk-mesas-item-subtotal">${formatearPrecio(it.precio_unitario * it.cantidad)}</span>
          <button type="button" class="tk-mesas-quitar" title="Quitar" onclick="eliminarItem(${it.id})">✕</button>
        </div>
      </div>
    `).join("");
  }

  document.getElementById("tk-mesas-orden-total").textContent = formatearPrecio(calcularTotal());
}

async function cambiarCantidad(itemId, delta) {
  const item = _ventaActual.items.find((it) => it.id === itemId);
  if (!item) return;

  const nuevaCantidad = item.cantidad + delta;
  try {
    if (nuevaCantidad <= 0) {
      const { error } = await _supabase.from("venta_items").delete().eq("id", itemId);
      if (error) throw error;
      _ventaActual.items = _ventaActual.items.filter((it) => it.id !== itemId);
    } else {
      const { error } = await _supabase
        .from("venta_items")
        .update({ cantidad: nuevaCantidad })
        .eq("id", itemId);
      if (error) throw error;
      item.cantidad = nuevaCantidad;
    }
    renderOrden();
    await guardarTotal();
  } catch (err) {
    console.error("Error al cambiar cantidad:", err);
    mostrarToast("No se pudo actualizar: " + (err.message || "error desconocido"), "error");
  }
}

async function eliminarItem(itemId) {
  try {
    const { error } = await _supabase.from("venta_items").delete().eq("id", itemId);
    if (error) throw error;
    _ventaActual.items = _ventaActual.items.filter((it) => it.id !== itemId);
    renderOrden();
    await guardarTotal();
  } catch (err) {
    console.error("Error al quitar producto:", err);
    mostrarToast("No se pudo quitar el producto: " + (err.message || "error desconocido"), "error");
  }
}

document.getElementById("tk-mesas-volver").addEventListener("click", mostrarVistaLista);

document.getElementById("tk-mesas-cancelar-mesa").addEventListener("click", async () => {
  if (!confirm(`¿Borrar "${_ventaActual.mesa}" por completo? Se pierde todo lo que lleva. Esto no se puede deshacer.`)) return;
  try {
    const { error } = await _supabase.from("ventas").delete().eq("id", _ventaActual.id);
    if (error) throw error;
    mostrarToast("Mesa cancelada.", "success");
    mostrarVistaLista();
  } catch (err) {
    console.error("Error al cancelar la mesa:", err);
    mostrarToast("No se pudo cancelar: " + (err.message || "error desconocido"), "error");
  }
});

document.getElementById("tk-mesas-cerrar-venta").addEventListener("click", async () => {
  if (_ventaActual.items.length === 0) {
    mostrarToast("Agrega al menos un producto antes de cerrar la venta.", "error");
    return;
  }
  if (!confirm(`¿Cerrar la venta de "${_ventaActual.mesa}" por ${formatearPrecio(calcularTotal())}?`)) return;

  try {
    const { error } = await _supabase
      .from("ventas")
      .update({ estado: "cerrada", total: calcularTotal(), cerrada_at: new Date().toISOString() })
      .eq("id", _ventaActual.id);
    if (error) throw error;
    mostrarToast("Venta cerrada. ¡Buen provecho!", "success");
    mostrarVistaLista();
  } catch (err) {
    console.error("Error al cerrar la venta:", err);
    mostrarToast("No se pudo cerrar la venta: " + (err.message || "error desconocido"), "error");
  }
});

// ----------------------------------------------------------------
// 4. SELECTOR DE PLATILLOS — modal para agregar productos a la orden
// ----------------------------------------------------------------
let _platillosCache = null; // se pide una sola vez por sesión de la página

const elSelector = document.getElementById("tk-mesas-selector");
const contSelector = document.getElementById("tk-mesas-selector-lista");
const campoBuscarSelector = document.getElementById("tk-mesas-selector-buscar");

document.getElementById("tk-mesas-agregar-producto").addEventListener("click", abrirSelector);
document.getElementById("tk-mesas-selector-cerrar").addEventListener("click", cerrarSelector);
document.getElementById("tk-mesas-selector-overlay").addEventListener("click", cerrarSelector);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !elSelector.hidden) cerrarSelector();
});

async function abrirSelector() {
  elSelector.hidden = false;
  campoBuscarSelector.value = "";
  campoBuscarSelector.focus();

  if (!_platillosCache) {
    contSelector.innerHTML = '<div class="tk-mesas-estado"><div class="tk-mesas-spinner"></div><p>Cargando el menú...</p></div>';
    try {
      const { data, error } = await _supabase
        .from("platillos")
        .select("id, nombre, categoria, precio, visible")
        .order("categoria", { ascending: true })
        .order("orden", { ascending: true });
      if (error) throw error;
      _platillosCache = data || [];
    } catch (err) {
      console.error("Error al cargar el menú:", err);
      contSelector.innerHTML = '<div class="tk-mesas-error">No se pudo cargar el menú.</div>';
      return;
    }
  }
  renderSelector();
}

function cerrarSelector() {
  elSelector.hidden = true;
}

campoBuscarSelector.addEventListener("input", renderSelector);

function renderSelector() {
  if (!_platillosCache) return;
  const filtro = campoBuscarSelector.value.trim().toLowerCase();
  const lista = filtro
    ? _platillosCache.filter((p) => p.nombre.toLowerCase().includes(filtro))
    : _platillosCache;

  if (lista.length === 0) {
    contSelector.innerHTML = '<div class="tk-mesas-vacio">Sin resultados.</div>';
    return;
  }

  const porCategoria = {};
  lista.forEach((p) => {
    (porCategoria[p.categoria] = porCategoria[p.categoria] || []).push(p);
  });

  contSelector.innerHTML = Object.keys(porCategoria).map((cat) => `
    <div class="tk-mesas-selector-grupo">
      <h4>${escapeHtml(cat)}</h4>
      ${porCategoria[cat].map((p) => `
        <button type="button" class="tk-mesas-selector-item" onclick="agregarPlatillo(${p.id})">
          <span>${escapeHtml(p.nombre)}${p.visible ? "" : " (oculto)"}</span>
          <span class="tk-mesas-selector-item-precio">${formatearPrecio(p.precio)}</span>
        </button>
      `).join("")}
    </div>
  `).join("");
}

async function agregarPlatillo(platilloId) {
  const platillo = _platillosCache.find((p) => p.id === platilloId);
  if (!platillo || !_ventaActual) return;

  try {
    // Si el platillo ya está en la orden, solo se sube la cantidad en vez
    // de insertar una segunda fila para el mismo producto.
    const existente = _ventaActual.items.find((it) => it.platillo_id === platilloId);
    if (existente) {
      await cambiarCantidad(existente.id, 1);
      return;
    }

    const { data: nuevoItem, error } = await _supabase
      .from("venta_items")
      .insert([{
        venta_id: _ventaActual.id,
        platillo_id: platillo.id,
        nombre: platillo.nombre,
        precio_unitario: platillo.precio,
        cantidad: 1,
      }])
      .select()
      .single();
    if (error) throw error;

    _ventaActual.items.push(nuevoItem);
    renderOrden();
    await guardarTotal();
  } catch (err) {
    console.error("Error al agregar producto:", err);
    mostrarToast("No se pudo agregar: " + (err.message || "error desconocido"), "error");
  }
}
