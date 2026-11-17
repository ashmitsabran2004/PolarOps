from django.db import models
from simple_history.models import HistoricalRecords
class ContingencyPlan(models.Model):
    expedition=models.OneToOneField('expeditions.Expedition',on_delete=models.CASCADE,related_name='contingency'); evacuation_route=models.TextField(); nearest_stations=models.TextField(blank=True); checklist=models.TextField(blank=True); history=HistoricalRecords()
class SOSEvent(models.Model):
    STATUS=[('open','Open'),('acknowledged','Acknowledged'),('resolved','Resolved')]
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.CASCADE,related_name='sos_events'); reported_by=models.ForeignKey('auth.User',null=True,on_delete=models.SET_NULL); latitude=models.DecimalField(max_digits=8,decimal_places=5); longitude=models.DecimalField(max_digits=8,decimal_places=5); details=models.TextField(); status=models.CharField(max_length=16,choices=STATUS,default='open'); created_at=models.DateTimeField(auto_now_add=True); history=HistoricalRecords()
    class Meta: ordering=['-created_at']

class SOSStatusEvent(models.Model):
    event=models.ForeignKey(SOSEvent,on_delete=models.CASCADE,related_name='status_history')
    from_status=models.CharField(max_length=16,blank=True)
    to_status=models.CharField(max_length=16,choices=SOSEvent.STATUS)
    changed_by=models.ForeignKey('auth.User',null=True,on_delete=models.SET_NULL)
    note=models.CharField(max_length=240,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    history=HistoricalRecords()
    class Meta: ordering=['created_at']
