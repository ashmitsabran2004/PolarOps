"""Asset custody workflow and QR tag generation."""
import base64
from io import BytesIO
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from assets.models import Asset,AssetCheckout

def checkout_asset(*,asset_id,taken_by,expedition,checked_out_by,checkout_date,handover_condition):
    """Atomically assign a ready asset and record its custody handover."""
    with transaction.atomic():
        asset=Asset.objects.select_for_update().get(pk=asset_id)
        if asset.condition!='ready': raise ValidationError('This asset is not ready for checkout; its condition is '+asset.get_condition_display()+'.')
        if handover_condition!='ready': raise ValidationError('An asset can only be handed over in ready condition.')
        if asset.checked_out_to_id or AssetCheckout.objects.filter(asset=asset,checkin_date__isnull=True).exists():
            raise ValidationError('This asset is already checked out.')
        if not taken_by.assignment_eligible(): raise ValidationError('The recipient has expired or missing medical clearance.')
        if not expedition.team.filter(pk=taken_by.pk).exists(): raise ValidationError('The recipient must be assigned to the selected expedition.')
        record=AssetCheckout.objects.create(asset=asset,taken_by=taken_by,expedition=expedition,checked_out_by=checked_out_by,checkout_date=checkout_date,handover_condition=handover_condition)
        asset.checked_out_to=taken_by; asset.expedition=expedition; asset.save(update_fields=['checked_out_to','expedition'])
        return record

def checkin_asset(*,asset_id,checked_in_by,return_condition,usage_hours_added,cold_exposure_hours_added,damage_notes=''):
    """Close an active custody record and add field usage to the asset totals."""
    with transaction.atomic():
        asset=Asset.objects.select_for_update().get(pk=asset_id)
        record=AssetCheckout.objects.select_for_update().filter(asset=asset,checkin_date__isnull=True).order_by('-checkout_date').first()
        if not record: raise ValidationError('This asset has no active checkout.')
        record.checked_in_by=checked_in_by; record.checkin_date=timezone.now(); record.return_condition=return_condition
        record.usage_hours_added=usage_hours_added; record.cold_exposure_hours_added=cold_exposure_hours_added; record.damage_notes=damage_notes; record.save()
        asset.usage_hours+=usage_hours_added; asset.cold_exposure_hours+=cold_exposure_hours_added; asset.condition=return_condition; asset.checked_out_to=None
        if return_condition!='ready': asset.condition='service' if return_condition=='service' else return_condition
        asset.save(update_fields=['usage_hours','cold_exposure_hours','condition','checked_out_to'])
        return record

def asset_qr_data_uri(asset,request=None,force=False):
    """Persist and return a scannable PNG targeting the asset detail URL."""
    import qrcode
    from django.conf import settings
    from django.core.files.base import ContentFile
    from qrcode.constants import ERROR_CORRECT_M
    path=reverse('asset_detail',kwargs={'code':asset.code})
    url=request.build_absolute_uri(path) if request is not None else settings.POLAROPS_PUBLIC_URL+path
    if asset.qr_image and not force:
        with asset.qr_image.open('rb') as existing: return 'data:image/png;base64,'+base64.b64encode(existing.read()).decode('ascii')
    image=qrcode.QRCode(version=None,error_correction=ERROR_CORRECT_M,box_size=7,border=3)
    image.add_data(url); image.make(fit=True)
    output=BytesIO(); image.make_image(fill_color='#102b39',back_color='white').save(output,format='PNG')
    if force and asset.qr_image: asset.qr_image.delete(save=False)
    asset.qr_image.save(f'{asset.code}.png',ContentFile(output.getvalue()),save=True)
    return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode('ascii')
