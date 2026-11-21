from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.db import transaction
from django.db.models import F
from django import forms
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from accounts.permissions import FIELD_MEMBER, RoleRequiredMixin, can, scoped_queryset, user_role
from core.services import calculate_requirements
from core.views import SupplyForm
from expeditions.models import Expedition
from inventory.models import Requisition, RequisitionLine, StockItem, StockMovement
from inventory.services import approve_requisition, fulfill_requisition, reject_requisition, submit_requisition


class RequisitionCreateView(RoleRequiredMixin, FormView):
    permission_action = 'requisition.create'
    template_name = 'core/calculator.html'
    form_class = SupplyForm

    def form_valid(self, form):
        data = form.cleaned_data
        expedition = Expedition.objects.filter(region=data['region'], status='active').first() or Expedition.objects.filter(region=data['region']).first()
        if not expedition:
            form.add_error('region', 'No expedition is configured for this region yet.')
            return self.form_invalid(form)
        if not can(self.request.user, 'requisition.create', expedition):
            raise PermissionDenied
        results = calculate_requirements(data['team_size'], data['days'], data['region'], data['season'], data['buffer'])
        req = Requisition.objects.create(expedition=expedition, requester=self.request.user, team_size=data['team_size'], duration_days=data['days'], season=data['season'], safety_buffer=data['buffer'])
        for row in results:
            category = row['item'] if row['item'] in dict(RequisitionLine.CATEGORIES) else 'spares'
            RequisitionLine.objects.create(requisition=req, item_name=row['item'].title(), category=category, quantity=Decimal(str(row['quantity'])), unit=row['unit'])
        messages.success(self.request, 'Draft requisition created from the supply calculation.')
        return redirect('requisition_detail', pk=req.pk)


class RequisitionListView(RoleRequiredMixin, ListView):
    permission_action = 'requisition.view'
    template_name = 'inventory/requisition_list.html'
    context_object_name = 'requisitions'
    paginate_by = 20

    def get_queryset(self):
        qs = scoped_queryset(self.request.user, Requisition.objects.select_related('expedition', 'requester', 'approver').prefetch_related('lines'))
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '')
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(expedition__name__icontains=q) | Q(requester__username__icontains=q))
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['statuses'] = Requisition.STATUS
        c['can_create_requisition'] = can(self.request.user, 'requisition.create')
        return c


class RequisitionDetailView(RoleRequiredMixin, DetailView):
    permission_action = 'requisition.view'
    template_name = 'inventory/requisition_detail.html'
    context_object_name = 'requisition'

    def get_queryset(self):
        return scoped_queryset(self.request.user, Requisition.objects.select_related('expedition', 'requester', 'approver').prefetch_related('lines__stock_item'))

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        req = self.object
        c.update({
            'buffer_percent': int(req.safety_buffer * 100),
            'can_submit_req': can(self.request.user, 'requisition.submit', req),
            'can_approve_req': can(self.request.user, 'requisition.approve', req),
            'can_reject_req': can(self.request.user, 'requisition.reject', req),
            'can_fulfill_req': can(self.request.user, 'requisition.fulfill', req),
            'can_export_req': can(self.request.user, 'requisition.pdf', req),
        })
        return c


class RequisitionActionView(RoleRequiredMixin, View):
    http_method_names = ['post']
    ACTIONS = {'submit': 'requisition.submit', 'approve': 'requisition.approve', 'reject': 'requisition.reject', 'fulfill': 'requisition.fulfill'}

    def get_permission_action(self):
        action = self.ACTIONS.get(self.kwargs.get('action'))
        if not action:
            raise PermissionDenied
        return action

    def post(self, request, pk, action):
        req = get_object_or_404(Requisition.objects.select_related('expedition'), pk=pk)
        permission_action = self.ACTIONS.get(action)
        if not permission_action:
            raise PermissionDenied
        if not can(request.user, permission_action, req):
            raise PermissionDenied
        try:
            if action == 'submit': submit_requisition(pk, request.user)
            elif action == 'approve': approve_requisition(pk, request.user)
            elif action == 'reject': reject_requisition(pk, request.user, request.POST.get('reason', ''))
            elif action == 'fulfill': fulfill_requisition(pk, request.user)
            messages.success(request, f'Requisition RQ-{pk} updated.')
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        return redirect('requisition_detail', pk=pk)


class RequisitionPDFView(RoleRequiredMixin, View):
    permission_action = 'requisition.pdf'

    def get(self, request, pk):
        req = get_object_or_404(scoped_queryset(request.user, Requisition.objects.select_related('expedition', 'requester', 'approver').prefetch_related('lines')), pk=pk)
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="requisition-{pk}.pdf"'
        table = Table([['Item', 'Category', 'Quantity', 'Unit']] + [[line.item_name, line.get_category_display(), str(line.quantity), line.unit] for line in req.lines.all()], repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#153f55')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd7dc')), ('PADDING', (0, 0), (-1, -1), 7)]))
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(response, pagesize=A4)
        doc.build([Paragraph(f'PolarOps · Requisition RQ-{req.pk}', styles['Title']), Paragraph(f'{req.expedition.name} · {req.get_status_display()} · Requested by {req.requester}', styles['Normal']), Spacer(1, 14), table])
        return response


class SupplyConsumptionForm(forms.Form):
    item = forms.ModelChoiceField(queryset=StockItem.objects.none())
    quantity = forms.DecimalField(min_value=Decimal('0.01'), max_digits=12, decimal_places=2)
    reason = forms.CharField(max_length=180)


class SupplyConsumptionView(RoleRequiredMixin, FormView):
    permission_action = 'inventory.usage'
    template_name = 'inventory/consumption_form.html'
    form_class = SupplyConsumptionForm
    success_url = reverse_lazy('dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        profile = getattr(self.request.user, 'field_profile', None)
        missions = profile.expeditions.all() if profile and profile.expeditions.count() == 1 else Expedition.objects.none()
        form.fields['item'].queryset = StockItem.objects.filter(expedition__in=missions).select_related('expedition')
        return form

    def form_valid(self, form):
        item = form.cleaned_data['item']
        if not can(self.request.user, 'inventory.usage', item):
            raise PermissionDenied
        quantity = form.cleaned_data['quantity']
        with transaction.atomic():
            locked = StockItem.objects.select_for_update().get(pk=item.pk)
            if locked.quantity < quantity:
                form.add_error('quantity', 'Consumption cannot exceed the available stock.')
                return self.form_invalid(form)
            movement=StockMovement(item=locked, delta=-quantity, reason=form.cleaned_data['reason'], by=self.request.user, movement_type='usage')
            movement._history_user=self.request.user
            movement.save()
            StockItem.objects.filter(pk=locked.pk).update(quantity=F('quantity') - quantity)
        messages.success(self.request, 'Supply consumption recorded.')
        return super().form_valid(form)
