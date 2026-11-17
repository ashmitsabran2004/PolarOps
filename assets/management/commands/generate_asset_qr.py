from django.core.management.base import BaseCommand
from assets.models import Asset
from assets.services import asset_qr_data_uri
class Command(BaseCommand):
    help='Generate or refresh persistent QR tag images for all registered assets.'
    def add_arguments(self,parser): parser.add_argument('--force',action='store_true',help='Regenerate tags using the configured public base URL.')
    def handle(self,*args,**options):
        count=0
        for asset in Asset.objects.all():
            asset_qr_data_uri(asset,force=options['force']);count+=1
        self.stdout.write(self.style.SUCCESS(f'Generated {count} asset QR tags.'))
