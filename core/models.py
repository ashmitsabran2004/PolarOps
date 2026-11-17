from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
class Alert(models.Model):
    TYPES=[('stock','Low stock'),('cert','Certification expiry'),('maintenance','Maintenance overdue'),('cold','Cold-chain breach'),('sos','SOS')]
    SEVERITIES=[(1,'Low'),(2,'Medium'),(3,'High'),(4,'Critical')]
    kind=models.CharField(max_length=16,choices=TYPES); severity=models.PositiveSmallIntegerField(choices=SEVERITIES,default=1); title=models.CharField(max_length=160); detail=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); acknowledged=models.BooleanField(default=False); recipient=models.ForeignKey(User,null=True,blank=True,on_delete=models.CASCADE,related_name='polar_alerts'); expedition=models.ForeignKey('expeditions.Expedition',null=True,blank=True,on_delete=models.CASCADE); history=HistoricalRecords()
    class Meta: ordering=['-created_at']

class AlertReceipt(models.Model):
    alert=models.ForeignKey(Alert,on_delete=models.CASCADE,related_name='receipts')
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='alert_receipts')
    read_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-read_at']
        constraints=[models.UniqueConstraint(fields=['alert','user'],name='unique_alert_read_receipt')]
