from django.contrib import admin
from core.models import Alert,AlertReceipt
from expeditions.models import Expedition
from personnel.models import PersonnelProfile
from assets.models import Asset,MaintenanceRecord
from inventory.models import StockItem,StockMovement,ColdChainBreach
from transport.models import TransportPlan
from risk.models import RiskAssessment,ConsumptionRate
from emergency.models import ContingencyPlan
admin.site.register([Alert,AlertReceipt,Expedition,PersonnelProfile,Asset,MaintenanceRecord,StockItem,StockMovement,ColdChainBreach,TransportPlan,RiskAssessment,ConsumptionRate,ContingencyPlan])
