
from django.db import models


class DocumentType(models.TextChoices):
    CPF = "CPF"
    CNPJ = "CNPJ"


class OwnStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED"


class Acquirer(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "acquirer"

    def __str__(self):
        return self.name


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


class Business(models.Model):
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    document = models.CharField(max_length=20)
    legal_name = models.CharField(max_length=200)
    trade_name = models.CharField(max_length=200)
    mcc = models.ForeignKey(CnaeMccMapping, on_delete=models.PROTECT, related_name="businesses")
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    own_status = models.CharField(max_length=20, choices=OwnStatus.choices, default=OwnStatus.NOT_STARTED)

    class Meta:
        db_table = "business"

    def __str__(self):
        return self.legal_name
