import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import CnaeMccMapping

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_cnaemcc.json"


class Command(BaseCommand):
    help = "Populate cnae_mcc_mapping table from load_cnaemcc.json (replaces all existing data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: cnaemcc.json at repo root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        self.stdout.write(f"Loading CNAE/MCC data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        mappings = []
        for item in data:
            cod_cnae = item.get("codCnae") or item.get("cod_cnae")
            desc_cnae = item.get("descCnae") or item.get("desc_cnae")
            cod_mcc = item.get("codMcc") or item.get("cod_mcc")

            if not all([cod_cnae, desc_cnae, cod_mcc is not None]):
                logger.warning("Skipping incomplete record: %s", item)
                continue

            mappings.append(
                CnaeMccMapping(
                    cod_cnae=str(cod_cnae),
                    desc_cnae=str(desc_cnae),
                    cod_mcc=int(cod_mcc),
                )
            )

        with transaction.atomic():
            CnaeMccMapping.objects.all().delete()
            CnaeMccMapping.objects.bulk_create(mappings)

        self.stdout.write(
            self.style.SUCCESS(f"Populated {len(mappings)} CNAE/MCC records.")
        )
