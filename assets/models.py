from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q
from simple_history.models import HistoricalRecords
class Asset(models.Model):
    CATEGORIES=[(x,x.replace('_',' ').title()) for x in ['vehicle','shelter','power','communication','scientific_instrument','safety_gear']]
    CONDITIONS=[('ready','Ready'),('service','Needs service'),('damaged','Damaged'),('retired','Retired')]
    code=models.CharField(max_length=32,unique=True); name=models.CharField(max_length=120); category=models.CharField(max_length=32,choices=CATEGORIES); condition=models.CharField(max_length=16,choices=CONDITIONS,default='ready'); location=models.CharField(max_length=160,blank=True); expedition=models.ForeignKey('expeditions.Expedition',null=True,blank=True,on_delete=models.SET_NULL,related_name='assets'); purchase_date=models.DateField(null=True,blank=True); usage_hours=models.PositiveIntegerField(default=0); cold_exposure_hours=models.PositiveIntegerField(default=0); last_service=models.DateField(null=True,blank=True); qr_payload=models.CharField(max_length=200,blank=True); checked_out_to=models.ForeignKey('personnel.PersonnelProfile',null=True,blank=True,on_delete=models.SET_NULL); history=HistoricalRecords()
    qr_image=models.ImageField(upload_to='asset_qr/',blank=True)
    class Meta: ordering=['code']; indexes=[models.Index(fields=['condition','category'])]
    def __str__(self): return f'{self.code} · {self.name}'
    @property
    def maintenance_risk(self):
        from django.utils import timezone
        days=(timezone.localdate()-self.last_service).days if self.last_service else 365
        return min(100, round(self.usage_hours/100 + self.cold_exposure_hours/180 + days/3))
class MaintenanceRecord(models.Model):
    asset=models.ForeignKey(Asset,on_delete=models.CASCADE,related_name='maintenance'); service_date=models.DateField(); summary=models.CharField(max_length=240); next_due=models.DateField(null=True,blank=True); history=HistoricalRecords()
    class Meta: ordering=['-service_date']

class AssetCheckout(models.Model):
    asset=models.ForeignKey(Asset,on_delete=models.CASCADE,related_name='checkouts')
    taken_by=models.ForeignKey('personnel.PersonnelProfile',on_delete=models.PROTECT,related_name='asset_checkouts')
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.PROTECT,related_name='asset_checkouts')
    checked_out_by=models.ForeignKey('auth.User',on_delete=models.PROTECT,related_name='asset_checkouts_created')
    checkout_date=models.DateTimeField()
    handover_condition=models.CharField(max_length=16,choices=Asset.CONDITIONS)
    checked_in_by=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='asset_checkins_recorded')
    checkin_date=models.DateTimeField(null=True,blank=True)
    return_condition=models.CharField(max_length=16,choices=Asset.CONDITIONS,blank=True)
    usage_hours_added=models.PositiveIntegerField(default=0)
    cold_exposure_hours_added=models.PositiveIntegerField(default=0)
    damage_notes=models.TextField(blank=True)
    force_checkin_reason=models.TextField(blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['-checkout_date']; indexes=[models.Index(fields=['asset','checkin_date'])]; constraints=[models.UniqueConstraint(fields=['asset'],condition=Q(checkin_date__isnull=True),name='unique_active_asset_checkout')]
    @property
    def active(self): return self.checkin_date is None
    def __str__(self): return f'{self.asset.code} · {self.checkout_date:%Y-%m-%d}'
