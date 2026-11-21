/* Current weather lookup and assessment-form fill. */
(function(){
 const button=document.getElementById('fetchWeather'),notice=document.getElementById('weatherNotice');if(!button||!notice)return;
 button.addEventListener('click',async()=>{button.disabled=true;button.textContent='FETCHING…';notice.textContent='Contacting Open-Meteo…';try{const response=await fetch(button.dataset.url,{method:'POST',headers:{'X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value,'Accept':'application/json'}});const data=await response.json();notice.textContent=data.notice;if(data.reading)for(const [key,value] of Object.entries(data.reading)){const input=document.getElementById('id_'+key);if(input)input.value=value;}}catch(_){notice.textContent='Could not reach weather service. Enter conditions manually.';}finally{button.disabled=false;button.textContent='FETCH WEATHER';}});
})();
