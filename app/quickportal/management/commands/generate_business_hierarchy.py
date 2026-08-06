import random
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quickportal.models import (
    Acquirer,
    Business,
    BusinessDetails,
    BusinessMembership,
    BusinessRole,
    BusinessType,
    Cnae,
    DocumentType,
    Plan,
)


COMPANY_PREFIXES = (
    "Aurora",
    "Bandeirantes",
    "Horizonte",
    "Ipê",
    "Mantiqueira",
    "Pioneira",
    "Serra Azul",
    "Vale Verde",
)
RESELLER_SUFFIXES = ("Pagamentos", "Soluções Financeiras", "Serviços")
STORE_SUFFIXES = ("Comércio", "Empório", "Mercado", "Varejo")
CITIES = ("Campinas", "Curitiba", "Goiânia", "Recife", "São Paulo")
BANK_CODES = ("001", "033", "077", "104", "237", "260", "341")


def cnpj_check_digits(base):
    def digit(value, weights):
        total = sum(int(number) * weight for number, weight in zip(value, weights))
        remainder = total % 11
        return "0" if remainder < 2 else str(11 - remainder)

    first = digit(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = digit(base + first, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return first + second


def random_cnpj(rng):
    base = "".join(str(rng.randrange(10)) for _ in range(8)) + "0001"
    return base + cnpj_check_digits(base)


class Command(BaseCommand):
    help = (
        "Generate a reseller, a child re-reseller, and a child store with "
        "realistic randomized data and store business details"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            type=int,
            help="Seed the random generator to make the generated data reproducible",
        )
        parser.add_argument(
            "--admin-email",
            help="Optionally grant ADMIN membership on the reseller to this user",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        admin = self.get_admin(options.get("admin_email"))
        plan = self.get_plan()

        reseller = self.create_business(rng, BusinessType.RESELLER)
        re_reseller = self.create_business(
            rng, BusinessType.RE_RESELLER, parent=reseller
        )
        store = self.create_business(
            rng,
            BusinessType.STORE,
            parent=re_reseller,
            cnae=plan.cnae,
        )
        details = self.create_details(rng, store, plan)

        if admin is not None:
            BusinessMembership.objects.create(
                user=admin,
                business=reseller,
                role=BusinessRole.ADMIN,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Generated business hierarchy:\n"
                f"  Reseller #{reseller.id}: {reseller.name}\n"
                f"  Re-reseller #{re_reseller.id}: {re_reseller.name}\n"
                f"  Store #{store.id}: {store.name}\n"
                f"  Business details #{details.id} using plan #{plan.id}"
            )
        )
        if admin is not None:
            self.stdout.write(f"Granted reseller ADMIN access to {admin.email}.")

    @staticmethod
    def get_admin(email):
        if not email:
            return None
        user = get_user_model().objects.filter(email__iexact=email.strip()).first()
        if user is None:
            raise CommandError(f"User not found: {email}")
        return user

    @staticmethod
    def get_plan():
        plan = (
            Plan.objects.select_related("acquirer", "cnae")
            .filter(acquirer__isnull=False)
            .first()
        )
        if plan is not None:
            return plan

        acquirer, _ = Acquirer.objects.get_or_create(name="Demo Acquirer")
        cnae, _ = Cnae.objects.get_or_create(
            code="4711302",
            defaults={
                "description": "Comércio varejista de mercadorias em geral",
                "mcc": "5411",
            },
        )
        return Plan.objects.create(
            name="Plano de demonstração",
            description="Plano criado para dados locais de demonstração.",
            acquirer=acquirer,
            cnae=cnae,
        )

    @staticmethod
    def create_business(rng, business_type, parent=None, cnae=None):
        prefix = rng.choice(COMPANY_PREFIXES)
        city = rng.choice(CITIES)
        suffixes = (
            STORE_SUFFIXES if business_type == BusinessType.STORE else RESELLER_SUFFIXES
        )
        type_label = {
            BusinessType.RESELLER: "Distribuidora",
            BusinessType.RE_RESELLER: "Representações",
            BusinessType.STORE: rng.choice(suffixes),
        }[business_type]
        name = f"{prefix} {type_label} {city} Ltda."
        trade_name = f"{prefix} {rng.choice(suffixes)}"
        document = random_cnpj(rng)
        while Business.objects.filter(document=document).exists():
            document = random_cnpj(rng)
        slug = re.sub(r"[^a-z0-9]+", ".", prefix.lower()).strip(".")
        ddd = rng.choice(("11", "19", "21", "31", "41", "51", "61", "81"))

        business = Business(
            type=business_type,
            parent=parent,
            document_type=DocumentType.CNPJ,
            document=document,
            name=name,
            trade_name=trade_name,
            cnae=cnae,
            email=f"contato.{slug}.{document[-6:]}@example.com",
            phone=f"{ddd}9{rng.randrange(10**8):08d}",
            landline=f"{ddd}3{rng.randrange(10**7):07d}",
        )
        business.full_clean()
        business.save()
        return business

    @staticmethod
    def create_details(rng, store, plan):
        projected_revenue = Decimal(rng.randrange(50_000, 500_001)).quantize(
            Decimal("0.01")
        )
        committed_revenue = (projected_revenue * Decimal("0.70")).quantize(
            Decimal("0.01")
        )
        details = BusinessDetails(
            business=store,
            acquirer=plan.acquirer,
            bank_code=rng.choice(BANK_CODES),
            branch=f"{rng.randrange(1, 10000):04d}",
            branch_digit=str(rng.randrange(10)),
            account_number=f"{rng.randrange(1, 10**8):08d}",
            account_digit=str(rng.randrange(10)),
            cep=f"{rng.randrange(1, 10**8):08d}",
            address_number=str(rng.randrange(1, 2000)),
            address_line2=rng.choice(
                ("Loja térrea", "Sala comercial", "Unidade principal", "")
            ),
            projected_revenue=projected_revenue,
            commited_revenue=committed_revenue,
            amount_of_terminals=rng.randrange(1, 11),
            plan=plan,
        )
        details.full_clean()
        details.save()
        return details
