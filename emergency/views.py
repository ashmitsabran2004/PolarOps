from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from accounts.permissions import RoleRequiredMixin, can
from emergency.forms import SOSSubmitForm
from emergency.models import SOSEvent, SOSStatusEvent


class FieldSOSView(RoleRequiredMixin, FormView):
    permission_action = 'sos.submit'
    template_name = 'emergency/sos_submit.html'
    form_class = SOSSubmitForm
    success_url = reverse_lazy('dashboard')

    def get_profile(self):
        profile = getattr(self.request.user, 'field_profile', None)
        if not profile or profile.expeditions.count() != 1:
            raise PermissionDenied('A Field Member must have exactly one assigned expedition.')
        return profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['profile'] = self.get_profile()
        return kwargs

    def form_valid(self, form):
        event = form.save()
        SOSStatusEvent.objects.create(event=event, to_status='open', changed_by=self.request.user, note='SOS submitted from field console.')
        messages.error(self.request, 'SOS TRANSMITTED. Stay in place if safe and maintain radio contact.')
        return super().form_valid(form)


class SOSActionView(RoleRequiredMixin, View):
    permission_action = 'sos.update'
    http_method_names = ['post']

    def post(self, request, pk, action):
        event = get_object_or_404(SOSEvent.objects.select_related('expedition'), pk=pk)
        if not can(request.user, 'sos.update', event):
            raise PermissionDenied
        target = {'acknowledge': 'acknowledged', 'resolve': 'resolved'}.get(action)
        note = request.POST.get('note', '').strip()
        if not target or not note:
            raise PermissionDenied('Choose a valid action and enter a status note.')
        previous = event.status
        if previous == 'resolved':
            messages.warning(request, 'Resolved SOS records cannot be changed.')
        elif previous != target:
            event.status = target
            event._history_user = request.user
            event.save(update_fields=['status'])
            SOSStatusEvent.objects.create(event=event, from_status=previous, to_status=target, changed_by=request.user, note=note)
            messages.success(request, f'SOS {event.pk} marked {target}.')
        else:
            messages.info(request, 'SOS already has this status.')
        return redirect(request.META.get('HTTP_REFERER') or 'dashboard')
