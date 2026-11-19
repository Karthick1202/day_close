from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import (
    Bill, BillTender, DayClose, FinanceInterface, Loyalty, Store,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
CARD_TOLERANCE = Decimal("1.00")


class DayCloseError(Exception):
    """A business-rule failure while closing a store day."""


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def close_day(store_code, business_date, machine_card_total, user):
    """
    Atomically close one store/business date.
    business_date must be a datetime.date; machine_card_total is Decimal-compatible.
    Returns a dict containing the close record, totals, loyalty awards and finance rows.
    """
    machine_card_total = money(machine_card_total)
    # print(machine_card_total)
    if machine_card_total < ZERO or 0:
        raise DayCloseError("Machine card total cannot be negative.")
    if not user:
        raise DayCloseError("A closing user is required.")

    start = timezone.make_aware(datetime.combine(business_date, time.min))
    end = timezone.make_aware(datetime.combine(business_date + timedelta(days=1), time.min))

    with transaction.atomic():
        try:
            # Locking the parent store serializes concurrent close attempts on databases
            store = Store.objects.select_for_update().get(store_code=store_code)
        except Store.DoesNotExist:
            raise DayCloseError(f"Unknown store: {store_code}")

        if DayClose.objects.filter(store=store, business_date=business_date).exists():
            raise DayCloseError("This store day has already been closed.")

        day_bills = Bill.objects.filter(
            store=store, bill_datetime__gte=start, bill_datetime__lt=end
        )
        if day_bills.filter(status="H").exists():
            raise DayCloseError("Cannot close day: there are held bills")

        completed = day_bills.filter(status="C").prefetch_related("tenders", "items")
        cash = ZERO
        card = ZERO
        upi = ZERO
        sales = ZERO
        gst = ZERO

        for bill in completed:
            sign = Decimal("-1") if bill.bill_type == "REFUND" else Decimal("1")
            for tender in bill.tenders.all():
                amount = money(tender.amount) * sign
                if tender.tender_type == "CASH":
                    cash += amount
                elif tender.tender_type == "CARD":
                    card += amount
                elif tender.tender_type == "UPI":
                    upi += amount

            for item in bill.items.all():
                line = Decimal(item.qty) * item.mrp - item.discount
                if line < ZERO:
                    raise DayCloseError(f"Negative item line on bill {bill.bill_no}.")
                rate = item.gst_rate / Decimal("100")
                tax = (line - (line / (Decimal("1") + rate))).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                sales += line * sign
                gst += tax * sign

        cash, card, upi = money(cash), money(card), money(upi)
        sales, gst = money(sales), money(gst)
        variance = money(card - machine_card_total)
        print('=variance=',variance)
        print('==CARD_TOLERANCE=',CARD_TOLERANCE)
        if abs(variance) > CARD_TOLERANCE:
            raise DayCloseError(f"Card variance too high: {variance}")

        # Preserve the PHP rule: sales only, floor(net bill value / 100), max 500.
        # Missing loyalty profiles are ignored as the legacy UPDATE affected zero rows.
        awards = {}
        sale_bills = completed.filter(bill_type="SALE").exclude(customer_mobile="")
        for bill in sale_bills:
            points = min(
                int((bill.net_amount / Decimal("100")).to_integral_value(rounding=ROUND_FLOOR)),
                500,
            )
            if points > 0:
                loyalty = Loyalty.objects.filter(
                    customer_mobile=bill.customer_mobile
                ).first()
                if loyalty:
                    loyalty.points += points
                    loyalty.save(update_fields=["points"])
                    awards[bill.customer_mobile] = awards.get(bill.customer_mobile, 0) + points

        close = DayClose.objects.create(
            store=store, business_date=business_date, closed_by=str(user)[:50],
            cash_total=cash, card_total=card, upi_total=upi,
            machine_card_total=machine_card_total, variance=variance,
        )
        finance_amounts = {
            "CASH": cash, "CARD": card, "UPI": upi,
            "SALES": money(sales - gst), "GST": gst,
        }
        finance_rows = [
            FinanceInterface(
                store=store, business_date=business_date,
                gl_type=kind, amount=amount,
            )
            for kind, amount in finance_amounts.items()
        ]
        FinanceInterface.objects.bulk_create(finance_rows)

    return {
        "day_close": close,
        "tender_totals": {"CASH": cash, "CARD": card, "UPI": upi},
        "sales_inclusive_gst": sales,
        "gst": gst,
        "sales_excluding_gst": money(sales - gst),
        "loyalty_points_awarded": awards,
        "finance_rows": finance_amounts,
        "variance": variance,
    }
