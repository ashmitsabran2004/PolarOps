from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import FormView

from accounts.permissions import RoleRequiredMixin, can
from core.crud import RiskAssessmentForm
from expeditions.models import Expedition
from risk.models import WeatherReading
from risk.services import fetch_open_meteo, latest_weather


class RiskEntryView(RoleRequiredMixin, FormView):
    permission_action = 'risk.assess'
    template_name = 'risk/assessment_form.html'
    form_class = RiskAssessmentForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        expedition = get_object_or_404(Expedition, pk=kwargs['expedition_id'])
        if not can(request.user, self.permission_action, expedition):
            raise PermissionDenied
        self.expedition = expedition
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['expedition'] = self.expedition.pk
        cached = latest_weather(self.expedition)
        if cached:
            initial.update({'temperature': float(cached.temperature), 'wind_kph': cached.wind_kph, 'visibility_km': float(cached.visibility_km), 'daylight_hours': float(cached.daylight_hours)})
        return initial

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['expedition'] = self.expedition
        c['latest_weather'] = latest_weather(self.expedition)
        return c

    def form_valid(self, form):
        result = form.save(commit=False)
        if result.override_verdict:
            result.verdict = result.override_verdict
            result.override_by = self.request.user
            result.override_at = timezone.now()
        result._history_user = self.request.user
        result.save()
        self.expedition.risk_score = result.score
        self.expedition._history_user = self.request.user
        self.expedition.save(update_fields=['risk_score'])
        messages.success(self.request, f'Risk assessment recorded: {result.verdict} · {result.score}/100.')
        return redirect('expedition_detail', pk=self.expedition.pk)


class WeatherFetchView(RoleRequiredMixin, View):
    permission_action = 'risk.weather'
    http_method_names = ['post']

    def post(self, request, expedition_id):
        expedition = get_object_or_404(Expedition, pk=expedition_id)
        if not can(request.user, self.permission_action, expedition):
            raise PermissionDenied
        try:
            reading = fetch_open_meteo(expedition)
            cached = WeatherReading.objects.create(expedition=expedition, temperature=reading['temperature'], wind_kph=reading['wind_kph'], visibility_km=reading['visibility_km'], daylight_hours=reading['daylight_hours'], payload=reading['payload'])
            messages.success(request, 'A current weather reading was recorded.')
            return JsonResponse({'status': 'success', 'source': 'Live', 'notice': f'Live Open-Meteo reading · {cached.fetched_at:%Y-%m-%d %H:%M} UTC', 'reading': {'temperature': float(cached.temperature), 'wind_kph': cached.wind_kph, 'visibility_km': float(cached.visibility_km), 'daylight_hours': float(cached.daylight_hours)}})
        except Exception as error:
            cached = latest_weather(expedition)
            if cached:
                notice=f'Weather provider offline. Using last successful reading from {cached.fetched_at:%Y-%m-%d %H:%M} UTC. Review it before submitting.'
                return JsonResponse({'status':'cached','source':'Cached','notice':notice,'reading':{'temperature':float(cached.temperature),'wind_kph':cached.wind_kph,'visibility_km':float(cached.visibility_km),'daylight_hours':float(cached.daylight_hours)}})
            return JsonResponse({'status':'manual','source':'Manual','notice':'Weather provider unavailable and no cached reading exists. Enter conditions manually.','reading':None},status=503)
