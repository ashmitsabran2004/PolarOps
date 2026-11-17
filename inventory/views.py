from decimal import Decimal
from django.contrib import messages
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView,DetailView,FormView
from core.permissions import has_role
from core.views import RoleMixin,SupplyForm
from core.services import calculate_requirements
from expeditions.models import Expedition
from inventory.models import Requisition,RequisitionLine
from inventory.services import submit_requisition,approve_requisition,reject_requisition,fulfill_requisition
MANAGERS=('Administrator','Expedition Leader','Logistics Officer')
class RequisitionCreateView(RoleMixin,FormView):
    template_name='core/calculator.html';form_class=SupplyForm
    def test_func(self): return has_role(self.request.user,'Logistics Officer','Administrator')
    def form_valid(self,form):
        data=form.cleaned_data; expedition=Expedition.objects.filter(region=data['region'],status='active').first() or Expedition.objects.filter(region=data['region']).first()
        if not expedition:
            form.add_error('region','No expedition is configured for this region yet.')
            return self.form_invalid(form)
        results=calculate_requirements(data['team_size'],data['days'],data['region'],data['season'],data['buffer'])
        req=Requisition.objects.create(expedition=expedition,requester=self.request.user,team_size=data['team_size'],duration_days=data['days'],season=data['season'],safety_buffer=data['buffer'])
        for row in results:
            category=row['item'] if row['item'] in dict(RequisitionLine.CATEGORIES) else 'spares'
            RequisitionLine.objects.create(requisition=req,item_name=row['item'].title(),category=category,quantity=Decimal(str(row['quantity'])),unit=row['unit'])
        messages.success(self.request,'Draft requisition created from the supply calculation.')
        return redirect('requisition_detail',pk=req.pk)
class RequisitionListView(RoleMixin,ListView):
    allowed_roles=MANAGERS
    template_name='inventory/requisition_list.html';context_object_name='requisitions';paginate_by=20
    def get_queryset(self):
        qs=Requisition.objects.select_related('expedition','requester','approver').prefetch_related('lines')
        q=self.request.GET.get('q','').strip();status=self.request.GET.get('status','')
        if q:
            from django.db.models import Q
            qs=qs.filter(Q(expedition__name__icontains=q)|Q(requester__username__icontains=q))
        if status: qs=qs.filter(status=status)
        return qs
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs);c['statuses']=Requisition.STATUS;return c
class RequisitionDetailView(RoleMixin,DetailView):
    allowed_roles=MANAGERS
    template_name='inventory/requisition_detail.html';context_object_name='requisition';queryset=Requisition.objects.select_related('expedition','requester','approver').prefetch_related('lines__stock_item')
    def get_context_data(self,**kwargs):
        c=super().get_context_data(**kwargs)
        c.update({'buffer_percent':int(self.object.safety_buffer*100),'can_submit_req':has_role(self.request.user,'Logistics Officer','Administrator'),'can_approve_req':has_role(self.request.user,'Expedition Leader','Administrator'),'can_fulfill_req':has_role(self.request.user,'Logistics Officer','Administrator')})
        return c
class RequisitionActionView(RoleMixin,View):
    allowed_roles=MANAGERS
    http_method_names=['post']
    def post(self,request,pk,action):
        req=get_object_or_404(Requisition,pk=pk)
        try:
            if action=='submit': submit_requisition(pk,request.user)
            elif action=='approve': approve_requisition(pk,request.user)
            elif action=='reject': reject_requisition(pk,request.user,request.POST.get('reason',''))
            elif action=='fulfill': fulfill_requisition(pk,request.user)
            else: raise PermissionDenied
            messages.success(request,f'Requisition RQ-{pk} updated.')
        except (PermissionDenied,ValidationError) as error:
            if isinstance(error,PermissionDenied): raise
            messages.error(request,' '.join(error.messages))
        return redirect('requisition_detail',pk=pk)
class RequisitionPDFView(RoleMixin,View):
    allowed_roles=MANAGERS
    def get(self,request,pk):
        req=get_object_or_404(Requisition.objects.select_related('expedition','requester','approver').prefetch_related('lines'),pk=pk)
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        response=HttpResponse(content_type='application/pdf');response['Content-Disposition']=f'attachment; filename=\"requisition-{pk}.pdf\"'
        table=Table([['Item','Category','Quantity','Unit']]+[[l.item_name,l.get_category_display(),str(l.quantity),l.unit] for l in req.lines.all()],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#153f55')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#cbd7dc')),('PADDING',(0,0),(-1,-1),7)]))
        styles=getSampleStyleSheet();doc=SimpleDocTemplate(response,pagesize=A4)
        doc.build([Paragraph(f'PolarOps · Requisition RQ-{req.pk}',styles['Title']),Paragraph(f'{req.expedition.name} · {req.get_status_display()} · Requested by {req.requester}',styles['Normal']),Spacer(1,14),table])
        return response
