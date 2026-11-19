from datetime import date, datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from day_close.models import Store, Bill, BillItem, BillTender, Loyalty, DayClose, FinanceInterface
from day_close.services import close_day, DayCloseError


class DayCloseTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(store_code="S01", store_name="Test Store")
        self.user = get_user_model().objects.create_user(username="manager", password="pass")
        self.day = date(2026, 11, 10)

    def bill(self, no, at="10:00:00", status="C", kind="SALE", mobile="", net="100.00"):
        dt = timezone.make_aware(datetime.strptime(f"2026-11-10 {at}", "%Y-%m-%d %H:%M:%S"))
        return Bill.objects.create(
            bill_no=no, store=self.store, bill_datetime=dt, status=status,
            bill_type=kind, customer_mobile=mobile, net_amount=Decimal(net),
        )

    def test_full_day_includes_late_transaction_and_excludes_next_day(self):
        late = self.bill("LATE", "23:59:59", net="100")
        nxt = Bill.objects.create(
            bill_no="NEXT", store=self.store,
            bill_datetime=timezone.make_aware(datetime(2026, 11, 11, 0, 0)),
            status="C", bill_type="SALE", net_amount=Decimal("500"),
        )
        BillTender.objects.create(bill=late, tender_type="CASH", amount=Decimal("100"))
        BillTender.objects.create(bill=nxt, tender_type="CASH", amount=Decimal("500"))
        result = close_day("S01", self.day, Decimal("0"), "manager")
        self.assertEqual(result["tender_totals"]["CASH"], Decimal("100.00"))

    def test_held_bill_blocks_close(self):
        self.bill("HELD", status="H")
        with self.assertRaisesMessage(DayCloseError, "held bills"):
            close_day("S01", self.day, Decimal("0"), "manager")
        self.assertEqual(DayClose.objects.count(), 0)

    def test_negative_card_variance_over_tolerance_is_rejected(self):
        b = self.bill("CARD")
        BillTender.objects.create(bill=b, tender_type="CARD", amount=Decimal("100"))
        with self.assertRaisesMessage(DayCloseError, "Card variance"):
            close_day("S01", self.day, Decimal("102"), "manager")

    def test_positive_card_variance_over_tolerance_is_rejected(self):
        b = self.bill("CARD")
        BillTender.objects.create(bill=b, tender_type="CARD", amount=Decimal("103"))
        with self.assertRaises(DayCloseError):
            close_day("S01", self.day, Decimal("100"), "manager")

    def test_exact_one_rupee_variance_is_allowed(self):
        b = self.bill("CARD")
        BillTender.objects.create(bill=b, tender_type="CARD", amount=Decimal("101"))
        result = close_day("S01", self.day, Decimal("100"), "manager")
        self.assertEqual(result["variance"], Decimal("1.00"))

    def test_loyalty_floor_cap_and_refund_exclusion(self):
        Loyalty.objects.create(customer_mobile="9000000001", points=10)
        sale = self.bill("SALE", mobile="9000000001", net="60000")
        refund = self.bill("REFUND", kind="REFUND", mobile="9000000001", net="5000")
        result = close_day("S01", self.day, Decimal("0"), "manager")
        self.assertEqual(Loyalty.objects.get(customer_mobile="9000000001").points, 510)
        self.assertEqual(result["loyalty_points_awarded"]["9000000001"], 500)

    def test_duplicate_close_is_rejected(self):
        close_day("S01", self.day, Decimal("0"), "manager")
        with self.assertRaisesMessage(DayCloseError, "already been closed"):
            close_day("S01", self.day, Decimal("0"), "manager")
        self.assertEqual(FinanceInterface.objects.count(), 5)

    def test_finance_rows_are_created(self):
        result = close_day("S01", self.day, Decimal("0"), "manager")
        self.assertEqual(FinanceInterface.objects.count(), 5)
        self.assertEqual(result["finance_rows"]["SALES"], Decimal("0.00"))

    def test_api_requires_authentication(self):
        response = self.client.post(
            "/api/day-close/",
            data={
                "store_code": "S01",
                "business_date": "2026-11-10",
                "machine_card_total": "44797.00",
            },
            content_type="application/json",
        )

        self.assertIn(response.status_code, [401, 403])

    def test_api_closes_day_for_authenticated_user(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post("/api/day-close/", {
            "store_code": "S01", "business_date": "2026-11-10",
            "machine_card_total": "0.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Day closed successfully")
