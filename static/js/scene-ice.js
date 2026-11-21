/* Bounded low-poly hero globe, paused outside the viewport and while scrolling. */
(async function(){
 const canvas=document.getElementById('heroIce');if(!canvas)return;
 const fallback=()=>document.documentElement.dataset.heroFallback='true';
 if(!window.WebGLRenderingContext||matchMedia('(prefers-reduced-motion: reduce)').matches||matchMedia('(max-width:700px)').matches){fallback();return;}
 try{
  const THREE=await import('/static/vendor/three-0.180.0.module.js');
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(34,1,.1,30);camera.position.z=4;
  const resize=()=>{const w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);renderer.setSize(Math.max(180,Math.round(w*.7)),Math.max(150,Math.round(h*.7)),false);camera.aspect=w/h;camera.updateProjectionMatrix();};resize();const ro=new ResizeObserver(resize);ro.observe(canvas);
  const accent=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#087f9b';
  const geometry=new THREE.IcosahedronGeometry(1,2),material=new THREE.MeshBasicMaterial({color:accent,wireframe:true,transparent:true,opacity:.4}),mesh=new THREE.Mesh(geometry,material);scene.add(mesh);
  const coreGeometry=new THREE.IcosahedronGeometry(.73,1),coreMaterial=new THREE.MeshBasicMaterial({color:accent,transparent:true,opacity:.15}),core=new THREE.Mesh(coreGeometry,coreMaterial);scene.add(core);
  let visible=false,raf=0,last=performance.now(),scrolling=false,timer;const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)raf=requestAnimationFrame(draw);});io.observe(canvas);
  window.addEventListener('scroll',()=>{scrolling=true;clearTimeout(timer);timer=setTimeout(()=>scrolling=false,180);},{passive:true});
  function draw(now){if(!visible||document.hidden||scrolling||window.PolarEffects?.mode!=='full')return;const dt=Math.min((now-last)/1000,.04);last=now;mesh.rotation.y+=dt*.1;core.rotation.y-=dt*.045;renderer.render(scene,camera);raf=requestAnimationFrame(draw);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('polar-visibility',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('beforeunload',()=>{cancelAnimationFrame(raf);io.disconnect();ro.disconnect();geometry.dispose();material.dispose();coreGeometry.dispose();coreMaterial.dispose();renderer.dispose();},{once:true});raf=requestAnimationFrame(draw);
 }catch(_){fallback();}
})();
