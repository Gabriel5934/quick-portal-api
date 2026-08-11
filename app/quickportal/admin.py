
from django.contrib import admin

from quickportal.models import (
    Business,
    BusinessDetails,
    BusinessMembership,
    PosDevice,
    RecurringFee,
    RecurringFeeTarget,
)

admin.site.register(Business)
admin.site.register(BusinessDetails)
admin.site.register(BusinessMembership)
admin.site.register(PosDevice)
admin.site.register(RecurringFee)
admin.site.register(RecurringFeeTarget)
