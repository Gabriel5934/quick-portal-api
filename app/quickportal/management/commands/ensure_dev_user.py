import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create or update a development user with the supplied credentials"

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("password")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        created = user is None

        if created:
            user = User(username=f"user_{uuid.uuid4().hex[:12]}")

        user.email = email
        user.is_active = True
        user.set_password(options["password"])
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} development user {email}."))
