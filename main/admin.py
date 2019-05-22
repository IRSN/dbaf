from django.contrib import admin
from django.contrib.auth.models import Permission
from .models import *

# Register your models here.

admin.site.register(Device)
admin.site.register(DataFile)
admin.site.register(DataEPDN2)
admin.site.register(DataLiulin)
admin.site.register(DataHawk)
admin.site.register(IntegratedDose)
admin.site.register(FlightFile)
admin.site.register(Flight)
admin.site.register(DeviceVersion)
admin.site.register(Coefficient)
