from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View

from accounts.permissions import RoleRequiredMixin, can
from transport.models import TransportPlan


class TransportApprovalView(RoleRequiredMixin, View):
    permission_action = 'transport.approve'
    http_method_names = ['post']

    def post(self, request, pk, action):
        plan = get_object_or_404(TransportPlan.objects.select_related('expedition'), pk=pk)
        if not can(request.user, 'transport.approve', plan):
            raise PermissionDenied
        if action not in ('approve', 'reject'):
            raise PermissionDenied
        if plan.approval_status != 'pending':
            messages.warning(request, 'Only pending transport plans can be approved or rejected.')
            return redirect('resource_detail', resource='transport', pk=plan.pk)
        note = request.POST.get('note', '').strip()
        if action == 'reject' and not note:
            raise ValidationError('A rejection reason is required.')
        plan.approval_status = 'approved' if action == 'approve' else 'rejected'
        plan.approved_by = request.user
        plan.approved_at = timezone.now()
        plan.approval_note = note
        if action == 'reject':
            plan.status = 'cancelled'
        plan._history_user = request.user
        plan.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'approval_note', 'status'])
        messages.success(request, f'Transport plan {plan.pk} {plan.approval_status}.')
        return redirect('resource_detail', resource='transport', pk=plan.pk)
