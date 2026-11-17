from django.db import models
from simple_history.models import HistoricalRecords
class TransportPlan(models.Model):
    TYPES=[('flight','Flight'),('ship','Ship'),('traverse','Vehicle traverse')]
    STATUS=[('scheduled','Scheduled'),('in_transit','In transit'),('complete','Complete'),('cancelled','Cancelled')]
    APPROVAL=[('pending','Pending leader approval'),('approved','Approved'),('rejected','Rejected')]
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.CASCADE,related_name='transport_plans'); kind=models.CharField(max_length=12,choices=TYPES); vehicle=models.CharField(max_length=100); starts_at=models.DateTimeField(); ends_at=models.DateTimeField(); capacity=models.PositiveIntegerField(); route=models.CharField(max_length=240); status=models.CharField(max_length=16,choices=STATUS,default='scheduled'); people=models.ManyToManyField('personnel.PersonnelProfile',blank=True)
    created_by=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='transport_plans_created')
    approval_status=models.CharField(max_length=12,choices=APPROVAL,default='approved')
    approved_by=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='transport_plans_approved')
    approval_note=models.CharField(max_length=240,blank=True)
    approved_at=models.DateTimeField(null=True,blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['starts_at']; indexes=[models.Index(fields=['vehicle','starts_at','ends_at'])]
