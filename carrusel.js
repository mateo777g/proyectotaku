// ================================================================
// carrusel.js — carrusel 3D "coverflow" del index.html, SOLO
// escritorio (≥1024px). En móvil el index se queda con las 3
// secciones de categoría de siempre (Platillos/Bebidas/Postres) sin
// ningún cambio — ver iniciarIndex() en catalogo.js, intacta.
//
// Archivo APARTE de catalogo.js a propósito: catalogo.js es
// "compartido por las 4 páginas" (CLAUDE.md) — este carrusel solo lo
// usa index.html, así que su lógica (bastante) no tiene por qué vivir
// ahí. Sí depende de varios globals que expone catalogo.js
// (obtenerCatalogo, agruparPorCategoria, CATEGORIAS, escapeHtml,
// iniciarAutoRefresco) — por eso en index.html
// <script src="catalogo.js"> va ANTES que <script src="carrusel.js">.
//
// Pedido explícito del dueño (27 ago 2026): puerto lo más fiel
// posible de un componente de referencia (React, "3-d-coverflow-
// carousel") — mismos colores, tamaños, animaciones y matemática de
// posicionamiento 3D, sin adaptarlos a la paleta del resto del sitio
// (ver CLAUDE.md → Design rules → Public menu site). Lo único que SÍ
// cambia contra el original: los datos. Nada de fotos de stock de
// Unsplash ni texto en inglés hardcodeado — las tarjetas se arman con
// platillos reales de Supabase, igual que el resto del sitio.
// ================================================================

// ⚠️ Debe ser EXACTAMENTE el mismo corte que el "@media (min-width:
// 1024px)" en style.css (sección "Carrusel 3D del menú") Y que
// _CARTA_BREAKPOINT_DESKTOP en carta.js (Fase 4.3, el equivalente de
// celular de esta misma sección) — son 3 lugares, no 2. Si cambias uno,
// cambia los otros dos — ver el comentario grande de ese bloque en
// style.css para el porqué de los 1024px y del riesgo de dejarlos
// desincronizados.
const _CARRUSEL_BREAKPOINT = "(min-width: 1024px)";

const _CARRUSEL_AUTOPLAY_MS = 5000; // mismo valor que autoplayDelay del original

// A dónde manda el botón de cada tarjeta según la categoría del
// platillo que muestra — mismas páginas que ya enlazan las 3
// secciones de categoría del index y el footer, nada nuevo.
const _CTA_POR_CATEGORIA = {
  Platillos: { texto: "Ver platillos", url: "menu-platillos.html" },
  Bebidas: { texto: "Ver bebidas", url: "menu-bebidas.html" },
  Postres: { texto: "Ver postres", url: "menu-postres.html" },
};

/** Tope POR CATEGORÍA del carrusel de escritorio: 2 platillos, 2 bebidas
 * y 2 postres, o sea 6 tarjetas como máximo.
 *
 * ⚠️ Esto CAMBIÓ el 3 sep 2026 y es lo contrario de lo que decía antes
 * este archivo. La versión original no tenía tope ("usa TODO lo visible
 * de verdad"), con el argumento de que capear tiraría platillos reales
 * nada más porque Bebidas/Postres tienen menos filas. El dueño lo revirtió
 * de forma explícita al ver el carrusel con 9 tarjetas: el carrusel de PC
 * es un ESCAPARATE, no el catálogo — para ver todo están las páginas de
 * categoría, a las que lleva el botón de cada tarjeta. Si algún día
 * vuelve a discutirse, la decisión vigente es esta, no el comentario
 * viejo. */
const _CARRUSEL_MAX_POR_CATEGORIA = 2;

/** 1 platillo, 1 bebida, 1 postre, y se repite el ciclo — tal como lo
 * pidió el dueño. Si una categoría se acaba antes que las demás (o llega
 * a su tope), simplemente se salta y se sigue con las que aún tengan, así
 * que una categoría con 1 sola fila no deja hueco ni desalinea el ciclo.
 *
 * El tope se aplica aquí y no en la consulta a propósito: obtenerCatalogo()
 * es la MISMA consulta compartida por la carta de celular, las 3 páginas de
 * categoría y su buscador (ver catalogo.js) — recortarla ahí les quitaría
 * filas a todos. Aquí solo se recorta lo que este carrusel pinta. */
