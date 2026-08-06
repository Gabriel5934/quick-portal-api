import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.management.commands.generate_business_hierarchy import (
    Command as GenerateHierarchyCommand,
)
from quickportal.models import Business, BusinessType


class Command(BaseCommand):
    help = (
        "Create a root reseller, or create a valid child for the supplied business"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "business_id",
            nargs="?",
            type=int,
            help="Optional parent business ID",
        )
        parser.add_argument(
            "--store",
            action="store_true",
            help="Create a store directly under a reseller instead of a re-reseller",
        )
        parser.add_argument(
            "--seed",
            type=int,
            help="Seed the random generator to make the generated data reproducible",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        parent = self.get_parent(options["business_id"])
        business_type = self.get_business_type(parent, options["store"])
        business = GenerateHierarchyCommand.create_business(
            random.Random(options["seed"]),
            business_type,
            parent=parent,
        )

        parent_text = f" under business #{parent.id}" if parent else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {business.get_type_display()} #{business.id}"
                f"{parent_text}: {business.name}"
            )
        )

    @staticmethod
    def get_parent(business_id):
        if business_id is None:
            return None
        try:
            return Business.objects.get(pk=business_id)
        except Business.DoesNotExist as exc:
            raise CommandError(f"Business not found: {business_id}") from exc

    @staticmethod
    def get_business_type(parent, create_store):
        if parent is None:
            if create_store:
                raise CommandError("--store requires a reseller business ID.")
            return BusinessType.RESELLER
        if parent.type == BusinessType.RESELLER:
            return BusinessType.STORE if create_store else BusinessType.RE_RESELLER
        if parent.type == BusinessType.RE_RESELLER:
            return BusinessType.STORE
        raise CommandError("A store cannot have child businesses.")
