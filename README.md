# AllPOS Day Close — Django rebuild

A Django + Django REST Framework implementation of the supplied legacy PHP day-close feature.

## Requirements
- Python 3.11+
- pip
- SQLite for local development (included with Python)
- MySQL is supported by changing the Django database settings.

## Setup
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python manage.py makemigrations day_close
python manage.py migrate
python manage.py createsuperuser
```

## Load supplied sample CSV data
Copy the five supplied CSV files into `sample_data/` (the directory should contain `stores.csv`, `bills.csv`, `bill_items.csv`, `bill_tenders.csv`, and `loyalty.csv`), then run:
```bash
python manage.py load_sample_data --data-dir sample_data
```
The source CSV files are intentionally not duplicated in this repository. Use the files provided with the assessment.

## Run server
```bash
python manage.py runserver
```

## API
`POST /api/day-close/` requires an authenticated Django user.

Request:
```json
{
  "store_code": "S01",
  "business_date": "2026-11-10",
  "machine_card_total": "44797.00"
}
```

Use Django session authentication or HTTP Basic authentication. For a quick local test, create a user with `createsuperuser` and use Basic Auth in an API client.

Success returns HTTP 201 with tender totals, sales, GST, loyalty points awarded, variance, and finance row amounts. Business-rule failures return HTTP 400. Invalid request fields are rejected by DRF validation.

## Run tests
```bash
python manage.py test
```

## MySQL configuration
Install a MySQL driver such as `mysqlclient`, then replace the `DATABASES` setting in `config/settings.py` with:
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "allpos",
        "USER": "your_user",
        "PASSWORD": "your_password",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
```
Create the database first and run migrations. Use environment variables or a secrets manager for credentials in production. `select_for_update()` requires a transactional database; SQLite does not provide equivalent row-level locking, but the unique store/date constraint still prevents duplicate close records.

## Design notes
- Business logic lives in `day_close/services.py`, separate from the HTTP view.
- `transaction.atomic()` ensures loyalty updates, the day-close record and finance postings commit or roll back together.
- Store-row locking serializes close attempts on MySQL/InnoDB.
- Unique constraint prevents more than one close per store/date.
- Full-day filtering uses `[00:00 on date, 00:00 next date)`.
- All financial arithmetic uses `Decimal`, not binary floating point.
- See `NOTES.md` for detailed business rules, identified legacy defects, business questions, and calculated sample results.