function _intercalarPorCategoria(grupos) {
  const resultado = [];
  const indices = { Platillos: 0, Bebidas: 0, Postres: 0 };
  let quedan = true;
  while (quedan) {
    quedan = false;
    for (const categoria of CATEGORIAS) {
      const lista = grupos[categoria] || [];
      const i = indices[categoria];
      if (i < lista.length && i < _CARRUSEL_MAX_POR_CATEGORIA) {
        resultado.push(lista[i]);
        indices[categoria] = i + 1;
        quedan = true;
      }
    }
  }
  return resultado;
}

// Firma barata para detectar si el catálogo realmente cambió entre un
// refresco y el anterior (iniciarAutoRefresco dispara cada 30s). Sin
// esto, cada tick reconstruiría las tarjetas desde cero aunque nada
// haya cambiado — reinicia el autoplay y puede verse como un
// parpadeo. Con esto, un tick sin cambios reales no toca el DOM.
function _firmaLista(lista) {
  return lista.map((p) => p.id).join(",");
}

function _tarjetaCarruselHTML(platillo, idx) {
  const nombre = escapeHtml(platillo.nombre || "");
  const descripcion = escapeHtml(platillo.descripcion || "");
  const categoria = escapeHtml(platillo.categoria || "");
  // Mismo fallback que tarjetaPlatilloHTML() en catalogo.js — hoy es
  // el caso normal (casi ningún platillo tiene foto todavía, ver
  // CLAUDE.md Fase 4), no una rareza.
  const imagen = escapeHtml(platillo.image_url || "assets/sin-foto.png");
  const cta = _CTA_POR_CATEGORIA[platillo.categoria] || { texto: "Ver menú", url: "index.html" };

  return `
    <div class="tk-cf-tarjeta" data-indice="${idx}">
      <img class="tk-cf-foto" src="${imagen}" alt="${nombre}" loading="lazy"
           onerror="this.onerror=null; this.src='assets/sin-foto.png';">
      <div class="tk-cf-vineta"></div>
      <div class="tk-cf-contenido">
        <div class="tk-cf-tag">${categoria ? "#" + categoria : ""}</div>
        <div class="tk-cf-cuerpo">
          <h2 class="tk-cf-titulo">${nombre}</h2>
          <div class="tk-cf-divisor"></div>
          ${descripcion ? `<p class="tk-cf-desc">${descripcion}</p>` : ""}
          <a class="tk-cf-cta" href="${cta.url}">
            <span>${cta.texto}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          </a>
        </div>
      </div>
    </div>
  `;
}

