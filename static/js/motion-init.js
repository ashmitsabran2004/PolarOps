/* Shared page entrance and restrained micro-interactions. */
(function () {
  const durations = { fast: .18, standard: .42, reveal: .68 };
  window.PolarMotion = { durations, spring: { stiffness: 150, damping: 22 }, stagger: .055 };
  function init() {
    const motion = window.Motion;
    const reduced = document.documentElement.dataset.effects !== 'full';
    document.body.classList.add('motion-ready');
    const targets = [...document.querySelectorAll('.sidebar,.topbar,.hero,.stat,.panel,.exp-card,.sos-alert,.page-heading,.data-table-wrap,.login-card')];
    if (motion && motion.animate && !reduced) {
      targets.forEach((el, i) => {
        el.style.opacity = '0';
        motion.animate(el, { opacity: [0, 1], y: [12, 0] }, { duration: durations.standard, delay: Math.min(i * .035, .38), easing: [.22, .8, .2, 1] });
      });
      if (motion.inView) motion.inView('.data-table tbody tr, .asset-risk, .timeline', element => { motion.animate(element, { opacity: [0, 1], y: [7, 0] }, { duration: durations.fast }); });
    } else targets.forEach(el => el.classList.add('motion-visible'));
    document.querySelectorAll('.toast').forEach(t => { const close=t.querySelector('button'); if(close)close.addEventListener('click',()=>t.remove()); setTimeout(()=>t.classList.add('toast-dismiss'),6500); });
    document.querySelectorAll('form[method="post"]').forEach(f=>f.addEventListener('submit',e=>{if(e.defaultPrevented||!f.reportValidity())return;const b=e.submitter||f.querySelector('button[type="submit"],button:not([type])');if(b&&!b.disabled){b.dataset.oldLabel=b.textContent.trim();b.disabled=true;b.textContent=b.dataset.loadingLabel||'WORKING…';b.classList.add('is-loading');}}));
    const password=document.querySelector('.password-toggle'); if(password)password.addEventListener('click',()=>{const input=document.getElementById('id_password');if(!input)return;input.type=input.type==='password'?'text':'password';password.textContent=input.type==='password'?'SHOW':'HIDE';password.setAttribute('aria-label',input.type==='password'?'Show passphrase':'Hide passphrase');});
    const utc=document.getElementById('loginUtc'); if(utc){const tick=()=>utc.textContent=new Date().toISOString().slice(11,19)+' UTC';tick();setInterval(tick,1000);}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
