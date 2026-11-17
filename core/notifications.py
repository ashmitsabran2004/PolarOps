from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q,Exists,OuterRef
from django.shortcuts import get_object_or_404,redirect
from django.views import View
from core.models import Alert,AlertReceipt
from core.permissions import has_role

def visible_alerts(user):
    qs=Alert.objects.select_related('expedition').filter(Q(recipient=user)|Q(recipient__isnull=True)).annotate(is_read=Exists(AlertReceipt.objects.filter(alert_id=OuterRef('pk'),user=user)))
    profile=getattr(user,'field_profile',None)
    field_member=has_role(user,'Field Member') and not has_role(user,'Administrator','Expedition Leader','Logistics Officer')
    if field_member:
        qs=qs.filter(Q(expedition__in=profile.expeditions.all())|Q(recipient=user)) if profile else qs.filter(recipient=user)
    return qs
class MarkAlertReadView(View):
    http_method_names=['post']
    def post(self,request,pk):
        if not has_role(request.user,'Administrator','Expedition Leader','Logistics Officer','Field Member'): raise PermissionDenied
        alert=get_object_or_404(visible_alerts(request.user),pk=pk)
        if not alert.is_read:
            AlertReceipt.objects.get_or_create(alert=alert,user=request.user)
            messages.success(request,'Notification marked as read.')
        return redirect(request.META.get('HTTP_REFERER') or 'notifications')

from django.contrib.auth.mixins import LoginRequiredMixin,UserPassesTestMixin
from django.views.generic import ListView
from core.permissions import ROLE_GROUPS
class NotificationsView(LoginRequiredMixin,UserPassesTestMixin,ListView):
    template_name='core/notifications.html';context_object_name='notifications';paginate_by=25
    def test_func(self): return has_role(self.request.user,*ROLE_GROUPS)
    def get_queryset(self):
        qs=visible_alerts(self.request.user)
        kind=self.request.GET.get('kind'); severity=self.request.GET.get('severity'); status=self.request.GET.get('status')
        if kind: qs=qs.filter(kind=kind)
        if severity in ('1','2','3','4'): qs=qs.filter(severity=int(severity))
        if status=='unread': qs=qs.filter(is_read=False)
        if status=='read': qs=qs.filter(is_read=True)
        return qs
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs);c['kinds']=Alert.TYPES;c['severities']=Alert.SEVERITIES;return c
