import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Network

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_networks.json"


class Command(BaseCommand):
    help = "Populate network table from load_networks.json (replaces all existing data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: load_networks.json at app root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        self.stdout.write(f"Loading network data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        networks = []
        for item in data:
            name = item.get("name")
            if not name:
                logger.warning("Skipping incomplete record: %s", item)
                continue
            networks.append(Network(name=str(name)))

        with transaction.atomic():
            Network.objects.all().delete()
            Network.objects.bulk_create(networks)

        self.stdout.write(
            self.style.SUCCESS(f"Populated {len(networks)} network records.")
        )
