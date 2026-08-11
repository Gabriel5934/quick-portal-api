
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


class RecurringFeePricingMode(models.TextChoices):
    FIXED = "FIXED", "Fixed"
    GOAL = "GOAL", "Goal-based"


class RecurrenceUnit(models.TextChoices):
    DAY = "DAY", "Day"
    WEEK = "WEEK", "Week"
    MONTH = "MONTH", "Month"
    YEAR = "YEAR", "Year"


class ChargeRule(models.TextChoices):
    INTERVAL = "INTERVAL", "Interval"
    WEEKDAY = "WEEKDAY", "Weekday"
    DAY_OF_MONTH = "DAY_OF_MONTH", "Day of month"
    BUSINESS_DAY_OF_MONTH = "BUSINESS_DAY_OF_MONTH", "Business day of month"
    DATE_OF_YEAR = "DATE_OF_YEAR", "Date of year"


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


class RecurringFee(models.Model):
    owner = models.ForeignKey(
        Business, on_delete=models.PROTECT, related_name="owned_recurring_fees"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    setup_value = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )
    pricing_mode = models.CharField(
        max_length=10, choices=RecurringFeePricingMode.choices
    )
    fee_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    goal_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    value_below_goal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    value_at_or_above_goal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    recurrence_unit = models.CharField(max_length=10, choices=RecurrenceUnit.choices)
    recurrence_interval = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    charge_rule = models.CharField(max_length=30, choices=ChargeRule.choices)
    charge_weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    charge_day = models.PositiveSmallIntegerField(null=True, blank=True)
    charge_month = models.PositiveSmallIntegerField(null=True, blank=True)
    business_day_ordinal = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_recurring_fees",
    )
    targets = models.ManyToManyField(
        Business,
        through="RecurringFeeTarget",
        related_name="targeted_recurring_fees",
    )

    class Meta:
        db_table = "recurring_fee"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(recurrence_interval__gte=1),
                name="recurring_fee_positive_interval",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="recurring_fee_valid_dates",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}

        if self.recurrence_interval is not None and self.recurrence_interval < 1:
            errors["recurrence_interval"] = "Use a recurrence interval of at least 1."

        if self.pricing_mode == RecurringFeePricingMode.FIXED:
            if self.fee_value is None:
                errors["fee_value"] = "This field is required for fixed pricing."
            for field in ("goal_amount", "value_below_goal", "value_at_or_above_goal"):
                if getattr(self, field) is not None:
                    errors[field] = "This field must be empty for fixed pricing."
        elif self.pricing_mode == RecurringFeePricingMode.GOAL:
            for field in ("goal_amount", "value_below_goal", "value_at_or_above_goal"):
                if getattr(self, field) is None:
                    errors[field] = "This field is required for goal-based pricing."
            if self.fee_value is not None:
                errors["fee_value"] = "This field must be empty for goal-based pricing."

        schedule_contract = {
            RecurrenceUnit.DAY: (ChargeRule.INTERVAL, ()),
            RecurrenceUnit.WEEK: (ChargeRule.WEEKDAY, ("charge_weekday",)),
            RecurrenceUnit.MONTH: (
                {ChargeRule.DAY_OF_MONTH, ChargeRule.BUSINESS_DAY_OF_MONTH},
                (),
            ),
            RecurrenceUnit.YEAR: (
                {ChargeRule.DATE_OF_YEAR, ChargeRule.BUSINESS_DAY_OF_MONTH},
                ("charge_month",),
            ),
        }
        expected_rule, base_required = schedule_contract.get(
            self.recurrence_unit, (set(), ())
        )
        valid_rules = expected_rule if isinstance(expected_rule, set) else {expected_rule}
        if self.charge_rule not in valid_rules:
            errors["charge_rule"] = "This charge rule is invalid for the recurrence unit."
        required = list(base_required)
        if self.charge_rule in {ChargeRule.DAY_OF_MONTH, ChargeRule.DATE_OF_YEAR}:
            required.append("charge_day")
        if self.charge_rule == ChargeRule.BUSINESS_DAY_OF_MONTH:
            required.append("business_day_ordinal")
        for field in required:
            if getattr(self, field) is None:
                errors[field] = "This field is required for the selected charge rule."

        if self.charge_weekday is not None and not 1 <= self.charge_weekday <= 7:
            errors["charge_weekday"] = "Use an ISO weekday from 1 to 7."
        if self.charge_day is not None and not 1 <= self.charge_day <= 31:
            errors["charge_day"] = "Use a day from 1 to 31."
        if self.charge_month is not None and not 1 <= self.charge_month <= 12:
            errors["charge_month"] = "Use a month from 1 to 12."
        if self.business_day_ordinal is not None and self.business_day_ordinal < 1:
            errors["business_day_ordinal"] = "Use a positive business-day ordinal."
        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors["end_date"] = "End date must be on or after start date."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RecurringFeeTarget(models.Model):
    recurring_fee = models.ForeignKey(
        RecurringFee, on_delete=models.CASCADE, related_name="target_links"
    )
    target = models.ForeignKey(
        Business, on_delete=models.PROTECT, related_name="recurring_fee_links"
    )
    setup_charged_at = models.DateTimeField(null=True, blank=True)
    next_charge_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recurring_fee_target"
        constraints = [
            models.UniqueConstraint(
                fields=["recurring_fee", "target"],
                name="unique_recurring_fee_target",
            )
        ]

    def __str__(self):
        return f"{self.recurring_fee_id} / {self.target_id}"


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
