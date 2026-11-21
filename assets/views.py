from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, FormView, TemplateView

from accounts.permissions import (
    ADMINISTRATOR, LOGISTICS_OFFICER, RoleRequiredMixin, can, has_role,
    scoped_queryset, user_role,
)
from assets.models import Asset, AssetCheckout
from assets.services import asset_qr_data_uri, checkin_asset, checkout_asset
from expeditions.models import Expedition
from personnel.models import PersonnelProfile


class AssetAccessMixin(RoleRequiredMixin):
    def get_asset(self):
        base = Asset.objects.select_related('expedition', 'checked_out_to__user')
        asset = get_object_or_404(base, code=self.kwargs['code'])
        action = self.get_permission_action()
        if action == 'asset.view':
            if not can(self.request.user, action, asset):
                from django.http import Http404
                raise Http404
            from core.scope import scope_model_queryset
            if not scope_model_queryset(self.request, Asset, base).filter(pk=asset.pk).exists():
                from django.http import Http404
                raise Http404
        elif not can(self.request.user, action, asset) and not can(self.request.user, 'asset.view', asset):
            raise PermissionDenied
        return asset


class AssetDetailView(AssetAccessMixin, DetailView):
    permission_action = 'asset.view'
    model = Asset
    template_name = 'assets/detail.html'
    context_object_name = 'asset'

    def get_object(self, queryset=None):
        return self.get_asset()

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['qr_data'] = asset_qr_data_uri(self.object, self.request)
        checkouts = self.object.checkouts.select_related('taken_by__user', 'checked_out_by', 'checked_in_by')
        active_checkout = checkouts.filter(checkin_date__isnull=True).first()
        if user_role(self.request.user) == 'Field Member':
            checkouts = checkouts.filter(taken_by__user=self.request.user)
        c['checkouts'] = checkouts.all()
        c['can_manage_assets'] = can(self.request.user, 'asset.manage', self.object)
        c['can_checkout_asset'] = not active_checkout and self.object.condition == 'ready' and can(self.request.user, 'asset.checkout', self.object)
        c['can_checkin_asset'] = bool(active_checkout and active_checkout.taken_by.user_id == self.request.user.pk and can(self.request.user, 'asset.checkin', active_checkout))
        c['can_force_checkin_asset'] = bool(active_checkout and can(self.request.user, 'asset.force_checkin', active_checkout))
        c['maintenance_records'] = self.object.maintenance.all() if c['can_manage_assets'] else []
        return c


class AssetTagView(AssetAccessMixin, TemplateView):
    permission_action = 'asset.manage'
    template_name = 'assets/tag.html'

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['asset'] = self.get_asset()
        c['qr_data'] = asset_qr_data_uri(c['asset'], self.request)
        return c


class CheckoutForm(forms.Form):
    taken_by = forms.ModelChoiceField(queryset=PersonnelProfile.objects.none(), label='Taken by')
    expedition = forms.ModelChoiceField(queryset=Expedition.objects.none())
    checkout_date = forms.DateTimeField(initial=timezone.now, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    handover_condition = forms.ChoiceField(choices=Asset.CONDITIONS, initial='ready')

    def __init__(self, *args, user, asset, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(user, 'field_profile', None)
        if has_role(user, ADMINISTRATOR, LOGISTICS_OFFICER):
            self.fields['taken_by'].queryset = PersonnelProfile.objects.filter(
                medical_cleared=True, medical_expiry__gte=timezone.localdate()
            ).select_related('user')
            self.fields['expedition'].queryset = Expedition.objects.all()
        elif profile:
            self.fields['taken_by'].queryset = PersonnelProfile.objects.filter(pk=profile.pk)
            self.fields['expedition'].queryset = profile.expeditions.all()
        self.asset = asset

    def clean(self):
        cleaned = super().clean()
        expedition = cleaned.get('expedition')
        person = cleaned.get('taken_by')
        if expedition and expedition.pk != self.asset.expedition_id:
            self.add_error('expedition', 'The expedition must match the asset assignment.')
        if expedition and person and not expedition.team.filter(pk=person.pk).exists():
            self.add_error('taken_by', 'Choose a team member assigned to this expedition.')
        return cleaned


class CheckoutView(AssetAccessMixin, FormView):
    permission_action = 'asset.checkout'
    template_name = 'assets/checkout.html'
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.asset = self.get_asset()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'user': self.request.user, 'asset': self.asset})
        return kwargs

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['asset'] = self.asset
        return c

    def form_valid(self, form):
        try:
            checkout_asset(
                asset_id=self.asset.pk, taken_by=form.cleaned_data['taken_by'],
                expedition=form.cleaned_data['expedition'], checked_out_by=self.request.user,
                checkout_date=form.cleaned_data['checkout_date'],
                handover_condition=form.cleaned_data['handover_condition'],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f'{self.asset.code} checked out successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('asset_detail', kwargs={'code': self.asset.code})


class CheckinForm(forms.Form):
    return_condition = forms.ChoiceField(choices=Asset.CONDITIONS)
    usage_hours_added = forms.IntegerField(min_value=0, initial=0)
    cold_exposure_hours_added = forms.IntegerField(min_value=0, initial=0)
    damage_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))
    force_checkin_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, force=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['force_checkin_reason'].required = force
        if not force:
            self.fields.pop('force_checkin_reason')


class CheckinView(AssetAccessMixin, FormView):
    permission_action = 'asset.checkin'
    template_name = 'assets/checkin.html'
    form_class = CheckinForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.asset = self.get_asset()
        self.checkout = AssetCheckout.objects.filter(asset=self.asset, checkin_date__isnull=True).select_related('taken_by__user').first()
        if not self.checkout:
            raise PermissionDenied('Asset has no active checkout.')
        self.force_checkin = self.checkout.taken_by.user_id != request.user.pk
        self.permission_action = 'asset.force_checkin' if self.force_checkin else 'asset.checkin'
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['force'] = self.force_checkin
        return kwargs

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c.update({'asset': self.asset, 'checkout': self.checkout, 'force_checkin': self.force_checkin})
        return c

    def form_valid(self, form):
        try:
            checkin_asset(
                asset_id=self.asset.pk, checked_in_by=self.request.user,
                force_checkin_reason=form.cleaned_data.get('force_checkin_reason', ''),
                **{key: value for key, value in form.cleaned_data.items() if key != 'force_checkin_reason'},
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f'{self.asset.code} checked in.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('asset_detail', kwargs={'code': self.asset.code})
