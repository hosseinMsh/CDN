from django.core.management.base import BaseCommand
from core.models import AllowedExtension

DEFAULTS = [
    'css','js','map','json','txt',
    'png','jpg','jpeg','webp','gif','svg','ico',
    'woff','woff2','ttf','otf','eot',
    'pdf','zip','tar','gz','bz2','xz','7z',
    'mp4','webm','mp3',
]

class Command(BaseCommand):
    help = 'Seed default allowed extensions'

    def handle(self, *args, **opts):
        created = 0
        for ext in DEFAULTS:
            _, was_created = AllowedExtension.objects.get_or_create(ext=ext)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded {created} extensions (idempotent).'))