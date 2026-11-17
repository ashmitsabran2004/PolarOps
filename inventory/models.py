from django.db import models
from django.core.validators import MinValueValidator
from uuid import uuid4
from simple_history.models import HistoricalRecords
def generate_stock_code():
    """Return a collision-resistant fallback code for manually created stock items."""
    return 'STK-'+uuid4().hex[:12].upper()
class StockItem(models.Model):
    CATEGORIES=[('food','Food'),('fuel','Fuel'),('medical','Medical'),('spares','Spare parts'),('sample','Sample')]
    LOCATIONS=[('warehouse','Warehouse'),('depot','Depot'),('camp','Camp')]
    code=models.CharField(max_length=32,unique=True,default=generate_stock_code)
    name=models.CharField(max_length=120); category=models.CharField(max_length=12,choices=CATEGORIES); quantity=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(0)]); unit=models.CharField(max_length=24); minimum=models.DecimalField(max_digits=12,decimal_places=2,default=0); location=models.CharField(max_length=16,choices=LOCATIONS,default='warehouse'); expedition=models.ForeignKey('expeditions.Expedition',null=True,blank=True,on_delete=models.SET_NULL,related_name='supplies'); cold_min=models.DecimalField(max_digits=5,decimal_places=1,null=True,blank=True); cold_max=models.DecimalField(max_digits=5,decimal_places=1,null=True,blank=True); history=HistoricalRecords()
    class Meta: ordering=['category','name']; indexes=[models.Index(fields=['category','location'])]
    @property
    def low_stock(self): return self.quantity <= self.minimum
    def __str__(self): return self.name
class StockMovement(models.Model):
    TYPES=[('receipt','Receipt'),('usage','Field usage'),('adjustment','Adjustment'),('requisition','Requisition fulfilment')]
    item=models.ForeignKey(StockItem,on_delete=models.CASCADE,related_name='movements'); delta=models.DecimalField(max_digits=12,decimal_places=2); reason=models.CharField(max_length=180); at=models.DateTimeField(auto_now_add=True); by=models.ForeignKey('auth.User',null=True,on_delete=models.SET_NULL); movement_type=models.CharField(max_length=16,choices=TYPES,default='adjustment'); history=HistoricalRecords()
class ColdChainBreach(models.Model):
    item=models.ForeignKey(StockItem,on_delete=models.CASCADE,related_name='breaches'); temperature=models.DecimalField(max_digits=5,decimal_places=1); recorded_at=models.DateTimeField(auto_now_add=True); notes=models.CharField(max_length=240,blank=True); history=HistoricalRecords()

class Requisition(models.Model):
    STATUS=[('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('fulfilled','Fulfilled'),('rejected','Rejected')]
    expedition=models.ForeignKey('expeditions.Expedition',on_delete=models.PROTECT,related_name='requisitions')
    requester=models.ForeignKey('auth.User',on_delete=models.PROTECT,related_name='requisitions_requested')
    approver=models.ForeignKey('auth.User',null=True,blank=True,on_delete=models.SET_NULL,related_name='requisitions_approved')
    status=models.CharField(max_length=12,choices=STATUS,default='draft')
    team_size=models.PositiveIntegerField()
    duration_days=models.PositiveIntegerField()
    season=models.CharField(max_length=32,default='standard')
    safety_buffer=models.DecimalField(max_digits=5,decimal_places=3,default='.200')
    created_at=models.DateTimeField(auto_now_add=True)
    submitted_at=models.DateTimeField(null=True,blank=True)
    approved_at=models.DateTimeField(null=True,blank=True)
    fulfilled_at=models.DateTimeField(null=True,blank=True)
    rejection_reason=models.TextField(blank=True)
    history=HistoricalRecords()
    class Meta: ordering=['-created_at']
    def __str__(self): return 'Requisition RQ-%s · %s' % (self.pk or 'NEW',self.expedition.name)

class RequisitionLine(models.Model):
    CATEGORIES=[('food','Food'),('fuel','Fuel'),('water','Water'),('medical','Medical'),('spares','Spare parts')]
    requisition=models.ForeignKey(Requisition,on_delete=models.CASCADE,related_name='lines')
    item_name=models.CharField(max_length=120)
    category=models.CharField(max_length=12,choices=CATEGORIES)
    quantity=models.DecimalField(max_digits=12,decimal_places=2)
    unit=models.CharField(max_length=24)
    stock_item=models.ForeignKey(StockItem,null=True,blank=True,on_delete=models.SET_NULL,related_name='requisition_lines')
    history=HistoricalRecords()
    def __str__(self): return f'{self.item_name} · {self.quantity} {self.unit}'
