// ================================================================
// carta.js — "carta" de celular del index.html (Fase 4.3), SOLO por
// debajo de 1024px. En escritorio esta sección se queda en display:none
// (ver style.css) y ni siquiera se arma su DOM ni se piden fotos aquí —
// mismo criterio que carrusel.js, pero al revés (ese archivo es solo de
// escritorio; este es solo de celular/tablet chico).
//
// Archivo APARTE de catalogo.js (compartido por las 4 páginas) y de
// carrusel.js (el equivalente de escritorio) — depende de globals que
// expone catalogo.js (obtenerCatalogo, agruparPorCategoria, escapeHtml,
// formatearPrecio, iniciarAutoRefresco), por eso en index.html
// <script src="catalogo.js"> va ANTES que <script src="carta.js">.
//
// Pedido explícito del dueño (2026-09-03, con una maqueta en imagen):
// fondo negro, foto del platillo YA RECORTADA (sin fondo, pero
// CONSERVANDO su tabla/plato — esa versión la genera el panel de Flet con
// rembg, ver models/cloudflare_storage.py; aquí solo se consume
// image_url_recortada, nunca se procesa nada en el navegador), autoplay +
// swipe, puntitos, y una lista de renglones con línea punteada + precio
// debajo, con el renglón del platillo activo resaltado en dorado.
// *** SIN FLECHAS a los lados *** — el dueño lo remarcó varias veces.
// Solo categoría Platillos. El tope de 5 lo aplica de verdad el panel al
// generar el recorte (ver dialogo_platillo.py) — el `.slice()` de aquí
// abajo es solo un respaldo, nunca la fuente de la verdad de ese límite.
// ================================================================

// ⚠️ Mismo valor EXACTO que el "@media (min-width: 1024px)" de style.css y
// que _CARRUSEL_BREAKPOINT en carrusel.js — ahora son 3 lugares que deben
// quedar sincronizados (ver la nota grande junto a ese bloque en
// style.css: si tocas uno de los tres, toca los otros dos). Al revés que
// carrusel.js: aquí NO se construye nada cuando el viewport SÍ es de
// escritorio.
const _CARTA_BREAKPOINT_DESKTOP = "(min-width: 1024px)";

const _CARTA_AUTOPLAY_MS = 5000; // mismo valor que _CARRUSEL_AUTOPLAY_MS del carrusel de PC
const _CARTA_LIMITE = 5;

// -------- Efecto de salida de la foto (3 sep 2026) --------
// Pedido del dueño: que la foto NO se vea rebanada por el borde de la
// ventanita al deslizar. Se resolvió dejándola deslizar (el gesto se
// siente igual que antes) pero apagándola y encogiéndola conforme se
// aleja del centro, de modo que se apaga ANTES de alcanzar la orilla.
//
// _CARTA_DERIVA: cuánto se mueve la foto, como fracción del ancho del
//   carril, cuando su slide se aleja un slide completo. Es MENOR que 1 a
//   propósito: el slide sí recorre todo el ancho (eso lo hace el scroll
//   nativo y no se toca), pero la foto de adentro solo "deriva" un poco,
//   y ese margen que gana es justo lo que evita que toque el borde.
// _CARTA_ENCOGE: cuánto se encoge en ese mismo recorrido (14%).
//
// ⚠️ Van amarrados al `max-width: 84%` de .tk-carta-foto-slide img en
// style.css — la cuenta completa está comentada ahí. Resumen: el borde
// más lejano que alcanza la foto es 0.12 + 0.42*0.86 = 0.481·W, contra el
// 0.5·W del carril. Si tocas uno de los tres números, rehaz esa cuenta o
// vuelve el corte que se acaba de arreglar.
const _CARTA_DERIVA = 0.12;
const _CARTA_ENCOGE = 0.14;

