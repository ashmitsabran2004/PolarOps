from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView, ListView, FormView, DetailView
from django.contrib.auth.models import Group
from django.db.models import Count
from django.urls import reverse_lazy
from django import forms
from expeditions.models import Expedition,Depot
from assets.models import Asset
from inventory.models import StockItem
from transport.models import TransportPlan
from core.models import Alert
from core.services import assess_risk
from accounts.permissions import (
    ADMINISTRATOR, EXPEDITION_LEADER, FIELD_MEMBER, LOGISTICS_OFFICER,
    ExpeditionScopedMixin, RoleRequiredMixin, can, scoped_queryset, user_role,
)

class RoleMixin(RoleRequiredMixin):
    permission_action = 'dashboard.view'

class ExpeditionSelectionView(RoleMixin,TemplateView):
    """Store a validated expedition scope, or clear it for the global dashboard."""
    http_method_names=['post']
    def post(self,request,*args,**kwargs):
        from django.shortcuts import redirect
        from django.core.exceptions import PermissionDenied
        from core.scope import SESSION_KEY,available_expeditions
        selected=request.POST.get('expedition_id','').strip()
        if selected:
            expedition=available_expeditions(request.user).filter(pk=selected).first()
            if not expedition: raise PermissionDenied('You cannot select that expedition.')
            request.session[SESSION_KEY]=str(expedition.pk)
        else:
            request.session.pop(SESSION_KEY,None)
        return redirect('dashboard')

class DashboardView(RoleMixin,TemplateView):
    template_name='core/dashboard.html'
    permission_action='dashboard.view'
    def get_context_data(self,**kwargs):
        from django.db.models import F,Q
        from django.utils import timezone
        from core.scope import available_expeditions,selected_expedition
        from core.services import dashboard_risk_snapshot
        from core.notifications import visible_alerts
        from emergency.models import SOSEvent
        c=super().get_context_data(**kwargs); user=self.request.user; role=user_role(user)
        available=available_expeditions(user)
        selected=selected_expedition(self.request)
        all_expeditions=available.select_related('contingency').prefetch_related('team__certifications','assets','supplies','assessments','sos_events__status_history__changed_by')
        scoped=all_expeditions.filter(pk=selected.pk) if selected else all_expeditions
        expeditions=list(scoped.distinct())
        snapshots=[dashboard_risk_snapshot(expedition) for expedition in expeditions]
        snapshots_by_id={expedition.pk:snapshot for expedition,snapshot in zip(expeditions,snapshots)}
        readiness_values=[]
        for expedition,snapshot in zip(expeditions,snapshots):
            expedition.risk_score=snapshot['risk']['score']
            factors=snapshot['risk'].get('factors',{})
            readiness_values.append(max(0,round(100-(sum(float(factors.get(key,0)) for key in ('team_readiness','equipment_readiness','supply_sufficiency'))/30*100))))
        readiness_score=round(sum(readiness_values)/len(readiness_values)) if readiness_values else 0
        if selected:
            risk=snapshots_by_id[selected.pk]['risk']; weather_info=snapshots_by_id[selected.pk]
        elif snapshots:
            weather_info=max(snapshots,key=lambda snapshot:snapshot['risk']['score'])
            risk=weather_info['risk']
        else:
            risk={'score':0,'verdict':'NO-GO','factors':{}}
            weather_info={'weather':{},'weather_source':'Manual','weather_notice':'No expedition is available.' ,'weather_at':None}
        exp_ids=[e.pk for e in expeditions]
        asset_qs=Asset.objects.filter(expedition_id__in=exp_ids).select_related('expedition')
        assets=list(asset_qs)
        supplies=StockItem.objects.filter(expedition_id__in=exp_ids).select_related('expedition').order_by('category','name')
        supply_items=list(supplies)
        alert_qs=visible_alerts(user).filter(acknowledged=False).select_related('expedition').order_by('-created_at')
        sos_qs=SOSEvent.objects.filter(expedition_id__in=exp_ids,status__in=['open','acknowledged']).select_related('expedition','reported_by').prefetch_related('status_history__changed_by')
        if role == FIELD_MEMBER:
            sos_qs=sos_qs.filter(expedition__team__user=user)
        transports=list(TransportPlan.objects.filter(expedition_id__in=exp_ids,status__in=['scheduled','in_transit'],ends_at__gte=timezone.now()).select_related('expedition').order_by('starts_at')[:8])
        depots=Depot.objects.filter(expedition_id__in=exp_ids).select_related('expedition').prefetch_related('expedition__assessments')
        import math
        markers=[]
        for expedition in expeditions:
            lat=float(expedition.latitude);lon=float(expedition.longitude);assessment=expedition.assessments.first()
            result=snapshots_by_id[expedition.pk]['risk']
            markers.append({'name':expedition.name,'lat':lat,'lon':lon,'pk':expedition.pk,'status':expedition.get_status_display(),'risk':result['verdict'],'risk_score':result['score'],'region':expedition.get_region_display(),'active':expedition.status=='active','url':f'/expeditions/{expedition.pk}/','x':round((lon+180)/360*900,1),'y':round(220-(lat/90)*190,1),'evacuation_route':getattr(getattr(expedition,'contingency',None),'evacuation_route','')})
        map_depots=[]
        for depot in depots:
            parent=depot.expedition;result=snapshots_by_id.get(parent.pk,{}).get('risk',{}) if parent else {}
            map_depots.append({'name':depot.name,'lat':float(depot.latitude),'lon':float(depot.longitude),'status':depot.get_status_display(),'expedition':parent.name if parent else 'Unassigned','region':parent.get_region_display() if parent else 'Unassigned','risk':result.get('verdict','—'),'risk_score':result.get('score',parent.risk_score if parent else 0),'url':f'/expeditions/{parent.pk}/' if parent else '#','x':round((float(depot.longitude)+180)/360*900,1),'y':round(220-(float(depot.latitude)/90)*190,1)})
        chart_rows=supply_items[:8]
        chart_max=max([float(item.quantity) for item in chart_rows]+[1.0])
        chart={'labels':[item.name for item in chart_rows],'values':[round(float(item.quantity)/chart_max*100,1) for item in chart_rows]}
        stock_rows=[{'item':item,'percent':min(100,round(float(item.quantity)/max(float(item.minimum)*2,1)*100))} for item in supply_items[:8]]
        alert_qs=alert_qs.filter(expedition_id__in=exp_ids) if selected else alert_qs.filter(Q(expedition_id__in=exp_ids)|Q(expedition__isnull=True))
        open_alert_count=alert_qs.count()
        active_count=sum(e.status=='active' for e in expeditions);planned_count=sum(e.status=='planned' for e in expeditions)
        badge={'score':risk['score'],'verdict':risk['verdict']}
        preview=self.request.GET.get('theme') if role == ADMINISTRATOR else None
        map_region=preview if preview in ('antarctica','arctic','himalaya','subantarctic','greenland') else (selected.region if selected else (expeditions[0].region if expeditions else 'antarctica'))
        c.update({'open_sos':sos_qs.distinct(),'expeditions':expeditions,'active_count':active_count,'planned_count':planned_count,'asset_count':len(assets),'open_alert_count':open_alert_count,'readiness_score':readiness_score,'low_stock':supply_items,'supply_items':supply_items,'stock_rows':stock_rows,'stock_chart':chart,'at_risk':sorted(assets,key=lambda a:a.maintenance_risk,reverse=True)[:5],'transports':transports,'alerts':alert_qs[:8],'risk':risk,'risk_badge':badge,'scope_label':selected.name if selected else 'All expeditions','selected_expedition_id':selected.pk if selected else '', 'map_markers':markers,'map_depots':map_depots,'map_routes':[{'expedition':p.expedition_id,'name':p.expedition.name,'status':p.status,'route':p.route,'url':f'/expeditions/{p.expedition_id}/'} for p in TransportPlan.objects.filter(expedition_id__in=exp_ids,kind='traverse',status__in=['scheduled','in_transit']).select_related('expedition')],'map_default_layer':'satellite' if map_region in ('antarctica','arctic') else 'terrain','weather':weather_info['weather'],'weather_source':weather_info['weather_source'],'weather_notice':weather_info['weather_notice'],'weather_at':weather_info['weather_at'],'role_name':role})
        if role == FIELD_MEMBER:
            from assets.models import AssetCheckout
            profile=getattr(user,'field_profile',None)
            c['checked_out_assets']=AssetCheckout.objects.filter(taken_by=profile,checkin_date__isnull=True).select_related('asset','expedition') if profile else []
            self.template_name='core/dashboard_field.html'
        elif role == EXPEDITION_LEADER:
            from inventory.models import Requisition
            c['pending_approvals']=Requisition.objects.filter(expedition__in=expeditions,status='submitted').select_related('requester')
            self.template_name='core/dashboard_leader.html'
        elif role == LOGISTICS_OFFICER:
            from inventory.models import Requisition
            c['pending_fulfillment']=Requisition.objects.filter(status='approved').select_related('expedition')
            self.template_name='core/dashboard_logistics.html'
        return c
