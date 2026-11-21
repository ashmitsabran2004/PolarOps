"""Role-gated class-based operational CRUD views."""
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from assets.models import Asset, MaintenanceRecord
from emergency.models import ContingencyPlan, SOSEvent
from expeditions.models import Expedition, Depot
from inventory.models import StockItem, StockMovement
from personnel.models import PersonnelProfile, Certification
from risk.models import RiskAssessment
from transport.models import TransportPlan
from accounts.permissions import (
    ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER,
    ExpeditionScopedMixin, RoleRequiredMixin, can, user_role,
)
from core.scope import scope_model_queryset

MANAGERS=(ADMINISTRATOR,EXPEDITION_LEADER,LOGISTICS_OFFICER)
class PolarForm(forms.ModelForm):
    """Apply shared styling while preserving Django field validation."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class','form-control')
            field.widget.attrs.setdefault('placeholder',field.label)
            if isinstance(field.widget,forms.DateInput): field.widget.attrs.setdefault('type','date')
            if isinstance(field.widget,forms.DateTimeInput): field.widget.attrs.setdefault('type','datetime-local')
        self.error_css_class='field-error'
class ExpeditionForm(PolarForm):
    class Meta: model=Expedition; fields=['name','region','latitude','longitude','start_date','end_date','objectives','status','leader','team']
    def clean_leader(self):
        leader=self.cleaned_data.get('leader')
        if leader and user_role(leader)!=EXPEDITION_LEADER:
            raise ValidationError('Assign an account with the Expedition Leader role.')
        return leader
    def clean_team(self):
        team=self.cleaned_data['team']
        expired=[]
        for person in team:
            if not person.assignment_eligible():
                expired.append(str(person))
                continue
            other_missions=person.expeditions.exclude(pk=getattr(self.instance,'pk',None))
            if other_missions.exists():
                expired.append(f'{person} (already assigned to another expedition)')
        if expired: raise ValidationError('Medical clearance expired or missing for: '+', '.join(expired))
        return team
class DepotForm(PolarForm):
    class Meta: model=Depot; fields=['expedition','name','latitude','longitude','status','notes']
class PersonnelForm(PolarForm):
    class Meta: model=PersonnelProfile; fields=['user','role','nationality','blood_group','emergency_contact','medical_cleared','medical_expiry','first_aid_expiry','glacier_rescue_expiry','polar_survival_expiry','vehicle_operation_expiry']
class CertificationForm(PolarForm):
    class Meta: model=Certification; fields=['profile','kind','issued_on','expires_on','credential_id']
class AssetForm(PolarForm):
    class Meta: model=Asset; fields=['code','name','category','condition','location','expedition','purchase_date','usage_hours','cold_exposure_hours','last_service']
class MaintenanceForm(PolarForm):
    class Meta: model=MaintenanceRecord; fields=['asset','service_date','summary','next_due']
class StockItemForm(PolarForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance and self.instance.pk:
            self.fields.pop('quantity',None)
    class Meta: model=StockItem; fields=['code','name','category','quantity','unit','minimum','location','expedition','cold_min','cold_max']
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('cold_min') is not None and cleaned.get('cold_max') is not None and cleaned['cold_min']>cleaned['cold_max']:
            self.add_error('cold_max','Maximum temperature must be at least the minimum temperature.')
        return cleaned
class StockMovementForm(PolarForm):
    def __init__(self,*args,**kwargs):
        instance=kwargs.get('instance')
        self.original_item_id=instance.item_id if instance and instance.pk else None
        self.original_delta=instance.delta if instance and instance.pk else None
        super().__init__(*args,**kwargs)
    class Meta: model=StockMovement; fields=['item','delta','reason']
    def save(self,commit=True):
        from django.db import transaction
        from django.db.models import F
        from decimal import Decimal
        old_item_id=self.original_item_id
        old_delta=self.original_delta if self.original_delta is not None else Decimal('0')
        movement=super().save(commit=False); movement.by=self.current_user
        if commit:
            with transaction.atomic():
                ids=sorted({x for x in (old_item_id,movement.item_id) if x})
                locked={x.pk:x for x in StockItem.objects.select_for_update().filter(pk__in=ids)}
                if old_item_id and old_item_id!=movement.item_id:
                    old_item=locked[old_item_id]
                    if old_item.quantity-old_delta<0: raise ValidationError('This movement cannot be removed because the stock has since been consumed.')
                    StockItem.objects.filter(pk=old_item_id).update(quantity=F('quantity')-old_delta)
                    new_item=locked[movement.item_id]
                    if new_item.quantity+movement.delta<0: raise ValidationError('Movement would reduce stock below zero.')
                    StockItem.objects.filter(pk=movement.item_id).update(quantity=F('quantity')+movement.delta)
                else:
                    item=locked[movement.item_id]; adjustment=movement.delta-old_delta
                    if item.quantity+adjustment<0: raise ValidationError('Movement would reduce stock below zero.')
                    StockItem.objects.filter(pk=item.pk).update(quantity=F('quantity')+adjustment)
                movement.save()
        return movement
class TransportForm(PolarForm):
    class Meta: model=TransportPlan; fields=['expedition','kind','vehicle','starts_at','ends_at','capacity','route','status','people']
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('starts_at') and cleaned.get('ends_at') and cleaned['ends_at']<=cleaned['starts_at']:
            self.add_error('ends_at','End time must be after start time.')
        if cleaned.get('starts_at') and cleaned.get('ends_at') and cleaned.get('vehicle'):
            from core.services import transport_conflicts
            conflicts=transport_conflicts(cleaned['vehicle'],cleaned['starts_at'],cleaned['ends_at'],cleaned.get('people'),getattr(self.instance,'pk',None))
            if conflicts: self.add_error(None,'Schedule conflict: this vehicle or one of the selected people is already assigned during that time.')
        return cleaned
class ContingencyPlanForm(PolarForm):
    class Meta: model=ContingencyPlan; fields=['expedition','evacuation_route','nearest_stations','checklist']
class RiskAssessmentForm(PolarForm):
    override_verdict=forms.ChoiceField(choices=[('', 'Use calculated verdict')]+[x for x in [('GO','GO'),('CAUTION','CAUTION'),('NO-GO','NO-GO')]],required=False,label='Decision override')
    override_reason=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':2}),label='Override reason')
    class Meta: model=RiskAssessment; fields=['expedition','temperature','wind_kph','visibility_km','daylight_hours']
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('override_verdict') and not cleaned.get('override_reason','').strip():
            self.add_error('override_reason','A written reason is required for a Go/No-Go override.')
        if cleaned.get('override_reason','').strip() and not cleaned.get('override_verdict'):
            self.add_error('override_verdict','Choose the verdict to apply with this reason.')
        return cleaned
    def save(self,commit=True):
        from core.services import assess_risk
        assessment=super().save(commit=False); result=assess_risk(assessment.temperature,assessment.wind_kph,assessment.visibility_km,assessment.daylight_hours)
        assessment.score=result['score']; assessment.verdict=result['verdict']; assessment.factors=result['factors']
        assessment.override_reason=self.cleaned_data.get('override_reason','')
        if commit: assessment.save()
        return assessment
class SOSForm(PolarForm):
    class Meta: model=SOSEvent; fields=['expedition','latitude','longitude','details']

RESOURCES={
 'expeditions':(Expedition,ExpeditionForm,['name','region','status','start_date','end_date']),
 'depots':(Depot,DepotForm,['name','expedition','latitude','longitude','status']),
 'personnel':(PersonnelProfile,PersonnelForm,['user','role','nationality','medical_cleared','medical_expiry']),
 'certifications':(Certification,CertificationForm,['profile','kind','expires_on','credential_id']),
 'assets':(Asset,AssetForm,['code','name','category','condition','location']),
 'maintenance':(MaintenanceRecord,MaintenanceForm,['asset','service_date','summary','next_due']),
 'inventory':(StockItem,StockItemForm,['code','name','category','quantity','unit','minimum','location']),
 'movements':(StockMovement,StockMovementForm,['item','delta','reason','at']),
 'transport':(TransportPlan,TransportForm,['expedition','kind','vehicle','starts_at','ends_at','status']),
 'emergency-plans':(ContingencyPlan,ContingencyPlanForm,['expedition','evacuation_route','nearest_stations']),
 'risk-assessments':(RiskAssessment,RiskAssessmentForm,['expedition','score','verdict','assessed_at']),
}

def resource_config(view):
    resource=view.kwargs['resource']
    if resource not in RESOURCES: raise __import__('django.http',fromlist=['Http404']).Http404()
    return resource,RESOURCES[resource]
class ManagerView(RoleRequiredMixin,ExpeditionScopedMixin):
    """Map resource/method pairs to the centralized permission declaration."""
    permission_action='record.delete'
    VIEW_ACTIONS={'expeditions':'expedition.view','depots':'depot.view','personnel':'personnel.view','certifications':'certification.view','assets':'asset.view','maintenance':'maintenance.view','inventory':'inventory.view','movements':'inventory.view','transport':'transport.view','emergency-plans':'emergency.view','risk-assessments':'risk.view'}
    CREATE_ACTIONS={'expeditions':'expedition.create','depots':'depot.manage','personnel':'personnel.manage','certifications':'certification.manage','assets':'asset.manage','maintenance':'maintenance.manage','inventory':'inventory.manage','movements':'inventory.manage','transport':'transport.create','emergency-plans':'emergency.edit','risk-assessments':'risk.assess'}
    EDIT_ACTIONS={'expeditions':'expedition.edit','depots':'depot.manage','personnel':'personnel.manage','certifications':'certification.manage','assets':'asset.manage','maintenance':'maintenance.manage','inventory':'inventory.manage','movements':'inventory.manage','transport':'transport.edit','emergency-plans':'emergency.edit','risk-assessments':'risk.edit'}
    def get_permission_action(self):
        resource=getattr(self,'resource','')
        if isinstance(self,ResourceDeleteView): return 'record.delete'
        if isinstance(self,ResourceUpdateView): return self.EDIT_ACTIONS.get(resource,'record.delete')
        if isinstance(self,ResourceCreateView): return self.CREATE_ACTIONS.get(resource,'record.delete')
        return self.VIEW_ACTIONS.get(resource,'record.delete')
    def get_queryset(self):
        qs=super().get_queryset()
        model=getattr(self,'model',None) or getattr(self,'config',(None,))[0]
        return scope_model_queryset(self.request,model,qs) if model else qs
class ResourceListView(ManagerView,ListView):
    template_name='core/resource_list.html'; paginate_by=15
    def dispatch(self,request,*args,**kwargs): self.resource,self.config=resource_config(self); self.model=self.config[0]; return super().dispatch(request,*args,**kwargs)
    def get_queryset(self):
        model,form,columns=self.config; qs=model.objects.all()
        if not model._meta.ordering: qs=qs.order_by('-pk')
        forward=[field.name for field in model._meta.fields if field.is_relation and (field.many_to_one or field.one_to_one)]
        many=[field.name for field in model._meta.many_to_many]
        if forward: qs=qs.select_related(*forward)
        if model is Certification: qs=qs.select_related('profile__user')
        if model is StockMovement: qs=qs.select_related('item__expedition','by')
        if many: qs=qs.prefetch_related(*many)
        q=self.request.GET.get('q','').strip()
        if q:
            terms=[f.name for f in model._meta.fields if getattr(f,'get_internal_type',lambda:'' )() in ('CharField','TextField')]
            query=Q()
            for field in terms: query|=Q(**{f'{field}__icontains':q})
            if query.children: qs=qs.filter(query)
        for field in ('region','status','category','kind','condition','location'):
            value=self.request.GET.get(field)
            if value and field in [f.name for f in model._meta.fields]: qs=qs.filter(**{field:value})
        from core.scope import scope_model_queryset
        qs=scope_model_queryset(self.request,model,qs)
        if model is StockMovement and user_role(self.request.user)=='Field Member': qs=qs.filter(movement_type='usage')
        return qs
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs)
        model=self.config[0]; columns=self.config[2]; filters=[]; rows=[]
        for name in ('region','status','category','kind','condition','location'):
            try: field=model._meta.get_field(name)
            except Exception: continue
            if field.choices:
                filters.append({'name':name,'current':self.request.GET.get(name,''),'choices':field.choices})
        for obj in c['object_list']:
            cells=[]
            for name in columns:
                display=getattr(obj,f'get_{name}_display',None)
                value=display() if display else getattr(obj,name,'—')
                if hasattr(value,'all'): value=', '.join(str(x) for x in value.all())
                cells.append(value if value is not None else '—')
            rows.append({'object':obj,'cells':cells})
        c.update({'resource':self.resource,'columns':columns,'filters':filters,'rows':rows,'can_create_record':can(self.request.user,self.CREATE_ACTIONS.get(self.resource,'record.delete'))})
        return c
class ResourceDetailView(ManagerView,DetailView):
    template_name='core/resource_detail.html'; context_object_name='object'
    def dispatch(self,request,*args,**kwargs): self.resource,self.config=resource_config(self); self.model=self.config[0]; return super().dispatch(request,*args,**kwargs)
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c['resource']=self.resource; c['fields']=[(f.verbose_name.title(),getattr(self.object,f.name)) for f in self.object._meta.fields if f.name not in ('id',)]
        c['can_edit_record']=can(self.request.user,self.EDIT_ACTIONS.get(self.resource,'record.delete'),self.object)
        c['can_delete_record']=can(self.request.user,'record.delete',self.object)
        c['can_approve_transport']=self.resource=='transport' and can(self.request.user,'transport.approve',self.object)
        return c
class ResourceCreateView(ManagerView,CreateView):
    template_name='core/resource_form.html'
    def dispatch(self,request,*args,**kwargs): self.resource,self.config=resource_config(self); self.model,self.form_class,_=self.config; return super().dispatch(request,*args,**kwargs)
    def get_form(self, form_class=None):
        form=super().get_form(form_class)
        role=user_role(self.request.user)
        for field in form.fields.values():
            qs=getattr(field,'queryset',None)
            if qs is not None and hasattr(qs,'model'):
                if qs.model is PersonnelProfile and role == EXPEDITION_LEADER:
                    from django.utils import timezone
                    from django.db.models import Q
                    field.queryset=qs.filter(medical_cleared=True,medical_expiry__gte=timezone.localdate()).filter(Q(expeditions__isnull=True)|Q(expeditions__leader=self.request.user)).distinct()
                else:
                    field.queryset=scope_model_queryset(self.request,qs.model,qs)
        if isinstance(form,ExpeditionForm) and role==EXPEDITION_LEADER:
            form.fields.pop('leader',None)
        if isinstance(form,TransportForm) and role==LOGISTICS_OFFICER:
            form.fields.pop('status',None)
        if self.model is Expedition and role==EXPEDITION_LEADER:
            form.fields.pop('leader',None)
        return form
    def get_success_url(self): return reverse('resource_detail',kwargs={'resource':self.resource,'pk':self.object.pk})
    def form_valid(self,form):
        if isinstance(form,ExpeditionForm) and user_role(self.request.user)==EXPEDITION_LEADER:
            form.instance.leader=self.request.user
        if isinstance(form,TransportForm):
            if self.object is None:
                form.instance.created_by=self.request.user
            if user_role(self.request.user)==LOGISTICS_OFFICER:
                form.instance.approval_status='pending'
                form.instance.status='scheduled'
                form.instance.approved_by=None
                form.instance.approved_at=None
                form.instance.approval_note=''
        if isinstance(form,RiskAssessmentForm) and form.cleaned_data.get('override_verdict'):
            from django.utils import timezone
            form.instance.override_verdict=form.cleaned_data['override_verdict']
            form.instance.override_reason=form.cleaned_data['override_reason']
            form.instance.override_by=self.request.user
            form.instance.override_at=timezone.now()
        form.instance._history_user=self.request.user
        if isinstance(form,StockMovementForm): form.current_user=self.request.user
        try: response=super().form_valid(form)
        except ValidationError as error:
            form.add_error(None,error);return self.form_invalid(form)
        messages.success(self.request,'Record created successfully.'); return response
class ResourceUpdateView(ResourceCreateView,UpdateView):
    def form_valid(self,form):
        if isinstance(form,StockMovementForm): form.current_user=self.request.user
        response=super().form_valid(form); messages.success(self.request,'Changes saved successfully.'); return response
class ResourceDeleteView(ManagerView,DeleteView):
    template_name='core/resource_confirm_delete.html'
    def dispatch(self,request,*args,**kwargs): self.resource,self.config=resource_config(self); self.model=self.config[0]; return super().dispatch(request,*args,**kwargs)
    def get_success_url(self): return reverse('resource_list',kwargs={'resource':self.resource})
    def form_valid(self,form):
        if isinstance(self.object,StockMovement):
            from django.db import transaction
            from django.db.models import F
            with transaction.atomic():
                item=StockItem.objects.select_for_update().get(pk=self.object.item_id)
                if item.quantity-self.object.delta<0:
                    form.add_error(None,'Cannot delete this movement because the stock has since been consumed.')
                    return self.form_invalid(form)
                StockItem.objects.filter(pk=item.pk).update(quantity=F('quantity')-self.object.delta)
                response=super().form_valid(form)
        else: response=super().form_valid(form)
        messages.success(self.request,'Record deleted.'); return response
