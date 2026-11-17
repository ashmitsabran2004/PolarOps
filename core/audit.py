from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.views.generic import TemplateView
from core.permissions import has_role
from expeditions.models import Expedition,Depot
from personnel.models import PersonnelProfile,Certification
from assets.models import Asset,MaintenanceRecord,AssetCheckout
from inventory.models import StockItem,StockMovement,ColdChainBreach,Requisition,RequisitionLine
from transport.models import TransportPlan
from risk.models import RiskAssessment,WeatherReading
from core.models import Alert
from emergency.models import ContingencyPlan,SOSEvent,SOSStatusEvent

AUDITED_MODELS=[Expedition,Depot,PersonnelProfile,Certification,Asset,MaintenanceRecord,AssetCheckout,StockItem,StockMovement,ColdChainBreach,TransportPlan,RiskAssessment,WeatherReading,ContingencyPlan,SOSEvent,SOSStatusEvent,Requisition,RequisitionLine,Alert]
class AuditLogView(TemplateView):
    template_name='core/audit_log.html'
    def dispatch(self,request,*args,**kwargs):
        if not has_role(request.user,'Administrator'): raise PermissionDenied
        return super().dispatch(request,*args,**kwargs)
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs);selected=self.request.GET.get('model','');user_id=self.request.GET.get('user','')
        models=[m for m in AUDITED_MODELS if not selected or m._meta.label_lower==selected]
        entries=[]
        for model in models:
            history_model=model.history.model
            qs=history_model.objects.select_related('history_user').all()
            if user_id: qs=qs.filter(history_user_id=user_id)
            for row in qs[:500]:
                entries.append({'at':row.history_date,'user':row.history_user,'model':model._meta.verbose_name.title(),'object':str(row),'action':{'+' :'Created','~':'Updated','-':'Deleted'}.get(row.history_type,row.history_type),'action_code':row.history_type,'model_key':model._meta.label_lower})
        entries.sort(key=lambda x:x['at'],reverse=True)
        page=Paginator(entries,40).get_page(self.request.GET.get('page'))
        c.update({'page_obj':page,'entries':page.object_list,'model_choices':[(m._meta.label_lower,m._meta.verbose_name.title()) for m in AUDITED_MODELS],'users':User.objects.filter(id__in=[x['user'].pk for x in entries if x['user']]).order_by('username').distinct(),'selected_model':selected,'selected_user':user_id})
        return c
