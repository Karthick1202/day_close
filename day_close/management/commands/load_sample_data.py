import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from day_close.models import Store, Bill, BillItem, BillTender, Loyalty


class Command(BaseCommand):
    help = "Load the supplied AllPOS CSV sample data."
    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default="sample_data")

    @transaction.atomic
    def handle(self, *args, **opts):
        folder = Path(opts["data_dir"])
        required = ["stores.csv", "bills.csv", "bill_items.csv", "bill_tenders.csv", "loyalty.csv"]
        missing = [n for n in required if not (folder / n).exists()]
        if missing:
            raise CommandError(f"Missing CSV files in {folder}: {', '.join(missing)}")

        with (folder / "stores.csv").open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                Store.objects.update_or_create(
                    store_code=r["store_code"], defaults={"store_name": r["store_name"]}
                )

        with (folder / "bills.csv").open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                store = Store.objects.get(store_code=r["store_code"])
                Bill.objects.update_or_create(
                    bill_no=r["bill_no"],
                    defaults={
                        "store": store,
                        "bill_datetime": datetime.strptime(r["bill_datetime"], "%Y-%m-%d %H:%M:%S"),
                        "status": r["status"], "bill_type": r["bill_type"],
                        "customer_mobile": r["customer_mobile"],
                        "net_amount": Decimal(r["net_amount"]),
                    },
                )

        with (folder / "bill_items.csv").open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                bill = Bill.objects.get(bill_no=r["bill_no"])
                BillItem.objects.update_or_create(
                    bill=bill, sku=r["sku"],
                    defaults={"qty": int(r["qty"]), "mrp": Decimal(r["mrp"]),
                              "discount": Decimal(r["discount"]), "gst_rate": Decimal(r["gst_rate"])},
                )

        with (folder / "bill_tenders.csv").open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                bill = Bill.objects.get(bill_no=r["bill_no"])
                BillTender.objects.get_or_create(
                    bill=bill, tender_type=r["tender_type"],
                    defaults={"amount": Decimal(r["amount"])},
                )

        with (folder / "loyalty.csv").open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                Loyalty.objects.update_or_create(
                    customer_mobile=r["customer_mobile"],
                    defaults={"points": int(r["points"])},
                )
        self.stdout.write(self.style.SUCCESS("Sample data loaded."))
