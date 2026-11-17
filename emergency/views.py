from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404,redirect
from django.urls import reverse_lazy
from django.views.generic import FormView,View
from django.utils import timezone
from core.permissions import has_role
from emergency.forms import SOSSubmitForm
from emergency.models import SOSEvent,SOSStatusEvent
from expeditions.models import Expedition
class FieldSOSView(LoginRequiredMixin,FormView):
    template_name='emergency/sos_submit.html'; form_class=SOSSubmitForm; success_url=reverse_lazy('dashboard')
    def get_profile(self):
        profile=getattr(self.request.user,'field_profile',None)
        if not has_role(self.request.user,'Field Member') or not profile: raise PermissionDenied
        return profile
    def get_form_kwargs(self):
        kwargs=super().get_form_kwargs(); kwargs['profile']=self.get_profile(); return kwargs
    def form_valid(self,form):
        event=form.save()
        SOSStatusEvent.objects.create(event=event,to_status='open',changed_by=self.request.user,note='SOS submitted from field console.')
        messages.error(self.request,'SOS TRANSMITTED. Stay in place if safe and maintain radio contact.')
        return super().form_valid(form)
class SOSActionView(LoginRequiredMixin,View):
    http_method_names=['post']
    def post(self,request,pk,action):
        if not has_role(request.user,'Administrator','Expedition Leader'): raise PermissionDenied
        event=get_object_or_404(SOSEvent.objects.select_related('expedition'),pk=pk)
        target={'acknowledge':'acknowledged','resolve':'resolved'}.get(action)
        if not target: raise PermissionDenied
        previous=event.status
        if previous=='resolved':
            messages.warning(request,'Resolved SOS records cannot be changed.')
        elif previous==target:
            messages.info(request,'SOS already has this status.')
        else:
            event.status=target; event.save(update_fields=['status'])
            SOSStatusEvent.objects.create(event=event,from_status=previous,to_status=target,changed_by=request.user,note=f'Status {target} by {request.user.get_username()}.')
            messages.success(request,f'SOS {event.pk} marked {target}.')
        return redirect(request.META.get('HTTP_REFERER') or 'dashboard')
