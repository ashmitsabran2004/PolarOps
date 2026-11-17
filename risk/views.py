import json
from django.contrib import messages
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404,redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView
from core.permissions import has_role
from core.crud import MANAGERS,RiskAssessmentForm
from expeditions.models import Expedition
from risk.models import WeatherReading
from risk.services import fetch_open_meteo,latest_weather

class RiskEntryView(FormView):
    template_name='risk/assessment_form.html'; form_class=RiskAssessmentForm
    def dispatch(self,request,*args,**kwargs):
        if not has_role(request.user,*MANAGERS): raise PermissionDenied
        self.expedition=get_object_or_404(Expedition,pk=kwargs['expedition_id'])
        return super().dispatch(request,*args,**kwargs)
    def get_initial(self):
        initial=super().get_initial(); initial['expedition']=self.expedition.pk
        cached=latest_weather(self.expedition)
        if cached:
            initial.update({'temperature':float(cached.temperature),'wind_kph':cached.wind_kph,'visibility_km':float(cached.visibility_km),'daylight_hours':float(cached.daylight_hours)})
        return initial
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c['expedition']=self.expedition; c['latest_weather']=latest_weather(self.expedition); return c
    def form_valid(self,form):
        result=form.save(); self.expedition.risk_score=result.score; self.expedition.save(update_fields=['risk_score'])
        messages.success(self.request,f'Risk assessment recorded: {result.verdict} · {result.score}/100.')
        return redirect('expedition_detail',pk=self.expedition.pk)

class WeatherFetchView(View):
    http_method_names=['post']
    def post(self,request,expedition_id):
        if not has_role(request.user,*MANAGERS): raise PermissionDenied
        expedition=get_object_or_404(Expedition,pk=expedition_id)
        try:
            reading=fetch_open_meteo(expedition)
            cached=WeatherReading.objects.create(expedition=expedition,temperature=reading['temperature'],wind_kph=reading['wind_kph'],visibility_km=reading['visibility_km'],daylight_hours=reading['daylight_hours'],payload=reading['payload'])
            return JsonResponse({'status':'success','notice':f'Live Open-Meteo reading · {cached.fetched_at:%Y-%m-%d %H:%M} UTC','reading':{'temperature':float(cached.temperature),'wind_kph':cached.wind_kph,'visibility_km':float(cached.visibility_km),'daylight_hours':float(cached.daylight_hours)}})
        except ValidationError:
            cached=latest_weather(expedition)
            if cached:
                return JsonResponse({'status':'cached','notice':f'Weather provider offline. Using last successful reading from {cached.fetched_at:%Y-%m-%d %H:%M} UTC. Review it before submitting.','reading':{'temperature':float(cached.temperature),'wind_kph':cached.wind_kph,'visibility_km':float(cached.visibility_km),'daylight_hours':float(cached.daylight_hours)}})
            return JsonResponse({'status':'manual','notice':'Weather provider unavailable and no cached reading exists. Enter conditions manually.','reading':None},status=503)
