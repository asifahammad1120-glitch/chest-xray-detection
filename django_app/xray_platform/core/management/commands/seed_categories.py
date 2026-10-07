from django.core.management.base import BaseCommand
from core.models import AbnormalityCategory

CATEGORIES = [
    "Aortic enlargement", "Atelectasis", "Calcification", "Cardiomegaly",
    "Consolidation", "ILD", "Infiltration", "Lung Opacity", "Nodule-Mass",
    "Other lesion", "Pleural effusion", "Pleural thickening", "Pneumothorax",
    "Pulmonary fibrosis", "Normal",
]

class Command(BaseCommand):
    help = "Seeds the AbnormalityCategory table with the 15 trained classes"

    def handle(self, *args, **options):
        created_count = 0
        for name in CATEGORIES:
            obj, created = AbnormalityCategory.objects.get_or_create(name=name)
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} new categories created, {len(CATEGORIES)} total expected."
        ))