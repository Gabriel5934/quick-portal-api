
from django.db import models


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
