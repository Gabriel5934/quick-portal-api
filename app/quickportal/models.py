
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.core.validators import MinValueValidator, RegexValidator


digits_only = RegexValidator(r"^\d+$", "This field must contain only digits.")


class DocumentType(models.TextChoices):
    CPF = "CPF"
    CNPJ = "CNPJ"


class Status(models.TextChoices):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"


class BusinessType(models.TextChoices):
    RESELLER = "RESELLER", "Reseller"
    RE_RESELLER = "RE_RESELLER", "Re-reseller"
    STORE = "STORE", "Store"


class BusinessRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    MANAGER = "MANAGER", "Manager"
    VIEWER = "VIEWER", "Viewer"


class Acquirer(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "acquirer"

    def __str__(self):
        return self.name


class Network(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Enter a valid hex color.")],
    )

    class Meta:
        db_table = "network"

    def __str__(self):
        return self.name


class PosModel(models.Model):
    model = models.CharField(max_length=100)
    acquirer = models.ForeignKey(Acquirer, on_delete=models.CASCADE, related_name="pos_models")

    class Meta:
        db_table = "pos_model"

    def __str__(self):
        return self.model


class Cnae(models.Model):
    code = models.CharField(max_length=20, unique=True, validators=[digits_only])
    description = models.TextField()
    mcc = models.CharField(max_length=20, validators=[digits_only])

    class Meta:
        db_table = "cnaes"

    def __str__(self):
        return f"{self.code} - {self.description}"


class Fee(models.Model):
    acquirer = models.ForeignKey(Acquirer, on_delete=models.CASCADE, related_name="fees")
    cnae = models.ForeignKey(Cnae, on_delete=models.PROTECT, related_name="fees")
    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="fees")
    installments = models.IntegerField()
    value = models.DecimalField(max_digits=20, decimal_places=16)

    class Meta:
        db_table = "fee"
        constraints = [
            models.UniqueConstraint(
                fields=["acquirer", "cnae", "network", "installments"],
                name="unique_fee_dimensions",
            )
        ]

    def __str__(self):
        return f"{self.acquirer} / {self.cnae} / {self.network} / {self.installments}"


class Plan(models.Model):
    acquirer = models.ForeignKey(
        Acquirer,
        on_delete=models.PROTECT,
        related_name="plans",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    split = models.BooleanField(default=False)
    anticipation = models.BooleanField(default=False)
    anticipation_fee = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    cnae = models.ForeignKey(
        Cnae,
        on_delete=models.PROTECT,
        related_name="plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plan"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class PlanFee(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="fees")
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name="plan_fees")
    value = models.DecimalField(max_digits=20, decimal_places=16)

    class Meta:
        db_table = "plan_fee"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "fee"], name="unique_plan_fee"
            )
        ]

    def __str__(self):
        return f"{self.plan_id} / Fee #{self.fee_id}"


class Business(models.Model):
    type = models.CharField(max_length=20, choices=BusinessType.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    document = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, blank=True)
    cnae = models.ForeignKey(
        Cnae,
        on_delete=models.PROTECT,
        related_name="businesses",
        null=True,
        blank=True,
    )
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    landline = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)

    class Meta:
        db_table = "business"
        constraints = [
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=F("id")),
                name="business_parent_not_self",
            )
        ]

    def clean(self):
        super().clean()
        if self.parent_id == self.pk and self.pk is not None:
            raise ValidationError({"parent": "A business cannot be its own parent."})
        if self.type == BusinessType.RESELLER and self.parent_id is not None:
            raise ValidationError({"parent": "A reseller must be a root business."})
        if self.type == BusinessType.RE_RESELLER:
            if self.parent_id is None or self.parent.type != BusinessType.RESELLER:
                raise ValidationError(
                    {"parent": "A re-reseller must belong to a reseller."}
                )
        if (
            self.type == BusinessType.STORE
            and self.parent_id is not None
            and self.parent.type
            not in {BusinessType.RESELLER, BusinessType.RE_RESELLER}
        ):
            raise ValidationError(
                {"parent": "A store may only belong to a reseller or re-reseller."}
            )
        if self.pk is not None:
            allowed_children = {
                BusinessType.RESELLER: {
                    BusinessType.RE_RESELLER,
                    BusinessType.STORE,
                },
                BusinessType.RE_RESELLER: {BusinessType.STORE},
                BusinessType.STORE: set(),
            }.get(self.type, set())
            if self.children.exclude(type__in=allowed_children).exists():
                raise ValidationError(
                    {"type": "This type is incompatible with existing children."}
                )

    def __str__(self):
        return self.name


class BusinessMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=BusinessRole.choices)

    class Meta:
        db_table = "business_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business"],
                name="unique_user_business_membership",
            )
        ]

    def __str__(self):
        return f"{self.user_id} / {self.business_id} / {self.role}"


class BusinessDetails(models.Model):
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="details"
    )
    acquirer = models.ForeignKey(
        Acquirer,
        on_delete=models.PROTECT,
        related_name="business_details",
        null=True,
        blank=True,
    )
    bank_code = models.CharField(max_length=8, validators=[digits_only])
    branch = models.CharField(max_length=20, validators=[digits_only])
    branch_digit = models.CharField(max_length=5, validators=[digits_only])
    account_number = models.CharField(max_length=30, validators=[digits_only])
    account_digit = models.CharField(max_length=5, validators=[digits_only])
    cep = models.CharField(max_length=8, validators=[digits_only])
    address_number = models.CharField(max_length=20, validators=[digits_only])
    address_line2 = models.CharField(max_length=255, blank=True)
    projected_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    commited_revenue = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    amount_of_terminals = models.PositiveIntegerField()
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="business_details")

    class Meta:
        db_table = "business_details"

    def __str__(self):
        return f"Details for {self.business}"


class PosDevice(models.Model):
    model = models.ForeignKey(PosModel, on_delete=models.PROTECT, related_name="devices")
    serial = models.CharField(max_length=100, validators=[digits_only])
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="pos_devices"
    )

    class Meta:
        db_table = "pos_device"
        constraints = [
            models.UniqueConstraint(fields=["model", "serial"], name="unique_pos_device_serial")
        ]

    def __str__(self):
        return self.serial
