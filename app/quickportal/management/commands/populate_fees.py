import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Fee, MccFee

JSON_FILE = Path(__file__).resolve().parents[3] / "load_fees.json"

NETWORKS = {
    1: "mastercard",
    2: "visa",
    3: "elo",
    4: "na",
    5: "pix",
}

METHODS = {
    1: "Pix",
    2: "Debit",
    3: "Credit",
    4: "InstallmentsA",
    5: "InstallmentsB",
    6: "InstallmentsC",
    7: "InstallmentsD",
}


def column_name(network_idx: int, method_idx: int) -> str:
    return f"{NETWORKS[network_idx]}{METHODS[method_idx]}"


class Command(BaseCommand):
    help = "Populate fee and mcc_fee tables from load_fees.json (replaces all existing data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(JSON_FILE),
            help="Path to the JSON file (default: load_fees.json at app root)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        self.stdout.write(f"Loading fee data from {file_path}...")

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc

        valid_fields = {f.name for f in Fee._meta.get_fields() if f.name != "id" and f.name != "mccs"}

        mcc_to_values: dict[str, dict[str, Decimal]] = {}
        for mcc, matrix in data.items():
            values: dict[str, Decimal] = {}
            for method_idx, row in enumerate(matrix, start=1):
                for network_idx, value in enumerate(row, start=1):
                    if value == "" or value is None:
                        continue
                    col = column_name(network_idx, method_idx)
                    if col not in valid_fields:
                        raise CommandError(
                            f"MCC '{mcc}' has unexpected populated cell '{col}' "
                            f"(method={method_idx}, network={network_idx})"
                        )
                    values[col] = Decimal(str(value))
            mcc_to_values[mcc] = values

        unique_fees: dict[tuple, dict[str, Decimal]] = {}
        mcc_to_key: dict[str, tuple] = {}
        for mcc, values in mcc_to_values.items():
            key = tuple(sorted(values.items()))
            unique_fees.setdefault(key, values)
            mcc_to_key[mcc] = key

        with transaction.atomic():
            MccFee.objects.all().delete()
            Fee.objects.all().delete()

            key_to_fee: dict[tuple, Fee] = {}
            for key, values in unique_fees.items():
                key_to_fee[key] = Fee.objects.create(**values)

            mappings = [
                MccFee(mcc=mcc, fee=key_to_fee[key])
                for mcc, key in mcc_to_key.items()
            ]
            MccFee.objects.bulk_create(mappings)

        self.stdout.write(
            self.style.SUCCESS(
                f"Populated {len(unique_fees)} unique Fee row(s) and {len(mappings)} MccFee mapping(s)."
            )
        )
