from django.contrib import admin
from .models import Store, Bill, BillItem, BillTender, Loyalty, DayClose, FinanceInterface
admin.site.register([Store, Bill, BillItem, BillTender, Loyalty, DayClose, FinanceInterface])
