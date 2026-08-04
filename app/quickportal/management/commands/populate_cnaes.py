import json
import logging
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Cnae

logger = logging.getLogger(__name__)

JSON_FILE = Path(__file__).resolve().parents[3] / "load_cnaes.json"


class Command(BaseCommand):
    help = "Populate the cnaes table from load_cnaes.json (replaces existing data)"

    def add_arguments(self, parser):
        parser.add_argument("code_key", help="JSON object key containing the CNAE code")
        parser.add_argument(
            "description_key", help="JSON object key containing the CNAE description"
        )
        parser.add_argument("mcc_key", help="JSON object key containing the MCC")
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: load_cnaes.json at app root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        code_key = options["code_key"]
        description_key = options["description_key"]
        mcc_key = options["mcc_key"]
        self.stdout.write(f"Loading CNAE data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        if not isinstance(data, list):
            raise CommandError("The JSON root must be a list of objects.")

        cnaes_by_code = {}
        for item in data:
            if not isinstance(item, dict):
                logger.warning("Skipping non-object record: %s", item)
                continue

            raw_code = item.get(code_key)
            description = item.get(description_key)
            raw_mcc = item.get(mcc_key)
            code = re.sub(r"\D", "", str(raw_code)) if raw_code is not None else ""
            mcc = re.sub(r"\D", "", str(raw_mcc)) if raw_mcc is not None else ""
            if not code or not mcc or description is None or not str(description).strip():
                logger.warning("Skipping incomplete record: %s", item)
                continue

            cnaes_by_code[code] = Cnae(
                code=code,
                description=str(description).strip(),
                mcc=mcc,
            )

        with transaction.atomic():
            Cnae.objects.all().delete()
            Cnae.objects.bulk_create(cnaes_by_code.values())

        self.stdout.write(
            self.style.SUCCESS(f"Populated {len(cnaes_by_code)} CNAE records.")
        )
