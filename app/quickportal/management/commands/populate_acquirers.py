import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Acquirer

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_acquirers.json"


class Command(BaseCommand):
    help = (
        "Populate acquirer table from load_acquirers.json (replaces all existing data)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: acquirers.json at app root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        self.stdout.write(f"Loading acquirer data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        acquirers = []
        for item in data:
            name = item.get("name")
            if not name:
                logger.warning("Skipping incomplete record: %s", item)
                continue
            acquirers.append(Acquirer(name=str(name)))

        with transaction.atomic():
            Acquirer.objects.all().delete()
            Acquirer.objects.bulk_create(acquirers)

        self.stdout.write(
            self.style.SUCCESS(f"Populated {len(acquirers)} acquirer records.")
        )
