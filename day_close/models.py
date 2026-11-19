from django.conf import settings
from django.db import models


class Store(models.Model):
    store_code = models.CharField(max_length=10, primary_key=True)
    store_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.store_code} - {self.store_name}"


class Bill(models.Model):
    STATUS_CHOICES = [("C", "Completed"), ("H", "Held"), ("V", "Voided")]
    TYPE_CHOICES = [("SALE", "Sale"), ("REFUND", "Refund")]
    bill_no = models.CharField(max_length=20, primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="bills")
    bill_datetime = models.DateTimeField()
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    bill_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    customer_mobile = models.CharField(max_length=15, blank=True, default="")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=["store", "bill_datetime", "status"])]


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    sku = models.CharField(max_length=20)
    qty = models.IntegerField()
    mrp = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)


class BillTender(models.Model):
    TENDER_CHOICES = [("CASH", "Cash"), ("CARD", "Card"), ("UPI", "UPI")]
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="tenders")
    tender_type = models.CharField(max_length=10, choices=TENDER_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)


class Loyalty(models.Model):
    customer_mobile = models.CharField(max_length=15, primary_key=True)
    points = models.IntegerField(default=0)


class DayClose(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="day_closes")
    business_date = models.DateField()
    closed_by = models.CharField(max_length=50)
    closed_at = models.DateTimeField(auto_now_add=True)
    cash_total = models.DecimalField(max_digits=12, decimal_places=2)
    card_total = models.DecimalField(max_digits=12, decimal_places=2)
    upi_total = models.DecimalField(max_digits=12, decimal_places=2)
    machine_card_total = models.DecimalField(max_digits=12, decimal_places=2)
    variance = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "business_date"], name="unique_store_day_close")
        ]


class FinanceInterface(models.Model):
    GL_CHOICES = [(x, x) for x in ("CASH", "CARD", "UPI", "SALES", "GST")]
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="finance_rows")
    business_date = models.DateField()
    gl_type = models.CharField(max_length=10, choices=GL_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["store", "business_date", "gl_type"])]
