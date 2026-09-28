// ================================================================
// hero-animacion.js — la animación del taco del hero (index.html,
// sección 1), 9 sep 2026. Archivo APARTE de catalogo.js/carrusel.js/
// carta.js, mismo criterio que esos tres: no depende de ningún dato de
// Supabase (nada de obtenerCatalogo aquí), así que no tiene nada que
// ver con lo que sí comparten ellos.
//
// Qué hace: precarga los 132 frames de assets/frames/ (frame_0001.webp
// a frame_0132.webp — NO TOCAR esos archivos, ni su alfa, ni
// reprocesarlos: ver CLAUDE.md) y los va dibujando en un <canvas>
// según cuánto se ha scrolleado dentro de #tk-hero-enganche — el
// "scroll-jacking". Mismo patrón que .tk-carrusel-enganche de la
// sección 2 (un contenedor más alto que la pantalla + el hero fijo
// adentro por position:sticky, ver style.css), solo que aquí el scroll
// de más no solo "atrapa": también decide qué frame pintar. Nada de
// listeners de wheel capturando el scroll a mano — el secuestro es
// 100% el truco de sticky+altura extra que ya vive en el CSS.
//
// El <img id="tk-hero-frame-estatico"> del HTML es el respaldo REAL,
// no un simple placeholder: arranca visible siempre (se pinta solo con
// HTML, sin esperar a este script) y este archivo solo lo esconde —a
// favor del <canvas>— cuando de verdad hay algo mejor que mostrar. Eso
// cubre de un solo golpe los 3 casos en los que este archivo tiene que
// quedarse quieto:
//   1. Celular (≤640px, mismo corte que esMovil() en catalogo.js): NUNCA
//      se descargan los 132 frames en datos móviles. El <img> ya trajo
//      frame_0001 solo con el src del HTML, sin JS de por medio, y aquí
//      no hay nada más que hacer — se corta antes de precargar nada.
//   2. prefers-reduced-motion:reduce: frame fijo, sin animación y sin
//      scroll-jacking. El CSS ya apaga su mitad del truco (.tk-hero-
//      enganche no gana alto extra ahí, ver style.css); este archivo
//      apaga la otra mitad no precargando ni un solo frame de más.
//   3. Si algo sale mal a medio camino (todos los frames fallan, la
//      página se descarga antes de terminar de precargar, etc.) el
//      respaldo se queda puesto — nunca un <canvas> vacío.
// ================================================================

const _RUTA_FRAMES = "assets/frames/";
const _TOTAL_FRAMES = 132;
const _rutaFrame = (n) => `${_RUTA_FRAMES}frame_${String(n).padStart(4, "0")}.webp`;

// Mismo corte que esMovil() en catalogo.js (640px) — no se inventó un
// número nuevo solo para esta sección. Se comprueba UNA vez al cargar
// la página, no en cada resize: es una decisión de "qué clase de
// dispositivo es este", igual que el matchMedia guard de carrusel.js.
const _esMovil = () => window.matchMedia("(max-width: 640px)").matches;
const _prefiereMovimientoReducido = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function iniciarHeroAnimacion() {
  const envoltura = document.getElementById("tk-hero-enganche");
  const estatico = document.getElementById("tk-hero-frame-estatico");
  const canvas = document.getElementById("tk-hero-canvas");
  if (!envoltura || !estatico || !canvas) return;

  // Celular o "reducir movimiento": el <img> de respaldo ya es TODO lo
  // que hace falta mostrar (ver el porqué arriba) — no se precarga ni
  // un solo frame de más y el <canvas> no se toca para nada.
  if (_esMovil() || _prefiereMovimientoReducido()) return;

  const ctx = canvas.getContext("2d");
  const imagenes = new Array(_TOTAL_FRAMES + 1); // índice 1..132, el 0 no se usa
  const disponibles = new Array(_TOTAL_FRAMES + 1).fill(false);
  let frameActual = 0; // 0 = "todavía no se pintó nada"

  // Si el frame pedido falló al cargar, busca el disponible más cercano
  // (primero hacia atrás, luego hacia adelante) en vez de dejar el
  // <canvas> en blanco — así un solo frame roto nunca rompe la
  // secuencia completa.
  function indiceMasCercanoDisponible(n) {
    if (disponibles[n]) return n;
    for (let d = 1; d < _TOTAL_FRAMES; d++) {
      const atras = n - d;
      const adelante = n + d;
      if (atras >= 1 && disponibles[atras]) return atras;
      if (adelante <= _TOTAL_FRAMES && disponibles[adelante]) return adelante;
    }
    return null; // ni un solo frame cargó
  }

  function dibujar(n) {
    const real = indiceMasCercanoDisponible(n);
    if (real === null || real === frameActual) return;
    frameActual = real;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imagenes[real], 0, 0, canvas.width, canvas.height);
  }

  // Cuánto se ha avanzado dentro de #tk-hero-enganche: 0 = arriba del
  // todo, 1 = a punto de soltar el scroll normal. offsetHeight -
  // innerHeight es el alto EXTRA real que tiene la envoltura ahora
  // mismo — var(--hero-scroll-extra) de style.css, medido en vivo del
  // DOM en vez de traído aquí como un número duplicado, así que este
  // archivo y ese CSS no se pueden desincronizar. Si la envoltura no
  // tiene alto extra por algún motivo (p. ej. el @media de scroll-
  // jacking no llegó a aplicar), se congela en el último frame en vez
  // de dividir entre cero.
  function progreso() {
    const extra = envoltura.offsetHeight - window.innerHeight;
    if (extra <= 0) return 1;
    const avanzado = -envoltura.getBoundingClientRect().top;
    return Math.min(1, Math.max(0, avanzado / extra));
  }

  function actualizarFrame() {
    const n = 1 + Math.round(progreso() * (_TOTAL_FRAMES - 1));
    dibujar(n);
  }

  // rAF siempre, nunca trabajo pesado directo en el evento de scroll —
  // mismo patrón (bandera "ticking" + requestAnimationFrame) que
  // iniciarOcultarAlScroll() en catalogo.js.
  let ticking = false;
  function programarActualizacion() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      actualizarFrame();
      ticking = false;
    });
  }

  function activar() {
    // Si absolutamente ningún frame cargó, el respaldo estático se
    // queda puesto — cambiar a un <canvas> que nunca va a poder dibujar
    // nada sería peor que dejar la foto fija.
    if (!disponibles.some(Boolean)) return;
    canvas.hidden = false;
    estatico.hidden = true;
    actualizarFrame(); // por si el visitante ya scrolleó mientras cargaba
    window.addEventListener("scroll", programarActualizacion, { passive: true });
    window.addEventListener("resize", programarActualizacion, { passive: true });
  }

  let restantes = _TOTAL_FRAMES;
  function marcarResuelto() {
    restantes--;
    if (restantes === 0) activar();
  }

  for (let n = 1; n <= _TOTAL_FRAMES; n++) {
    const img = new Image();
    imagenes[n] = img;
    img.onload = () => {
      if (img.naturalWidth === 0) {
        console.error("hero-animacion.js: frame vacío", img.src);
      } else {
        disponibles[n] = true;
      }
      marcarResuelto();
    };
    img.onerror = () => {
      console.error("hero-animacion.js: no se pudo cargar", img.src);
      marcarResuelto();
    };
    img.src = _rutaFrame(n);
  }
}
