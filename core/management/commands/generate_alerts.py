from django.core.management.base import BaseCommand
from core.services import refresh_alerts
class Command(BaseCommand):
 help='Generate in-app PolarOps operational alerts.'
 def handle(self,*args,**kwargs): self.stdout.write(f'Created {len(refresh_alerts())} alerts.')
