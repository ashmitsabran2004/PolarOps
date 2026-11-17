"""Requisition state transitions and inventory fulfillment."""
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from core.permissions import has_role
from inventory.models import Requisition,StockItem,StockMovement

def _require(user,*roles):
    if not has_role(user,*roles): raise PermissionDenied

@transaction.atomic
def submit_requisition(requisition_id,user):
    """Submit a draft requisition; Logistics Officers own this transition."""
    _require(user,'Logistics Officer','Administrator')
    req=Requisition.objects.select_for_update().get(pk=requisition_id)
    if req.status!='draft': raise ValidationError('Only draft requisitions can be submitted.')
    req.status='submitted';req.submitted_at=timezone.now();req.save(update_fields=['status','submitted_at'])
    return req

@transaction.atomic
def approve_requisition(requisition_id,user):
    """Approve a submitted requisition; Leaders and Administrators may approve."""
    _require(user,'Expedition Leader','Administrator')
    req=Requisition.objects.select_for_update().get(pk=requisition_id)
    if req.status!='submitted': raise ValidationError('Only submitted requisitions can be approved.')
    req.status='approved';req.approver=user;req.approved_at=timezone.now();req.save(update_fields=['status','approver','approved_at'])
    return req

@transaction.atomic
def reject_requisition(requisition_id,user,reason=''):
    """Reject a submitted requisition with an auditable reason."""
    _require(user,'Expedition Leader','Administrator')
    req=Requisition.objects.select_for_update().get(pk=requisition_id)
    if req.status!='submitted': raise ValidationError('Only submitted requisitions can be rejected.')
    req.status='rejected';req.approver=user;req.approved_at=timezone.now();req.rejection_reason=reason;req.save(update_fields=['status','approver','approved_at','rejection_reason'])
    return req

def fulfill_requisition(requisition_id,user):
    """Create corresponding positive stock movements for every approved line item."""
    _require(user,'Logistics Officer','Administrator')
    with transaction.atomic():
        req=Requisition.objects.select_for_update().get(pk=requisition_id)
        if req.status!='approved': raise ValidationError('Only approved requisitions can be fulfilled.')
        for line in req.lines.select_for_update():
            item=line.stock_item
            if item is None:
                item=StockItem.objects.filter(expedition=req.expedition,category=line.category,name__iexact=line.item_name).first()
            if item is None:
                item=StockItem.objects.create(name=line.item_name,category=line.category,quantity=0,unit=line.unit,minimum=0,location='camp',expedition=req.expedition)
                line.stock_item=item;line.save(update_fields=['stock_item'])
            elif item.expedition_id not in (None,req.expedition_id):
                raise ValidationError(f'{item.name} belongs to another expedition.')
            StockMovement.objects.create(item=item,delta=line.quantity,reason=f'Fulfilled requisition RQ-{req.pk}',by=user)
            StockItem.objects.filter(pk=item.pk).update(quantity=F('quantity')+line.quantity)
        req.status='fulfilled';req.fulfilled_at=timezone.now();req.save(update_fields=['status','fulfilled_at'])
        return req
