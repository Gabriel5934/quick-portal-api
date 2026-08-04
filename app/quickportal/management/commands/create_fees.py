import random
import re
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import Acquirer, Cnae, Fee, Network


NETWORK_INSTALLMENTS = {
    "visa": range(22),
    "mastercard": range(22),
    "elo": range(22),
    "pix": (-1,),
    "acquirer": (-2,),
}


def random_percentage() -> Decimal:
    """Return 1.00%–5.00% as a decimal fraction with 0.01% precision."""
    return Decimal(random.randint(100, 500)) / Decimal(10_000)


class Command(BaseCommand):
    help = "Create or update randomized fees for an acquirer and CNAE"

    def add_arguments(self, parser):
        parser.add_argument("acquirer", help="Acquirer ID or name")
        parser.add_argument("cnae", help="CNAE code (formatting is ignored)")

    @staticmethod
    def get_acquirer(value):
        acquirer = None
        if value.isdigit():
            acquirer = Acquirer.objects.filter(pk=int(value)).first()
        if acquirer is None:
            acquirer = Acquirer.objects.filter(name__iexact=value).first()
        if acquirer is None:
            raise CommandError(f"Acquirer not found: {value}")
        return acquirer

    @staticmethod
    def get_network(name):
        network = Network.objects.filter(name__iexact=name).first()
        if network is None:
            network = Network.objects.create(name=name)
        return network

    def handle(self, *args, **options):
        acquirer = self.get_acquirer(options["acquirer"])
        cnae_code = re.sub(r"\D", "", options["cnae"])
        if not cnae_code:
            raise CommandError("CNAE must contain at least one digit.")
        try:
            cnae = Cnae.objects.get(code=cnae_code)
        except Cnae.DoesNotExist as exc:
            raise CommandError(f"CNAE not found: {cnae_code}") from exc

        created_count = 0
        updated_count = 0
        with transaction.atomic():
            for network_name, installments_values in NETWORK_INSTALLMENTS.items():
                network = self.get_network(network_name)
                for installments in installments_values:
                    _, created = Fee.objects.update_or_create(
                        acquirer=acquirer,
                        cnae=cnae,
                        network=network,
                        installments=installments,
                        defaults={"value": random_percentage()},
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} and updated {updated_count} fees "
                f"for {acquirer.name} / CNAE {cnae.code}."
            )
        )