class ExpeditionListView(RoleMixin,ListView):
    model=Expedition; template_name='expeditions/list.html'; context_object_name='expeditions'; paginate_by=12
    def get_queryset(self):
        qs=Expedition.objects.prefetch_related('team','assets').all(); user=self.request.user
        qs=scoped_queryset(user,qs)
        from core.scope import scope_model_queryset
        return scope_model_queryset(self.request,Expedition,qs).distinct()
class SupplyForm(forms.Form):
    team_size=forms.IntegerField(min_value=1,initial=8); days=forms.IntegerField(min_value=1,initial=30); region=forms.ChoiceField(choices=Expedition.REGION); season=forms.CharField(initial='standard'); buffer=forms.DecimalField(min_value=0,max_value=2,initial='.20')
class CalculatorView(RoleMixin,FormView):
    permission_action='calculator.run'
    template_name='core/calculator.html'; form_class=SupplyForm
    def form_valid(self,form):
        from core.services import calculate_requirements
        self.extra_context={'results':calculate_requirements(form.cleaned_data['team_size'],form.cleaned_data['days'],form.cleaned_data['region'],form.cleaned_data['season'],float(form.cleaned_data['buffer']))}
        return self.render_to_response(self.get_context_data(form=form,**self.extra_context))
class AlertsView(RoleMixin,ListView):
    permission_action='alerts.view'
    model=Alert; template_name='core/alerts.html'; context_object_name='alerts'; paginate_by=25
    def get_queryset(self):
        from core.scope import selected_expedition
        qs=Alert.objects.filter(acknowledged=False).select_related('expedition')
        expedition=selected_expedition(self.request)
        return qs.filter(expedition=expedition) if expedition else qs

class ExpeditionDetailView(RoleMixin,DetailView):
    permission_action='expedition.view'
    model=Expedition
    template_name='expeditions/detail.html'
    context_object_name='expedition'
    def get_queryset(self):
        qs=Expedition.objects.prefetch_related('team__user','assets','supplies','transport_plans','assessments','sos_events')
        qs=scoped_queryset(self.request.user,qs)
        from core.scope import scope_model_queryset
        return scope_model_queryset(self.request,Expedition,qs).distinct()
