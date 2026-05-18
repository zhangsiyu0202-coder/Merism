"""Management command: migrate probe_directions → probe_blocks in all guides."""

from django.core.management.base import BaseCommand

from merism.conductor.probe_blocks import directions_to_blocks
from merism.models import InterviewGuide


class Command(BaseCommand):
    help = "Migrate probe_directions to probe_blocks in InterviewGuide sections"

    def handle(self, *args, **options):
        guides = InterviewGuide.objects.all()
        updated = 0
        for guide in guides:
            changed = False
            for section in guide.sections:
                for q in section.get("questions", []):
                    if "probe_directions" in q and "probe_blocks" not in q:
                        q["probe_blocks"] = directions_to_blocks(q.pop("probe_directions"))
                        changed = True
            if changed:
                guide.save(update_fields=["sections"])
                updated += 1
        self.stdout.write(f"Migrated {updated} guides.")
