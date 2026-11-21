/* Count up numeric displays once they enter the viewport. */
(function(){
 const nodes=document.querySelectorAll('[data-count]'); if(!nodes.length)return;
 const run=node=>{const target=Number(node.dataset.count);if(!Number.isFinite(target))return;const start=performance.now(),duration=700;function frame(now){const p=Math.min(1,(now-start)/duration);node.textContent=String(Math.round(target*(1-Math.pow(1-p,3))));if(p<1)requestAnimationFrame(frame);}requestAnimationFrame(frame);};
 if('IntersectionObserver'in window){const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){run(e.target);io.unobserve(e.target);}}));nodes.forEach(n=>io.observe(n));}else nodes.forEach(run);
})();
