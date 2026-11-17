from django.db import models
from simple_history.models import HistoricalRecords
class ConsumptionRate(models.Model):
    region=models.CharField(max_length=24); season=models.CharField(max_length=24,default='standard'); item=models.CharField(max_length=24); per_person_day=models.DecimalField(max_digits=8,decimal_places=3); temperature_factor=models.DecimalField(max_digits=5,decimal_places=2,default=1); updated_at=models.DateTimeField(auto_now=True)
    class Meta: unique_together=[('region','season','item')]
class RiskAssessment(models.Model):
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.CASCADE,related_name='assessments'); temperature=models.DecimalField(max_digits=5,decimal_places=1); wind_kph=models.PositiveSmallIntegerField(); visibility_km=models.DecimalField(max_digits=5,decimal_places=1); daylight_hours=models.DecimalField(max_digits=4,decimal_places=1); score=models.PositiveSmallIntegerField(); verdict=models.CharField(max_length=12); factors=models.JSONField(default=dict); assessed_at=models.DateTimeField(auto_now_add=True)
    override_verdict=models.CharField(max_length=12,blank=True)
    override_reason=models.TextField(blank=True)
    override_by=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='risk_overrides')
    override_at=models.DateTimeField(null=True,blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['-assessed_at']

class WeatherReading(models.Model):
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.CASCADE,related_name='weather_readings')
    temperature=models.DecimalField(max_digits=5,decimal_places=1)
    wind_kph=models.PositiveSmallIntegerField()
    visibility_km=models.DecimalField(max_digits=5,decimal_places=1)
    daylight_hours=models.DecimalField(max_digits=4,decimal_places=1)
    source=models.CharField(max_length=32,default='open-meteo')
    fetched_at=models.DateTimeField(auto_now_add=True)
    payload=models.JSONField(default=dict,blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['-fetched_at']; indexes=[models.Index(fields=['expedition','-fetched_at'])]