function _cartaPrefiereMovimientoReducido() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function _cartaFotoSlideHTML(platillo) {
  const nombre = escapeHtml(platillo.nombre || "");
  // Estos platillos ya vienen filtrados a "sí tienen image_url_recortada"
  // (ver cargar() más abajo) — este fallback es solo por si esa URL
  // puntual deja de cargar (borrada a mano, sin internet), mismo
  // placeholder que usa el resto del sitio, nunca un ícono roto.
  const imagen = escapeHtml(platillo.image_url_recortada || "assets/sin-foto.png");
  return `
    <div class="tk-carta-foto-slide">
      <img src="${imagen}" alt="${nombre}" loading="lazy"
           onerror="this.onerror=null; this.src='assets/sin-foto.png';">
    </div>
  `;
}

function _cartaRenglonHTML(platillo, idx) {
  const nombre = escapeHtml(platillo.nombre || "");
  const precio = formatearPrecio(platillo.precio);
  return `
    <div class="tk-carta-renglon" data-indice="${idx}">
      <span class="tk-carta-renglon-nombre">${nombre}</span>
      <span class="tk-carta-renglon-puntos"></span>
      <span class="tk-carta-renglon-precio">${precio}</span>
    </div>
  `;
}

// Firma barata para no reconstruir el DOM en cada tick de
// iniciarAutoRefresco() (cada 30s) cuando nada cambió de verdad — mismo
// truco que _firmaLista() en carrusel.js (si no, cada tick reiniciaría el
// autoplay y el scroll actual, y se sentiría como un parpadeo).
function _firmaListaCarta(lista) {
  return lista.map((p) => p.id).join(",");
}

