/* Small low-poly scene for the sign-in view; theme colors come from CSS variables. */
(async function(){
 const canvas=document.getElementById('loginGlobe'); if(!canvas)return;
 const effects=()=>window.PolarEffects;
 const prefersReduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const fallback=()=>document.documentElement.dataset.sceneFallback='true';
 if(!window.WebGLRenderingContext||matchMedia('(max-width:700px)').matches||prefersReduced){fallback();return;}
 try{
  const THREE=await import('/static/vendor/three-0.180.0.module.js');
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));renderer.setSize(Math.max(320,canvas.clientWidth*.68),Math.max(240,canvas.clientHeight*.68),false);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,Math.max(1,canvas.clientWidth/canvas.clientHeight),.1,50);camera.position.z=5;
  const color=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#087f9b';
  const geometry=new THREE.IcosahedronGeometry(1.42,2),material=new THREE.MeshBasicMaterial({color,wireframe:true,transparent:true,opacity:.4});const globe=new THREE.Mesh(geometry,material);scene.add(globe);
  const points=[];for(let i=0;i<260;i++){const a=Math.random()*Math.PI*2,z=Math.random()*2-1,r=2.05+Math.random()*.65,q=Math.sqrt(1-z*z);points.push(r*q*Math.cos(a),r*z,r*q*Math.sin(a));}
  const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const pm=new THREE.PointsMaterial({color,size:.018,transparent:true,opacity:.72});scene.add(new THREE.Points(pg,pm));
  const markers=[[-77.84,166.68],[78.92,11.92],[28.00,86.85]];markers.forEach(([lat,lon])=>{const phi=(90-lat)*Math.PI/180,theta=(lon+180)*Math.PI/180;const dot=new THREE.Mesh(new THREE.SphereGeometry(.045,6,4),new THREE.MeshBasicMaterial({color:0xf1b955}));dot.position.set(-1.45*Math.sin(phi)*Math.cos(theta),1.45*Math.cos(phi),1.45*Math.sin(phi)*Math.sin(theta));globe.add(dot);});
  let visible=true,last=performance.now(),raf=0;const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)raf=requestAnimationFrame(draw);});io.observe(canvas);
  let scrolling=false,timer;window.addEventListener('scroll',()=>{scrolling=true;clearTimeout(timer);timer=setTimeout(()=>scrolling=false,180);},{passive:true});
  function draw(now){if(!visible||document.hidden||scrolling||!(effects()?.allowed?.()??true))return;const dt=Math.min((now-last)/1000,.04);last=now;globe.rotation.y+=dt*.08;globe.rotation.x=Math.sin(now*.00016)*.08;renderer.render(scene,camera);raf=requestAnimationFrame(draw);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('polar-visibility',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('beforeunload',()=>{cancelAnimationFrame(raf);io.disconnect();geometry.dispose();material.dispose();pg.dispose();pm.dispose();renderer.dispose();},{once:true});
  raf=requestAnimationFrame(draw);
 }catch(_){fallback();}
})();
