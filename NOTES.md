# AllPOS Day Close — Business Rules, Findings and Sample Result

## Scope and source interpretation
Rebuilt from the supplied `day_close.php`, `schema.sql`, and five CSV files. The original PHP is the source of legacy business rules. This implementation preserves those rules unless a correction is documented below.

## Business rules found in `day_close.php`
1. A store day cannot close while any bill for that store/day has status `H` (held).
2. Only completed (`C`) bills contribute to totals. Voided (`V`) bills are ignored.
3. Tender types are CASH, CARD and UPI. Tender amounts on REFUND bills are subtracted; SALE tender amounts are added.
4. Each completed bill item has GST-inclusive MRP. Its line amount is `qty * mrp - discount`.
5. GST is calculated on each line as `line - line / (1 + gst_rate / 100)`, rounded to two decimal places. Refund line value and GST are negative.
6. Card variance is POS card tender total minus the manager-entered machine slip total. The stated tolerance is Rs 1.
7. Loyalty applies to completed SALE bills with a non-empty customer mobile. Points are `floor(net_amount / 100)`, capped at 500 per bill. Refunds do not earn points.
8. A successful close creates one day-close row and five finance rows: CASH, CARD, UPI, SALES (excluding GST), and GST.

## Legacy bugs / risks and changes
| Finding in PHP | Production risk | Change |
|---|---|---|
| `BETWEEN '$date' AND '$date'` compares timestamps against the same midnight boundary | Transactions after midnight at the start of the date may be omitted; late-night bills such as 23:30 are missed | Use inclusive start-of-day and exclusive start-of-next-day datetime bounds |
| Card validation checks only `variance > 1` | A large negative variance is accepted even though the machine and POS disagree | Reject when `abs(variance) > 1`; exactly Rs 1 either way is allowed |
| No transaction wraps loyalty, day-close and finance writes | Partial close can update loyalty without creating all accounting rows | Wrap the operation in `transaction.atomic()` |
| No duplicate-close protection | Repeated requests can award loyalty twice and duplicate finance postings | Unique store/date constraint plus a locked store row and existing-close check |
| SQL values are interpolated directly | SQL injection and quoting/data-corruption risk | Use Django ORM parameterized queries |
| Database write errors are not checked | PHP can report success after failed inserts/updates | ORM exceptions abort the atomic transaction |
| No explicit missing loyalty-profile handling | A customer without a loyalty row silently receives no points | Preserve the actual legacy outcome (no row means no update); record awarded points only for an existing profile |

## Questions for the business
1. Should card variance be absolute, as implemented, or is there a documented reason to reject only positive variance? The PHP comment says the POS total must agree with the slip, so absolute variance is the safer interpretation.
2. Should a sale for a mobile number without a `loyalty` row create a loyalty profile automatically, or should it continue to receive no points as the PHP `UPDATE` currently does?
3. Does `net_amount` always equal the sum of item line amounts after discounts? The legacy code uses item rows for sales/GST and bill `net_amount` for loyalty, without reconciling them.
4. Should a refund reverse loyalty points previously awarded on the original sale? The PHP explicitly awards points on SALE bills only, so this rebuild does not reverse points.
5. Is the Rs 1 card tolerance inclusive? This rebuild allows exactly Rs 1 and rejects any amount greater than Rs 1.

## Sample run — S01, 2026-11-10, machine card total Rs 44,797.00
Calculated using the supplied CSV data and corrected full-day date range.

### Tender totals
| Tender | Amount |
|---|---:|
| CASH | 1,797.00 |
| CARD | 44,797.00 |
| UPI | 25,878.00 |
| **Total tenders** | **72,472.00** |

### Sales and GST
| Measure | Amount |
|---|---:|
| Sales including GST (net of refunds) | 72,472.00 |
| GST | 7,402.12 |
| **Sales excluding GST** | **65,069.88** |

GST is rounded per bill-item line, matching the PHP calculation method. Refund B1005 reduces sales by Rs 999.00 and GST by Rs 47.57.

### Card reconciliation
- POS card total: Rs 44,797.00
- Machine card total: Rs 44,797.00
- Variance (POS minus machine): Rs 0.00
- Result: accepted.

### Loyalty points
| Customer mobile | Starting points | Points awarded | Ending points |
|---|---:|---:|---:|
| 9840011111 | 120 | 37 | 157 |
| 9840033333 | 40 | 500 | 540 |
| 9840022222 | No loyalty row | 0 | No row created |

B1004's customer (9840022222) earns 38 points by the bill formula, but no loyalty profile exists in the supplied loyalty CSV. The legacy SQL UPDATE would affect zero rows. This rebuild preserves that outcome and calls it out as a business question.

### Finance interface rows
| GL type | Amount |
|---|---:|
| CASH | 1,797.00 |
| CARD | 44,797.00 |
| UPI | 25,878.00 |
| SALES | 65,069.88 |
| GST | 7,402.12 |

Five rows are created, one per GL type.

## Important date-range observation
B1007 at 23:30 on 10 November is included. B1008 at 00:10 on 11 November and B1009 on 11 November are excluded. B1003 is voided and excluded. B1009 is held but belongs to the next date, so it does not block the 10 November close.

## Rounding and portability
Money uses `Decimal`; GST is rounded to two decimal places per item using `ROUND_HALF_UP`. The Django ORM and standard transaction APIs are database portable. SQLite is configured for local use; MySQL can be configured in `config/settings.py`.