async function iniciarCarta() {
  // La carta es EXCLUSIVA de celular/tablet chico. En escritorio ni
  // siquiera se arma el DOM ni se piden las fotos recortadas — de
  // cualquier forma la sección está en display:none ahí (ver style.css).
  if (window.matchMedia(_CARTA_BREAKPOINT_DESKTOP).matches) return;

  const seccion = document.getElementById("carta-menu");
  const fotos = document.getElementById("carta-fotos");
  const titulo = document.getElementById("carta-titulo");
  const lista = document.getElementById("carta-lista");
  const dots = document.getElementById("carta-dots");
  if (!seccion || !fotos || !titulo || !lista || !dots) return;

  let items = [];
  let indiceActual = 0;
  let temporizador = null;
  let sincronizando = null; // debounce del listener de scroll (swipe manual)

  function detenerAutoplay() {
    if (temporizador) {
      clearInterval(temporizador);
      temporizador = null;
    }
  }
  function iniciarAutoplay() {
    detenerAutoplay();
    // Igual que el carrusel de PC: con 0-1 platillo no hay a dónde avanzar.
    // prefers-reduced-motion apaga el AUTOPLAY nada más — el swipe manual
    // sigue funcionando igual (el resto del sitio ya respeta esta
    // preferencia solo para movimiento decorativo/automático).
    if (items.length <= 1 || _cartaPrefiereMovimientoReducido()) return;
    temporizador = setInterval(() => irA(indiceActual + 1), _CARTA_AUTOPLAY_MS);
  }

  function pintar() {
    titulo.textContent = items[indiceActual] ? items[indiceActual].nombre || "" : "";
    lista.querySelectorAll(".tk-carta-renglon").forEach((renglon, i) => {
      renglon.classList.toggle("tk-carta-renglon-activo", i === indiceActual);
    });
    dots.querySelectorAll(".tk-cf-dot").forEach((dot, i) => {
      dot.classList.toggle("tk-cf-dot-activo", i === indiceActual);
    });
  }

  // Posición de scroll exacta que deja alineado al slide `idx`. Se lee de
  // la geometría REAL del slide (su offsetLeft dentro del carril) y NO de
  // `idx * clientWidth`: hoy dan lo mismo (slides de flex:0 0 100%, sin
  // gap ni padding en el carril), pero si algún día se le agrega un gap o
  // un padding, la fórmula aritmética se desincroniza en silencio y la
  // geometría real no.
  //
  // ⚠️ offsetLeft se mide contra el offsetParent, así que .tk-carta-fotos
  // TIENE que ser position:relative en style.css (ahí está la nota larga).
  // Sin eso se medía contra <body> y le metía el desplazamiento
  // horizontal de toda la sección a un número que scrollTo() interpreta
  // como coordenada del carril.
  function _posicionDe(idx) {
    const slide = fotos.children[idx];
    return slide ? slide.offsetLeft : 0;
  }

  // Inversa de _posicionDe(): qué slide quedó alineado después de que el
  // usuario deslizó a mano. Busca el más cercano por su posición real, en
  // vez de dividir entre clientWidth, para que las dos direcciones
  // (pintar → scroll y scroll → pintar) usen SIEMPRE la misma fuente de
  // verdad y no puedan desincronizarse entre ellas.
  function _indiceMasCercano() {
    let mejor = 0;
    let mejorDistancia = Infinity;
    for (let i = 0; i < fotos.children.length; i++) {
      const distancia = Math.abs(fotos.children[i].offsetLeft - fotos.scrollLeft);
      if (distancia < mejorDistancia) {
        mejorDistancia = distancia;
        mejor = i;
      }
    }
    return mejor;
  }

  // Recalcula opacidad/escala/deriva de cada foto segun que tan lejos del
  // centro del carril quedo SU slide. p = 0 -> centrada; p = ±1 -> a un
  // slide completo de distancia. La opacidad es 1 - |p| para que en el
  // punto medio de un deslizamiento las dos fotos vayan a 0.5 y sumen 1:
  // asi nunca hay un hueco negro entre una y otra.
  function _actualizarEfecto() {
    const ancho = fotos.clientWidth;
    if (!ancho) return;
    const centro = fotos.scrollLeft + ancho / 2;
    for (const slide of fotos.children) {
      const img = slide.querySelector("img");
      if (!img) continue; // los estados de carga/error no llevan <img>
      const p = (slide.offsetLeft + ancho / 2 - centro) / ancho;
      const lejania = Math.min(1, Math.abs(p));

      // El slide YA se movio p*ancho por su cuenta: eso lo hace el scroll
      // nativo y no se toca (es lo que da el swipe con inercia y el snap).
      // Queremos que la FOTO de adentro se separe del centro mucho menos
      // que eso, solo _CARTA_DERIVA del recorrido, asi que el transform no
      // suma movimiento: RESTA la diferencia entre lo que el slide ya se
      // movio y lo poco que queremos que se note.
      //   correccion = (deseado) - (lo que ya se movio) -> siempre negativa
      // Si esto se escribe como una suma (p * DERIVA * ancho, sin restar el
      // recorrido del slide) la foto se mueve MAS que el slide en vez de
      // menos, y el corte que este efecto venia a resolver empeora.
      const deseado = p * _CARTA_DERIVA * ancho;
      const correccion = deseado - p * ancho;

      img.style.opacity = String(Math.max(0, 1 - lejania));
      img.style.transform =
        "translateX(" + correccion.toFixed(1) + "px)" +
        " scale(" + (1 - lejania * _CARTA_ENCOGE).toFixed(3) + ")";
    }
  }

  // El scroll dispara muchisimos eventos por segundo; sin esto se
  // recalcularia el efecto varias veces por cuadro para nada. Con rAF se
  // hace una sola vez por cuadro, justo antes de pintar.
  let efectoPendiente = false;
  function _pedirEfecto() {
    if (efectoPendiente) return;
    efectoPendiente = true;
    requestAnimationFrame(() => {
      efectoPendiente = false;
      _actualizarEfecto();
    });
  }

  function irA(idx) {
    if (items.length === 0) return;
    indiceActual = ((idx % items.length) + items.length) % items.length;
    fotos.scrollTo({
      left: _posicionDe(indiceActual),
      behavior: _cartaPrefiereMovimientoReducido() ? "auto" : "smooth",
    });
    pintar();
  }

  // El swipe en sí ya lo hace scroll-snap de forma nativa (sin JS) — este
  // listener solo RESINCRONIZA título/lista/puntitos con la foto que
  // quedó centrada después de que el usuario desliza a mano.
  fotos.addEventListener(
    "scroll",
    () => {
      // Pegado al scroll, sin el debounce de abajo: el efecto tiene que
      // seguir al dedo cuadro por cuadro. Lo que si va con debounce es la
      // resincronizacion del titulo/lista/puntitos, que solo importa
      // cuando el deslizamiento ya se detuvo.
      _pedirEfecto();
      clearTimeout(sincronizando);
      sincronizando = setTimeout(() => {
        if (items.length === 0) return;
        const idx = _indiceMasCercano();
        if (idx !== indiceActual) {
          indiceActual = idx;
          pintar();
        }
      }, 120);
    },
    { passive: true }
  );
  // Pausar el autoplay mientras el dedo está tocando — pedido explícito
  // del dueño, mismo criterio que ya usa el carrusel de PC con el mouse
  // (mouseenter/mouseleave) pero aquí con eventos táctiles.
  fotos.addEventListener("touchstart", detenerAutoplay, { passive: true });
  fotos.addEventListener("touchend", iniciarAutoplay, { passive: true });

  function render() {
    fotos.innerHTML = items.map(_cartaFotoSlideHTML).join("");
    lista.innerHTML = items.map(_cartaRenglonHTML).join("");
    dots.innerHTML = items
      .map((_, i) => `<button class="tk-cf-dot" aria-label="Ir al platillo ${i + 1}"></button>`)
      .join("");

    lista.querySelectorAll(".tk-carta-renglon").forEach((renglon) => {
      renglon.addEventListener("click", () => irA(Number(renglon.dataset.indice)));
    });
    dots.querySelectorAll(".tk-cf-dot").forEach((dot, i) => {
      dot.addEventListener("click", () => irA(i));
    });

    fotos.scrollLeft = 0;
    pintar();
    // Las <img> recien creadas nacen sin opacidad/transform inline, asi
    // que sin esto las 4 no centradas se verian a opacidad 1 hasta el
    // primer scroll.
    _actualizarEfecto();
    iniciarAutoplay();
  }

  function mostrarError() {
    // No se reusa htmlEstadoError() de catalogo.js: esa caja asume fondo
    // claro (rosa/rojo) y aquí el fondo es negro — mismo criterio que ya
    // documenta carrusel.js para su propio aviso de error.
    fotos.innerHTML = `
      <div class="tk-cf-error">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.25"/><line x1="12" y1="7.5" x2="12" y2="12.5"/><circle cx="12" cy="16.3" r="1" fill="currentColor" stroke="none"/></svg>
        <p>No hay conexión con el servidor. Revisa tu internet.</p>
      </div>
    `;
    titulo.textContent = "";
    lista.innerHTML = "";
    dots.innerHTML = "";
    detenerAutoplay();
  }

  async function cargar(forzar = false) {
    try {
      const catalogo = await obtenerCatalogo({ forzar });
      const grupos = agruparPorCategoria(catalogo);
      const nuevos = (grupos.Platillos || [])
        .filter((p) => p.image_url_recortada)
        .slice(0, _CARTA_LIMITE);

      if (nuevos.length === 0) {
        // Sin ningún Platillo con recorte todavía (el caso normal hoy —
        // ver CLAUDE.md/roadmap Fase 4.3, solo hay 1 platillo real y su
        // recorte se genera desde el panel, no desde aquí) se esconde
        // toda la sección: el móvil queda hero → footer directo, igual
        // que una categoría vacía se esconde en el preview del index.
        items = [];
        seccion.style.display = "none";
        detenerAutoplay();
        return;
      }

      seccion.style.display = "";
      const cambiaron = _firmaListaCarta(nuevos) !== _firmaListaCarta(items);
      items = nuevos;
      if (cambiaron) {
        if (indiceActual >= items.length) indiceActual = 0;
        render();
      }
    } catch (e) {
      console.error("[carta] error cargando el catálogo:", e);
      // Error de red SÍ deja la sección visible con su propio aviso (igual
      // que carrusel.js) — esconderla dejaría un hueco mudo entre el hero
      // y el footer sin ninguna pista de qué pasó.
      items = [];
      seccion.style.display = "";
      mostrarError();
    }
  }

  // Al rotar el telefono o cambiar el tamano de la ventana cambia
  // clientWidth, y la deriva se calcula a partir de el.
  window.addEventListener("resize", _pedirEfecto, { passive: true });

  await cargar();
  iniciarAutoRefresco(cargar);
}
