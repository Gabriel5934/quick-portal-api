import json
import logging
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Network

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_networks.json"


class Command(BaseCommand):
    help = "Create or update networks from load_networks.json"

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

        networks = {}
        for item in data:
            name = item.get("name")
            if not name:
                logger.warning("Skipping incomplete record: %s", item)
                continue
            name = str(name).strip()
            color = str(item.get("color") or "").strip()
            if color and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise CommandError(f"Invalid color for network {name}: {color}")
            networks[name.casefold()] = (name, color)

        with transaction.atomic():
            for name, color in networks.values():
                Network.objects.update_or_create(
                    name__iexact=name,
                    defaults={"name": name, "color": color},
                )

        self.stdout.write(
            self.style.SUCCESS(f"Loaded {len(networks)} network records.")
        )
