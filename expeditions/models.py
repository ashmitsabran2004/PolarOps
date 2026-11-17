from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from simple_history.models import HistoricalRecords
class Expedition(models.Model):
    STATUS=[('planned','Planned'),('active','Active'),('completed','Completed'),('aborted','Aborted')]
    REGION=[('antarctica','Antarctica'),('arctic','Arctic'),('himalaya','Himalaya / High altitude'),('subantarctic','Subantarctic / Sea voyage'),('greenland','Greenland / Tundra')]
    name=models.CharField(max_length=140); region=models.CharField(max_length=24,choices=REGION); latitude=models.DecimalField(max_digits=8,decimal_places=5); longitude=models.DecimalField(max_digits=8,decimal_places=5)
    start_date=models.DateField(); end_date=models.DateField(); objectives=models.TextField(blank=True); status=models.CharField(max_length=12,choices=STATUS,default='planned'); risk_score=models.PositiveSmallIntegerField(default=0,validators=[MaxValueValidator(100)])
    leader=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='led_expeditions')
    team=models.ManyToManyField('personnel.PersonnelProfile',blank=True,related_name='expeditions'); created_at=models.DateTimeField(auto_now_add=True); history=HistoricalRecords()
    class Meta: ordering=['-start_date']; indexes=[models.Index(fields=['status','region'])]
    def __str__(self): return self.name

class Depot(models.Model):
    """A mapped logistics depot with its own surveyed WGS84 coordinates."""
    expedition=models.ForeignKey(Expedition,null=True,blank=True,on_delete=models.SET_NULL,related_name='depots')
    name=models.CharField(max_length=120,unique=True)
    latitude=models.DecimalField(max_digits=8,decimal_places=5,validators=[MinValueValidator(-90),MaxValueValidator(90)])
    longitude=models.DecimalField(max_digits=8,decimal_places=5,validators=[MinValueValidator(-180),MaxValueValidator(180)])
    status=models.CharField(max_length=16,choices=[('active','Active'),('standby','Standby'),('closed','Closed')],default='active')
    notes=models.TextField(blank=True)
    history=HistoricalRecords()
    class Meta:
        ordering=['name']
        indexes=[models.Index(fields=['status','latitude','longitude'])]
    def __str__(self): return self.name