async function iniciarCarrusel() {
  // El carrusel es EXCLUSIVO de escritorio. Ni siquiera se arma el DOM
  // ni se piden las fotos aquí si el viewport no es de escritorio —
  // evita bajar de más en una conexión de celular/tablet algo que de
  // cualquier forma va a quedar en display:none (ver style.css).
  if (!window.matchMedia(_CARRUSEL_BREAKPOINT).matches) return;

  const seccion = document.getElementById("carrusel-menu");
  const fondo = document.getElementById("carrusel-fondo");
  const escenario = document.getElementById("carrusel-escenario");
  const dots = document.getElementById("carrusel-dots");
  const btnPrev = document.getElementById("carrusel-prev");
  const btnNext = document.getElementById("carrusel-next");
  if (!seccion || !fondo || !escenario || !dots || !btnPrev || !btnNext) return;

  // En escritorio, los 3 links del navbar ("Platillos"/"Bebidas"/
  // "Postres") ya no tienen a dónde apuntar — esas secciones están
  // escondidas (ver style.css). Los mandamos todos al carrusel, que es
  // ahora "el menú" en esta versión de la página. OJO: solo el navbar
  // de arriba (.tk-nav-links) — el sidebar móvil (.tk-sidebar-links) NO
  // se toca aquí, ya apunta a las páginas reales (menu-platillos.html
  // etc, mismo destino que el footer y el CTA de la carta) directo
  // desde el HTML, sin necesidad de reescritura por JS. ⚠️ Esto se
  // rompió un rato en la Fase 4.3 con este mismo comentario diciendo lo
  // contrario ("las 3 secciones reales siguen ahí" en móvil) — ya no,
  // desde esa misma fase #platillos/#bebidas/#postres se ocultan en
  // TODOS los anchos (ver style.css), así que un link a "#platillos" no
  // lleva a ningún lado ni en escritorio ni en celular. Corregido el
  // 4 sep 2026 (reportado por el dueño: "la navbar dejó de funcionar").
  document.querySelectorAll(".tk-nav-links .tk-nav-link").forEach((enlace) => {
    enlace.setAttribute("href", "#carrusel-menu");
  });

  let items = [];
  let indiceActual = 0;
  let temporizador = null;

  function detenerAutoplay() {
    if (temporizador) {
      clearInterval(temporizador);
      temporizador = null;
    }
  }
  function iniciarAutoplay() {
    detenerAutoplay();
    if (items.length <= 1) return; // igual que el original: total <= 1 no autoavanza
    temporizador = setInterval(() => irA(indiceActual + 1), _CARRUSEL_AUTOPLAY_MS);
  }

  function irA(idx) {
    indiceActual = ((idx % items.length) + items.length) % items.length;
    pintar();
  }
  function siguiente() { irA(indiceActual + 1); }
  function anterior() { irA(indiceActual - 1); }

  // Coloca cada tarjeta según su distancia (offset) a la tarjeta
  // activa — calcado literal de la matemática del componente original
  // (mismos translateX/scale/rotateY/opacity/filter por offset).
  function pintar() {
    const total = items.length;
    fondo.style.backgroundImage = `url("${items[indiceActual].image_url || "assets/sin-foto.png"}")`;

    escenario.querySelectorAll(".tk-cf-tarjeta").forEach((tarjeta) => {
      const idx = Number(tarjeta.dataset.indice);
      const offset = ((idx - indiceActual) % total + total) % total;
      tarjeta.classList.toggle("tk-cf-centro", offset === 0);

      if (offset === 0) {
        tarjeta.style.transform = "translateX(0px) scale(1) rotateY(0deg)";
        tarjeta.style.opacity = "1";
        tarjeta.style.zIndex = "30";
        tarjeta.style.filter = "brightness(1)";
      } else if (offset === 1) {
        tarjeta.style.transform = "translateX(285px) scale(0.84) rotateY(-24deg)";
        tarjeta.style.opacity = "0.65";
        tarjeta.style.zIndex = "20";
        tarjeta.style.filter = "brightness(0.75)";
      } else if (offset === 2) {
        tarjeta.style.transform = "translateX(510px) scale(0.68) rotateY(-38deg)";
        tarjeta.style.opacity = "0.38";
        tarjeta.style.zIndex = "10";
        tarjeta.style.filter = "brightness(0.55) blur(1px)";
      } else if (offset === total - 1) {
        tarjeta.style.transform = "translateX(-285px) scale(0.84) rotateY(24deg)";
        tarjeta.style.opacity = "0.65";
        tarjeta.style.zIndex = "20";
        tarjeta.style.filter = "brightness(0.75)";
      } else if (offset === total - 2) {
        tarjeta.style.transform = "translateX(-510px) scale(0.68) rotateY(38deg)";
        tarjeta.style.opacity = "0.38";
        tarjeta.style.zIndex = "10";
        tarjeta.style.filter = "brightness(0.55) blur(1px)";
      } else {
        tarjeta.style.transform = "translateX(0px) scale(0.4) rotateY(0deg)";
        tarjeta.style.opacity = "0";
        tarjeta.style.zIndex = "0";
        tarjeta.style.filter = "brightness(0.4) blur(2px)";
      }
    });

    dots.querySelectorAll(".tk-cf-dot").forEach((dot, i) => {
      dot.classList.toggle("tk-cf-dot-activo", i === indiceActual);
    });
  }

  function render() {
    // Se recuperan de un posible estado de error de un refresco previo.
    btnPrev.style.display = "";
    btnNext.style.display = "";

    escenario.innerHTML = items.map((p, i) => _tarjetaCarruselHTML(p, i)).join("");
    dots.innerHTML = items
      .map((_, i) => `<button class="tk-cf-dot" aria-label="Ir a la tarjeta ${i + 1}"></button>`)
      .join("");

    dots.querySelectorAll(".tk-cf-dot").forEach((dot, i) => {
      dot.addEventListener("click", () => irA(i));
    });
    escenario.querySelectorAll(".tk-cf-tarjeta").forEach((tarjeta) => {
      tarjeta.addEventListener("click", () => {
        const idx = Number(tarjeta.dataset.indice);
        if (idx !== indiceActual) irA(idx);
      });
    });

    pintar();
    iniciarAutoplay();
  }

  function mostrarError() {
    // No se reusa htmlEstadoError() de catalogo.js: esa caja asume
    // fondo claro (rosa/rojo) y aquí el fondo es negro — se ve un
    // parche fuera de lugar. Mismo mensaje, tratamiento propio.
    escenario.innerHTML = `
      <div class="tk-cf-error">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.25"/><line x1="12" y1="7.5" x2="12" y2="12.5"/><circle cx="12" cy="16.3" r="1" fill="currentColor" stroke="none"/></svg>
        <p>No hay conexión con el servidor. Revisa tu internet.</p>
      </div>
    `;
    dots.innerHTML = "";
    btnPrev.style.display = "none";
    btnNext.style.display = "none";
    detenerAutoplay();
  }

  async function cargar(forzar = false) {
    try {
      const lista = await obtenerCatalogo({ forzar });
      const grupos = agruparPorCategoria(lista);
      const nuevos = _intercalarPorCategoria(grupos);

      if (nuevos.length === 0) {
        // Catálogo real pero sin nada visible en ninguna categoría —
        // no hay nada que enseñar, se esconde toda la sección (igual
        // que una categoría vacía se esconde en el preview del index).
        items = nuevos;
        seccion.style.display = "none";
        detenerAutoplay();
        return;
      }

      seccion.style.display = "";
      const cambiaron = _firmaLista(nuevos) !== _firmaLista(items);
      items = nuevos;
      if (cambiaron) {
        if (indiceActual >= items.length) indiceActual = 0;
        render();
      }
    } catch (e) {
      console.error("[carrusel] error cargando el catálogo:", e);
      // A diferencia del catálogo vacío, un error SÍ deja la sección
      // visible (con su propio aviso) — si la escondiéramos, un
      // usuario de escritorio se quedaría viendo un hueco mudo entre
      // el hero y el footer sin ninguna pista de qué pasó.
      items = [];
      seccion.style.display = "";
      mostrarError();
    }
  }

  btnPrev.addEventListener("click", anterior);
  btnNext.addEventListener("click", siguiente);
  seccion.addEventListener("mouseenter", detenerAutoplay);
  seccion.addEventListener("mouseleave", iniciarAutoplay);

  document.addEventListener("keydown", (e) => {
    if (seccion.style.display === "none") return;
    const objetivo = e.target;
    const escribiendo =
      objetivo && (objetivo.tagName === "INPUT" || objetivo.tagName === "TEXTAREA" || objetivo.isContentEditable);
    if (escribiendo) return;
    if (e.key === "ArrowLeft") anterior();
    if (e.key === "ArrowRight") siguiente();
  });

  let inicioToqueX = 0;
  seccion.addEventListener("touchstart", (e) => { inicioToqueX = e.touches[0].clientX; }, { passive: true });
  seccion.addEventListener("touchend", (e) => {
    const diferencia = e.changedTouches[0].clientX - inicioToqueX;
    if (Math.abs(diferencia) > 45) {
      if (diferencia < 0) siguiente();
      else anterior();
    }
  });

  await cargar();
  iniciarAutoRefresco(cargar);
}
