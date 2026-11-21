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
      targets.forEach((el, i) => { el.style.opacity = '0'; motion.animate(el, { opacity: [0, 1], y: [12, 0] }, { type: motion.spring, stiffness: 150, damping: 22, delay: Math.min(i * .035, .38) }); });
      const rows=document.querySelectorAll('.stats-grid .stat');if(rows.length)motion.animate(rows,{opacity:[0,1],y:[10,0]},{type:motion.spring,stiffness:170,damping:24,delay:motion.stagger(.07,{startDelay:.08})});
      if (motion.inView) motion.inView('.data-table tbody tr, .asset-risk, .timeline', element => { motion.animate(element, { opacity: [0, 1], y: [7, 0] }, { duration: durations.fast }); });
      if (motion.scroll) motion.scroll(progress => document.documentElement.style.setProperty('--scroll-progress', progress));
    } else targets.forEach(el => el.classList.add('motion-visible'));
    document.querySelectorAll('.toast').forEach(t => { const close=t.querySelector('button'); if(close)close.addEventListener('click',()=>t.remove()); setTimeout(()=>t.classList.add('toast-dismiss'),6500); });
    document.querySelectorAll('form[method="post"]').forEach(f=>f.addEventListener('submit',e=>{if(e.defaultPrevented||!f.reportValidity())return;const b=e.submitter||f.querySelector('button[type="submit"],button:not([type])');if(b&&!b.disabled){b.dataset.oldLabel=b.textContent.trim();b.disabled=true;b.textContent=b.dataset.loadingLabel||'WORKING…';b.classList.add('is-loading');}}));
    document.querySelectorAll('[data-mobile-menu]').forEach(b=>b.addEventListener('click',()=>document.body.classList.toggle('nav-open')));
    document.querySelectorAll('[data-submit-on-change]').forEach(el=>el.addEventListener('change',()=>el.form?.requestSubmit()));
    document.querySelectorAll('[data-field-mode-toggle]').forEach(el=>el.addEventListener('change',()=>{document.body.classList.toggle('field-mode',el.checked);localStorage.setItem('polarops-field-mode',el.checked?'on':'off');}));
    document.querySelectorAll('[data-print-page]').forEach(b=>b.addEventListener('click',()=>window.print()));
    document.querySelectorAll('[data-confirm-submit]').forEach(form=>form.addEventListener('submit',e=>{if(!confirm(form.dataset.confirmSubmit))e.preventDefault();}));
    const fieldMode=localStorage.getItem('polarops-field-mode')==='on';document.body.classList.toggle('field-mode',fieldMode);const fieldToggle=document.getElementById('field-mode-toggle');if(fieldToggle)fieldToggle.checked=fieldMode;
    const holdButton=document.querySelector('[data-hold-sos]');if(holdButton){let timer,armed=false;holdButton.addEventListener('pointerdown',()=>{armed=false;holdButton.classList.add('is-holding');timer=setTimeout(()=>{armed=true;holdButton.classList.remove('is-holding');holdButton.classList.add('is-armed');holdButton.textContent='RELEASE TO TRANSMIT';},900);});['pointerup','pointerleave','pointercancel'].forEach(type=>holdButton.addEventListener(type,()=>{clearTimeout(timer);holdButton.classList.remove('is-holding');if(!armed)holdButton.textContent='HOLD TO TRANSMIT SOS';}));holdButton.addEventListener('click',e=>{if(e.detail===0){if(!confirm('Transmit an emergency SOS to mission control now?'))e.preventDefault();return;}if(!armed)e.preventDefault();});}
    const password=document.querySelector('.password-toggle'); if(password)password.addEventListener('click',()=>{const input=document.getElementById('id_password');if(!input)return;input.type=input.type==='password'?'text':'password';password.textContent=input.type==='password'?'SHOW':'HIDE';password.setAttribute('aria-label',input.type==='password'?'Show passphrase':'Hide passphrase');});
    const utc=document.getElementById('loginUtc'); if(utc){const tick=()=>utc.textContent=new Date().toISOString().slice(11,19)+' UTC';tick();setInterval(tick,1000);}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
