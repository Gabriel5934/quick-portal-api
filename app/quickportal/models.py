
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator


digits_only = RegexValidator(r"^\d+$", "This field must contain only digits.")


class DocumentType(models.TextChoices):
    CPF = "CPF"
    CNPJ = "CNPJ"


class Status(models.TextChoices):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"


class Acquirer(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "acquirer"

    def __str__(self):
        return self.name


class Network(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "network"

    def __str__(self):
        return self.name


class Client(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client",
    )

    class Meta:
        db_table = "client"

    def __str__(self):
        return str(self.user)


class PosModel(models.Model):
    model = models.CharField(max_length=100)
    acquirer = models.ForeignKey(Acquirer, on_delete=models.CASCADE, related_name="pos_models")

    class Meta:
        db_table = "pos_model"

    def __str__(self):
        return self.model


class CnaeMccMapping(models.Model):
    cod_cnae = models.CharField(max_length=20)
    desc_cnae = models.TextField()
    cod_mcc = models.IntegerField()
    id = models.BigAutoField(primary_key=True)

    class Meta:
        db_table = "cnae_mcc_mapping"

    def __str__(self):
        return f"{self.cod_cnae} → MCC {self.cod_mcc}"


class Fee(models.Model):
    acquirer = models.ForeignKey(Acquirer, on_delete=models.CASCADE, related_name="fees")
    cnae = models.CharField(max_length=20, validators=[digits_only])
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


class MccFee(models.Model):
    mcc = models.CharField(max_length=200, unique=True)
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name="mccs")

    class Meta:
        db_table = "mcc_fee"

    def __str__(self):
        return f"{self.mcc} → Fee #{self.fee_id}"


class Plan(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    split = models.BooleanField(default=False)
    anticipation = models.BooleanField(default=False)
    anticipation_fee = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    cnae = models.CharField(max_length=20, validators=[digits_only])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plan"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class PlanFee(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="fees")
    fee = models.OneToOneField(Fee, on_delete=models.CASCADE, related_name="plan_fee")
    value = models.DecimalField(max_digits=20, decimal_places=16)

    class Meta:
        db_table = "plan_fee"

    def __str__(self):
        return f"{self.plan_id} / Fee #{self.fee_id}"


class Business(models.Model):
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    document = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200, blank=True)
    cod_cnae = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    landline = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)

    class Meta:
        db_table = "business"

    def __str__(self):
        return self.name


class BusinessDetails(models.Model):
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="details"
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
