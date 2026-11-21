import csv

from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from accounts.permissions import RoleRequiredMixin, scoped_queryset
from core.scope import selected_expedition


class ReportView(RoleRequiredMixin, View):
    ACTIONS = {
        'manifest': 'report.manifest.export', 'assets': 'report.assets.export',
        'inventory': 'report.inventory.export', 'risk': 'report.risk.export',
        'transport': 'report.transport.export', 'requisitions': 'report.requisition.export',
    }

    def get_permission_action(self):
        return self.ACTIONS.get(self.kwargs.get('kind'), 'report.invalid')

    def report_rows(self, kind):
        from expeditions.models import Expedition
        from assets.models import Asset
        from inventory.models import StockItem, Requisition
        from risk.models import RiskAssessment
        from transport.models import TransportPlan

        expedition = selected_expedition(self.request)
        missions = scoped_queryset(self.request.user, Expedition.objects.prefetch_related('team__user'))
        assets = scoped_queryset(self.request.user, Asset.objects.select_related('expedition'))
        inventory = scoped_queryset(self.request.user, StockItem.objects.select_related('expedition'))
        risks = scoped_queryset(self.request.user, RiskAssessment.objects.select_related('expedition'))
        transports = scoped_queryset(self.request.user, TransportPlan.objects.select_related('expedition'))
        requisitions = scoped_queryset(self.request.user, Requisition.objects.select_related('expedition', 'requester', 'approver'))
        if expedition:
            missions = missions.filter(pk=expedition.pk)
            assets = assets.filter(expedition=expedition)
            inventory = inventory.filter(expedition=expedition)
            risks = risks.filter(expedition=expedition)
            transports = transports.filter(expedition=expedition)
            requisitions = requisitions.filter(expedition=expedition)
        if kind == 'manifest':
            return [['Expedition', 'Region', 'Status', 'Personnel']] + [[e.name, e.region, e.status, ', '.join(p.user.get_full_name() or p.user.username for p in e.team.all())] for e in missions]
        if kind == 'assets':
            return [['Code', 'Name', 'Category', 'Condition', 'Location', 'Risk']] + [[a.code, a.name, a.category, a.condition, a.location, a.maintenance_risk] for a in assets]
        if kind == 'inventory':
            return [['Name', 'Category', 'Quantity', 'Unit', 'Minimum', 'Location']] + [[i.name, i.category, i.quantity, i.unit, i.minimum, i.location] for i in inventory]
        if kind == 'risk':
            return [['Expedition', 'Score', 'Verdict', 'Assessed']] + [[r.expedition.name, r.score, r.verdict, r.assessed_at] for r in risks]
        if kind == 'transport':
            return [['Expedition', 'Vehicle', 'Route', 'Starts', 'Status', 'Approval']] + [[p.expedition.name, p.vehicle, p.route, p.starts_at, p.status, p.approval_status] for p in transports]
        if kind == 'requisitions':
            return [['Expedition', 'Requester', 'Status', 'Created', 'Approved']] + [[r.expedition.name, r.requester.get_username(), r.status, r.created_at, r.approved_at] for r in requisitions]
        return None

    def get(self, request, kind):
        rows = self.report_rows(kind)
        if rows is None:
            return HttpResponse('Unknown report', status=404)
        as_pdf = request.GET.get('format') == 'pdf'
        expedition = selected_expedition(request)
        scope = '-' + expedition.region if expedition else '-all'
        extension = 'pdf' if as_pdf else 'csv'
        response = HttpResponse(content_type='application/pdf' if as_pdf else 'text/csv')
        response['Content-Disposition'] = f'attachment; filename="polarops-{kind}{scope}-{timezone.localdate()}.{extension}"'
        if as_pdf:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            data = [[str(cell) for cell in row] for row in rows]
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#153f55')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#cbd7dc')), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f6')]), ('FONTSIZE', (0, 0), (-1, -1), 8), ('PADDING', (0, 0), (-1, -1), 6)]))
            doc = SimpleDocTemplate(response, pagesize=landscape(A4))
            title = 'PolarOps · ' + kind.title() + ' report · ' + (expedition.name if expedition else 'All expeditions')
            doc.build([Paragraph(title, getSampleStyleSheet()['Title']), Spacer(1, 12), table])
            return response
        csv.writer(response).writerows(rows)
        return response
