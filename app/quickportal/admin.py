
from django.contrib import admin

from quickportal.models import Business, BusinessDetails, BusinessMembership, PosDevice

admin.site.register(Business)
admin.site.register(BusinessDetails)
admin.site.register(BusinessMembership)
admin.site.register(PosDevice)
