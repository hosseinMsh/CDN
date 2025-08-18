from django.core.management.base import BaseCommand
from core.models import AllowedExtension

DEFAULTS = [
    # Web assets
    'css', 'js', 'map', 'json', 'txt',
    # Images
    'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'ico',
    # Fonts
    'woff', 'woff2', 'ttf', 'otf', 'eot',
    # Docs/archives/media (adjust as needed)
    'pdf', 'zip', 'tar', 'gz', 'bz2', 'xz', '7z',
    'mp4', 'webm', 'mp3',
]

class Command(BaseCommand):
    help = "Seed default allowed extensions"

    def handle(self, *args, **options):
        created = 0
        for ext in DEFAULTS:
            obj, was_created = AllowedExtension.objects.get_or_create(ext=ext)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} extensions (idempotent)."))