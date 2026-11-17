from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from simple_history.models import HistoricalRecords
class PersonnelProfile(models.Model):
    BLOOD=[(x,x) for x in ['A+','A-','B+','B-','AB+','AB-','O+','O-','Unknown']]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='field_profile'); role=models.CharField(max_length=40,default='Field Member'); nationality=models.CharField(max_length=80,blank=True); blood_group=models.CharField(max_length=8,choices=BLOOD,default='Unknown'); contact_number=models.CharField(max_length=32,blank=True); emergency_contact=models.CharField(max_length=160,blank=True); medical_cleared=models.BooleanField(default=False); medical_expiry=models.DateField(null=True,blank=True)
    first_aid_expiry=models.DateField(null=True,blank=True); glacier_rescue_expiry=models.DateField(null=True,blank=True); polar_survival_expiry=models.DateField(null=True,blank=True); vehicle_operation_expiry=models.DateField(null=True,blank=True); history=HistoricalRecords()
    class Meta: indexes=[models.Index(fields=['medical_cleared','medical_expiry'])]
    def assignment_eligible(self): return self.medical_cleared and self.medical_expiry and self.medical_expiry >= timezone.localdate()
    def __str__(self): return self.user.get_full_name() or self.user.username

class Certification(models.Model):
    TYPES=[('first_aid','First aid'),('glacier_rescue','Glacier rescue'),('polar_survival','Polar survival'),('vehicle_operation','Vehicle operation')]
    profile=models.ForeignKey(PersonnelProfile,on_delete=models.CASCADE,related_name='certifications')
    kind=models.CharField(max_length=24,choices=TYPES)
    issued_on=models.DateField(null=True,blank=True)
    expires_on=models.DateField()
    credential_id=models.CharField(max_length=80,blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['expires_on']; indexes=[models.Index(fields=['kind','expires_on'])]
    def __str__(self): return f'{self.profile} · {self.get_kind_display()}'
