import random

from django.core.management.base import BaseCommand
from django.db import transaction

from quickportal.management.commands.generate_business_hierarchy import (
    Command as GenerateHierarchyCommand,
)
from quickportal.models import BusinessType


ROOT_TYPES = {
    "reseller": BusinessType.RESELLER,
    "store": BusinessType.STORE,
}


class Command(BaseCommand):
    help = "Create a root reseller or root store with realistic randomized data"

    def add_arguments(self, parser):
        parser.add_argument(
            "type",
            choices=ROOT_TYPES,
            help="Type of root business to create",
        )
        parser.add_argument(
            "--seed",
            type=int,
            help="Seed the random generator to make the generated data reproducible",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        business = GenerateHierarchyCommand.create_business(
            random.Random(options["seed"]),
            ROOT_TYPES[options["type"]],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created root {business.get_type_display()} "
                f"#{business.id}: {business.name}"
            )
        )
