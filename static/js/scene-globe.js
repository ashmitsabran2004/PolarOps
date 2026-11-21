/* Compact low-poly login globe: <3000 vertices, no lighting or post-processing. */
(async function(){
 const canvas=document.getElementById('loginGlobe');if(!canvas)return;
 const root=document.documentElement,themes=['antarctica','arctic','himalaya','subantarctic','greenland'];let themeIndex=0;
 const region=document.getElementById('loginRegion');setInterval(()=>{themeIndex=(themeIndex+1)%themes.length;root.dataset.theme=themes[themeIndex];if(region)region.textContent=themes[themeIndex].toUpperCase()+' / EXPEDITION NETWORK';},9000);
 const fallback=()=>root.dataset.sceneFallback='true';
 if(!window.WebGLRenderingContext||matchMedia('(max-width:700px)').matches||matchMedia('(prefers-reduced-motion: reduce)').matches){fallback();return;}
 try{
  const THREE=await import('/static/vendor/three-0.180.0.module.js');
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.1,50);camera.position.z=5;
  const resize=()=>{const w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);renderer.setSize(Math.round(w*.68),Math.round(h*.68),false);camera.aspect=w/h;camera.updateProjectionMatrix();};resize();const ro=new ResizeObserver(resize);ro.observe(canvas);
  const color=getComputedStyle(root).getPropertyValue('--accent').trim()||'#087f9b';
  const geometry=new THREE.IcosahedronGeometry(1.42,2),material=new THREE.MeshBasicMaterial({color,wireframe:true,transparent:true,opacity:.42}),globe=new THREE.Mesh(geometry,material);scene.add(globe);
  const points=[];for(let i=0;i<260;i++){const a=Math.random()*Math.PI*2,z=Math.random()*2-1,r=2.05+Math.random()*.65,q=Math.sqrt(1-z*z);points.push(r*q*Math.cos(a),r*z,r*q*Math.sin(a));}
  const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const pm=new THREE.PointsMaterial({color,size:.018,transparent:true,opacity:.72});scene.add(new THREE.Points(pg,pm));
  const markers=[[-77.84,166.68],[78.92,11.92],[28.00,86.85]];markers.forEach(([lat,lon])=>{const phi=(90-lat)*Math.PI/180,theta=(lon+180)*Math.PI/180,dot=new THREE.Mesh(new THREE.SphereGeometry(.045,6,4),new THREE.MeshBasicMaterial({color:0xf1b955}));dot.position.set(-1.45*Math.sin(phi)*Math.cos(theta),1.45*Math.cos(phi),1.45*Math.sin(phi)*Math.sin(theta));globe.add(dot);});
  const arcMaterial=new THREE.LineBasicMaterial({color:0xe8f5ed,transparent:true,opacity:.32});[[0,1],[1,2]].forEach(pair=>{const a=globe.children[pair[0]].position,b=globe.children[pair[1]].position,mid=a.clone().add(b).multiplyScalar(.5).normalize().multiplyScalar(1.72),curve=new THREE.QuadraticBezierCurve3(a,mid,b),line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(24)),arcMaterial);globe.add(line);});
  let visible=false,last=performance.now(),raf=0,scrolling=false,timer;const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)raf=requestAnimationFrame(draw);});io.observe(canvas);
  window.addEventListener('scroll',()=>{scrolling=true;clearTimeout(timer);timer=setTimeout(()=>scrolling=false,180);},{passive:true});
  window.addEventListener('pointermove',e=>{if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;camera.position.x=(e.clientX/innerWidth-.5)*.22;camera.position.y=-(e.clientY/innerHeight-.5)*.14;camera.lookAt(0,0,0);},{passive:true});
  function draw(now){if(!visible||document.hidden||scrolling)return;const dt=Math.min((now-last)/1000,.04);last=now;const prefs=window.PolarEffects;if(!prefs||prefs.allowed()){globe.rotation.y+=dt*.08;globe.rotation.x=Math.sin(now*.00016)*.08;}material.color.set(getComputedStyle(root).getPropertyValue('--accent').trim()||'#087f9b');renderer.render(scene,camera);raf=requestAnimationFrame(draw);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});window.addEventListener('polar-visibility',()=>{if(!document.hidden&&visible)raf=requestAnimationFrame(draw);});
  const form=document.querySelector('[data-login-error]');if(form)form.classList.add('login-error');
  window.addEventListener('beforeunload',()=>{cancelAnimationFrame(raf);io.disconnect();ro.disconnect();geometry.dispose();material.dispose();pg.dispose();pm.dispose();arcMaterial.dispose();globe.traverse(o=>{if(o.geometry&&o.geometry!==geometry)o.geometry.dispose();});renderer.dispose();},{once:true});raf=requestAnimationFrame(draw);
 }catch(_){fallback();}
})();
