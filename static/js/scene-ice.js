/* Bounded low-poly hero globe, paused outside the viewport and on reduced effects. */
(async function(){
 const canvas=document.getElementById('heroIce');if(!canvas)return;
 const fallback=()=>document.documentElement.dataset.heroFallback='true';
 if(!window.WebGLRenderingContext||matchMedia('(prefers-reduced-motion: reduce)').matches||matchMedia('(max-width:700px)').matches){fallback();return;}
 try{
  const THREE=await import('/static/vendor/three-0.180.0.module.js');
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.setSize(Math.max(180,canvas.clientWidth*.7),Math.max(150,canvas.clientHeight*.7),false);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(34,Math.max(1,canvas.clientWidth/canvas.clientHeight),.1,30);camera.position.z=4;
  const accent=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#087f9b';
  const geometry=new THREE.IcosahedronGeometry(1,2),material=new THREE.MeshBasicMaterial({color:accent,wireframe:true,transparent:true,opacity:.4}),mesh=new THREE.Mesh(geometry,material);scene.add(mesh);
  const core=new THREE.Mesh(new THREE.IcosahedronGeometry(.73,1),new THREE.MeshBasicMaterial({color:accent,transparent:true,opacity:.15}));scene.add(core);
  let visible=false,raf=0,last=performance.now();const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)raf=requestAnimationFrame(draw);});io.observe(canvas);
  function draw(now){if(!visible||document.hidden||window.PolarEffects?.mode!=='full')return;const dt=Math.min((now-last)/1000,.04);last=now;mesh.rotation.y+=dt*.1;core.rotation.y-=dt*.045;renderer.render(scene,camera);raf=requestAnimationFrame(draw);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('beforeunload',()=>{cancelAnimationFrame(raf);io.disconnect();geometry.dispose();material.dispose();renderer.dispose();},{once:true});raf=requestAnimationFrame(draw);
 }catch(_){fallback();}
})();
