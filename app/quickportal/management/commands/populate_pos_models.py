import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Acquirer, PosModel

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_pos_models.json"


class Command(BaseCommand):
    help = "Populate pos_model table from load_pos_models.json (replaces all existing data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: pos_models.json at app root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        self.stdout.write(f"Loading POS model data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        acquirer_cache = {a.name: a for a in Acquirer.objects.all()}

        pos_models = []
        for item in data:
            model_name = item.get("model")
            acquirer_name = item.get("acquirer")

            if not model_name or not acquirer_name:
                logger.warning("Skipping incomplete record: %s", item)
                continue

            acquirer = acquirer_cache.get(acquirer_name)
            if acquirer is None:
                logger.warning(
                    "Acquirer '%s' not found — skipping record: %s",
                    acquirer_name,
                    item,
                )
                continue

            pos_models.append(PosModel(model=str(model_name), acquirer=acquirer))

        with transaction.atomic():
            PosModel.objects.all().delete()
            PosModel.objects.bulk_create(pos_models)

        self.stdout.write(
            self.style.SUCCESS(f"Populated {len(pos_models)} POS model records.")
        )
