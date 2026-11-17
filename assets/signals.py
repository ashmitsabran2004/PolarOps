from django.db.models.signals import post_save
from django.dispatch import receiver
from assets.models import Asset
from assets.services import asset_qr_data_uri

@receiver(post_save,sender=Asset)
def ensure_asset_qr(sender,instance,created,**kwargs):
    """Persist a QR tag whenever an asset is created without one."""
    if not instance.qr_image:
        asset_qr_data_uri(instance)
