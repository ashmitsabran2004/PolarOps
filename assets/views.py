from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView,FormView,TemplateView
from django.utils import timezone
from assets.models import Asset,AssetCheckout
from assets.services import checkout_asset,checkin_asset,asset_qr_data_uri
from core.permissions import has_role
from personnel.models import PersonnelProfile
from expeditions.models import Expedition

MANAGERS=('Administrator','Expedition Leader','Logistics Officer')
class AssetAccessMixin(LoginRequiredMixin):
    def field_profile(self): return getattr(self.request.user,'field_profile',None)
    def allowed_asset(self,asset):
        from core.scope import selected_expedition
        selected=selected_expedition(self.request)
        if selected and asset.expedition_id!=selected.pk: return False
        if has_role(self.request.user,*MANAGERS): return True
        profile=self.field_profile()
        return bool(profile and asset.expedition_id and profile.expeditions.filter(pk=asset.expedition_id).exists())
    def get_asset(self):
        asset=get_object_or_404(Asset.objects.select_related('expedition','checked_out_to__user'),code=self.kwargs['code'])
        if not self.allowed_asset(asset): raise PermissionDenied
        return asset

class AssetDetailView(AssetAccessMixin,DetailView):
    model=Asset; template_name='assets/detail.html'; context_object_name='asset'
    def get_object(self,queryset=None): return self.get_asset()
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c['qr_data']=asset_qr_data_uri(self.object,self.request)
        c['checkouts']=self.object.checkouts.select_related('taken_by__user','checked_out_by','checked_in_by').all()
        c['can_manage_assets']=has_role(self.request.user,*MANAGERS)
        return c

class AssetTagView(AssetAccessMixin,TemplateView):
    template_name='assets/tag.html'
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c['asset']=self.get_asset(); c['qr_data']=asset_qr_data_uri(c['asset'],self.request); return c

class CheckoutForm(forms.Form):
    taken_by=forms.ModelChoiceField(queryset=PersonnelProfile.objects.none(),label='Taken by')
    expedition=forms.ModelChoiceField(queryset=Expedition.objects.none())
    checkout_date=forms.DateTimeField(initial=timezone.now,widget=forms.DateTimeInput(attrs={'type':'datetime-local'},format='%Y-%m-%dT%H:%M'))
    handover_condition=forms.ChoiceField(choices=Asset.CONDITIONS,initial='ready')
    def __init__(self,*args,user,asset,**kwargs):
        super().__init__(*args,**kwargs); profile=getattr(user,'field_profile',None)
        if has_role(user,*MANAGERS):
            self.fields['taken_by'].queryset=PersonnelProfile.objects.filter(medical_cleared=True,medical_expiry__gte=timezone.localdate()).select_related('user')
            self.fields['expedition'].queryset=Expedition.objects.all()
        elif profile:
            self.fields['taken_by'].queryset=PersonnelProfile.objects.filter(pk=profile.pk)
            self.fields['expedition'].queryset=profile.expeditions.all()
        self.asset=asset
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('expedition') and cleaned.get('taken_by') and not cleaned['expedition'].team.filter(pk=cleaned['taken_by'].pk).exists():
            self.add_error('taken_by','Choose a team member assigned to this expedition.')
        return cleaned

class CheckoutView(AssetAccessMixin,FormView):
    template_name='assets/checkout.html'; form_class=CheckoutForm
    def dispatch(self,request,*args,**kwargs):
        self.asset=self.get_asset(); return super().dispatch(request,*args,**kwargs)
    def get_form_kwargs(self):
        kwargs=super().get_form_kwargs(); kwargs.update({'user':self.request.user,'asset':self.asset}); return kwargs
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c['asset']=self.asset; return c
    def form_valid(self,form):
        try:
            checkout_asset(asset_id=self.asset.pk,taken_by=form.cleaned_data['taken_by'],expedition=form.cleaned_data['expedition'],checked_out_by=self.request.user,checkout_date=form.cleaned_data['checkout_date'],handover_condition=form.cleaned_data['handover_condition'])
        except ValidationError as error:
            form.add_error(None,error); return self.form_invalid(form)
        messages.success(self.request,f'{self.asset.code} checked out successfully.')
        return super().form_valid(form)
    def get_success_url(self): return reverse('asset_detail',kwargs={'code':self.asset.code})

class CheckinForm(forms.Form):
    return_condition=forms.ChoiceField(choices=Asset.CONDITIONS)
    usage_hours_added=forms.IntegerField(min_value=0,initial=0)
    cold_exposure_hours_added=forms.IntegerField(min_value=0,initial=0)
    damage_notes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}))
class CheckinView(AssetAccessMixin,FormView):
    template_name='assets/checkin.html'; form_class=CheckinForm
    def dispatch(self,request,*args,**kwargs):
        self.asset=self.get_asset(); self.checkout=AssetCheckout.objects.filter(asset=self.asset,checkin_date__isnull=True).first()
        if not self.checkout: raise PermissionDenied('Asset has no active checkout.')
        return super().dispatch(request,*args,**kwargs)
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs); c.update({'asset':self.asset,'checkout':self.checkout}); return c
    def form_valid(self,form):
        checkin_asset(asset_id=self.asset.pk,checked_in_by=self.request.user,**form.cleaned_data)
        messages.success(self.request,f'{self.asset.code} checked in.')
        return super().form_valid(form)
    def get_success_url(self): return reverse('asset_detail',kwargs={'code':self.asset.code})
