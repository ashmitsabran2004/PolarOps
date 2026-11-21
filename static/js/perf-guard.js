/* Shared animation budget, effect preference and visibility gate. */
(function () {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cores = navigator.hardwareConcurrency || 4;
  const memory = navigator.deviceMemory || 4;
  const smallScreen = matchMedia('(max-width: 700px)').matches;
  let weak = cores <= 2 || memory <= 2 || smallScreen || !window.WebGLRenderingContext;
  let fps = 60, frames = 0, start = performance.now();
  function probe(now) {
    frames++;
    if (now - start < 1000) requestAnimationFrame(probe);
    else { fps = frames * 1000 / (now - start); if (fps < 38) weak = true; apply(); }
  }
  requestAnimationFrame(probe);
  const root = document.documentElement;
  function stored() { try { return localStorage.getItem('polarops-effects'); } catch (_) { return null; } }
  function apply() {
    const pref = stored() || 'full';
    const mode = reduced || weak ? 'reduced' : pref;
    root.dataset.effects = mode;
    root.dataset.weakDevice = String(weak);
    document.querySelectorAll('[data-effects]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.effects === mode)));
    window.PolarEffects = { mode, weak, fps: Math.round(fps), allowed: () => mode === 'full' && !document.hidden };
    window.dispatchEvent(new CustomEvent('polar-effects-ready', { detail: window.PolarEffects }));
  }
  document.addEventListener('click', e => {
    const button = e.target.closest('[data-effects]'); if (!button) return;
    try { localStorage.setItem('polarops-effects', button.dataset.effects); } catch (_) {}
    apply();
  });
  document.addEventListener('visibilitychange', () => window.dispatchEvent(new Event('polar-visibility')));
  apply();
})();
