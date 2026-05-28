
from django.db import models


class CnaeMccMapping(models.Model):
    cod_cnae = models.CharField(max_length=20)
    desc_cnae = models.TextField()
    cod_mcc = models.IntegerField()
    id = models.BigAutoField(primary_key=True)

    class Meta:
        db_table = "cnae_mcc_mapping"

    def __str__(self):
        return f"{self.cod_cnae} → MCC {self.cod_mcc}"
