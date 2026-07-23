
from django.contrib import admin

from quickportal.models import BusinessDetails, CnaeMccMapping, PosDevice

admin.site.register(CnaeMccMapping)
admin.site.register(BusinessDetails)
admin.site.register(PosDevice)
