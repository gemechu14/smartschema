# Services Documentation

This document provides detailed documentation for all business logic services in the SmartSchema Backend.

## Overview

Services contain business logic separated from route handlers. They handle external integrations, data processing, and complex operations.

## Service Files

### `app/services/billing.py`

Stripe billing integration service.

#### PLANS Dictionary

```python
PLANS = {
    "FREE": {
        "id": "free",
        "name": "Free",
        "price": 0,
        "import_formats": ["csv", "excel"],
        "limits": {
            "rows": 1000,
            "schemas": 5,
            "members": 3,
        },
    },
    "PRO": {
        "id": "pro",
        "name": "Pro",
        "price": 39900,  # in cents
        "import_formats": ["csv", "excel"],
        "limits": {
            "rows": None,
            "schemas": None,
            "members": None,
        },
    },
}
```

**Purpose**: Defines available subscription plans and their limits

**Usage**: Used by public plans endpoint and subscription status

---

#### create_checkout_session()

```python
def create_checkout_session(
    customer_email: str,
    plan_key: str,
    success_url: str,
    cancel_url: str,
    account_id: str
) -> dict
```

**Purpose**: Create Stripe Checkout Session for subscription

**Parameters**:
- `customer_email`: Customer email address
- `plan_key`: "FREE" or "PRO"
- `success_url`: Redirect URL after successful payment
- `cancel_url`: Redirect URL if payment canceled
- `account_id`: Account UUID to link subscription

**Returns**: Stripe Checkout Session object

**Implementation**:
- For PRO: Creates subscription checkout with 14-day trial
- For FREE: Creates customer only (no subscription)
- Includes account_id in metadata
- Requires `STRIPE_PRICE_ID_PRO` environment variable

**Example**:
```python
session = create_checkout_session(
    customer_email="user@example.com",
    plan_key="PRO",
    success_url="https://app.smartschema.io/billing/success",
    cancel_url="https://app.smartschema.io/billing/cancel",
    account_id=str(account.id)
)
```

**Errors**:
- `ValueError`: Unknown plan
- `RuntimeError`: STRIPE_PRICE_ID_PRO not configured

---

#### create_billing_portal_session()

```python
def create_billing_portal_session(
    stripe_customer_id: str,
    return_url: str
) -> dict
```

**Purpose**: Create Stripe Billing Portal session

**Parameters**:
- `stripe_customer_id`: Stripe customer ID
- `return_url`: URL to redirect after portal session

**Returns**: Stripe Billing Portal Session object

**Example**:
```python
session = create_billing_portal_session(
    stripe_customer_id="cus_123",
    return_url="https://app.smartschema.io/billing/portal-return"
)
```

**Errors**:
- `ValueError`: stripe_customer_id required
- Stripe API errors if portal not configured

---

#### retrieve_subscription()

```python
def retrieve_subscription(
    stripe_subscription_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None
) -> Optional[dict]
```

**Purpose**: Retrieve subscription from Stripe

**Parameters**:
- `stripe_subscription_id`: Subscription ID (preferred)
- `stripe_customer_id`: Customer ID (fallback)

**Returns**: Stripe Subscription object or None

**Implementation**:
- Retrieves by subscription ID if provided
- Otherwise lists subscriptions for customer (returns first)
- Returns None on error

**Example**:
```python
sub = retrieve_subscription(stripe_subscription_id="sub_123")
if sub:
    status = sub.get("status")
```

---

#### canonicalize_status()

```python
def canonicalize_status(raw_status: Optional[str]) -> str
```

**Purpose**: Map Stripe status to canonical status

**Parameters**:
- `raw_status`: Raw Stripe status string

**Returns**: Canonical status string

**Mapping**:
- `active`, `trialing` → `"active"`
- `incomplete`, `incomplete_expired` → `"incomplete"`
- `past_due`, `unpaid` → `"past_due"`
- `canceled`, `cancelled` → `"canceled"`
- `paused`, `pause_collection` → `"paused"`
- Other → `"unknown"`

**Example**:
```python
canonical = canonicalize_status("trialing")  # Returns "active"
```

---

#### status_description()

```python
def status_description(canonical_status: str) -> str
```

**Purpose**: Get user-friendly status description

**Parameters**:
- `canonical_status`: Canonical status string

**Returns**: Human-readable description

**Example**:
```python
desc = status_description("active")
# Returns: "Subscription is active and billing is up to date."
```

---

### `app/services/mailer.py`

Email sending service.

#### send_email()

```python
def send_email(
    to_email: str,
    subject: str,
    html: str,
    from_name: Optional[str] = None
)
```

**Purpose**: Send HTML email via SMTP

**Parameters**:
- `to_email`: Recipient email address
- `subject`: Email subject line
- `html`: HTML email body
- `from_name`: Sender display name (optional)

**Implementation**:
- Uses SMTP with STARTTLS
- Authenticates with SMTP_USER and SMTP_PASSWORD
- Sends from MAIL_FROM address
- Uses MIMEText for HTML emails

**Configuration** (from `app/core/config.py`):
- `SMTP_SERVER`: SMTP server hostname
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `MAIL_FROM`: Sender email address
- `MAIL_FROM_NAME`: Default sender name

**Example**:
```python
send_email(
    to_email="user@example.com",
    subject="Welcome to SmartSchema",
    html="<h1>Welcome!</h1><p>Thank you for signing up.</p>",
    from_name="SmartSchema Team"
)
```

**Email Types Sent**:
- Verification emails
- Password reset emails
- Invitation emails
- Password change confirmations
- Contact form submissions

**Error Handling**:
- Raises exception on failure
- Routes catch and handle gracefully (best-effort)

---

### `app/services/schema_inference.py`

Schema inference from files and SQL.

#### infer_from_file()

```python
def infer_from_file(
    raw: bytes,
    filename: str,
    source_type: Optional[str] = None,
    header_row: int = 0,
    sheets: Optional[List[str]] = None,
    sheet_header_rows: Optional[List[int]] = None
) -> List[Dict[str, Any]]
```

**Purpose**: Infer schema from uploaded file

**Parameters**:
- `raw`: File bytes
- `filename`: Original filename
- `source_type`: File type hint ("csv", "excel", "pdf", "json")
- `header_row`: 0-based row index for header (CSV/Excel)
- `sheets`: List of sheet names/indices (Excel only)
- `sheet_header_rows`: Per-sheet header rows (Excel only)

**Returns**: List of inferred schemas (one per sheet/table)

**Supported Formats**:
- CSV: Comma-separated values
- Excel: Multiple sheets supported
- PDF: Extracts tables using pdfplumber
- JSON: Parses JSON structure

**Implementation**:
- Detects file type via `filetype` library or extension
- Reads into pandas DataFrame
- Applies header row if specified
- Infers types using `type_inference` module
- Generates validators based on data patterns

**Example**:
```python
with open("data.csv", "rb") as f:
    raw = f.read()
schemas = infer_from_file(
    raw,
    filename="data.csv",
    source_type="csv",
    header_row=0
)
# Returns: [{"schema": {...}, "validators": {...}}]
```

**Errors**:
- `ValueError`: Invalid file format or header row out of range

---

#### infer_from_sql()

```python
def infer_from_sql(sql: str) -> List[Dict[str, Any]]
```

**Purpose**: Infer schema from SQL CREATE TABLE statement

**Parameters**:
- `sql`: SQL CREATE TABLE statement

**Returns**: List of inferred schemas (one per table)

**Implementation**:
- Parses SQL using `sqlparse`
- Extracts CREATE TABLE statements
- Infers column types from SQL types
- Generates basic validators

**Example**:
```python
sql = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255),
    age INTEGER
);
"""
schemas = infer_from_sql(sql)
# Returns: [{"schema": {"columns": [...]}, "validators": {...}}]
```

---

#### infer_from_dataframe()

```python
def infer_from_dataframe(
    df: pd.DataFrame,
    sample: int = 500
) -> Dict[str, Any]
```

**Purpose**: Infer schema from pandas DataFrame

**Parameters**:
- `df`: Pandas DataFrame
- `sample`: Number of rows to sample for inference

**Returns**: Schema dictionary with columns and validators

**Implementation**:
- Samples rows for performance
- Normalizes column names (handles duplicates)
- Infers types using `guess_scalar_type()`
- Detects ID-like columns
- Detects email columns
- Generates regex patterns
- Calculates numeric bounds
- Special handling for age columns

**Type Inference**:
- UUID: If 80%+ values match UUID pattern
- Boolean: If values match boolean patterns
- Integer: If values are integers
- Float: If values are numeric
- Date: If values are dates (no time)
- DateTime: If values are datetimes
- String: Default fallback

**Validator Rules**:
- ID-like columns: `required=True`, `unique=True`
- Email columns: `unique=True`, email regex
- Age columns: `min=0`, `max=None`
- Other numeric: `min`/`max` from data bounds
- Pattern matching: Regex if 80%+ match pattern

---

### `app/services/type_inference.py`

Data type inference utilities.

#### guess_scalar_type()

```python
def guess_scalar_type(values: Iterable) -> str
```

**Purpose**: Infer data type from value samples

**Parameters**:
- `values`: Iterable of values to analyze

**Returns**: Type string ("uuid", "integer", "float", "boolean", "date", "datetime", "string")

**Algorithm**:
1. Filters out null/empty values
2. Checks UUID pattern (80%+ match)
3. Checks boolean patterns
4. Checks integer patterns
5. Checks float patterns
6. Checks date/datetime patterns
7. Returns most common type or "string"

**Example**:
```python
values = ["2024-01-01", "2024-01-02", "2024-01-03"]
type_str = guess_scalar_type(values)  # Returns "date"
```

---

#### best_regex()

```python
def best_regex(values: Iterable) -> Optional[str]
```

**Purpose**: Find best matching regex pattern

**Parameters**:
- `values`: Iterable of values to analyze

**Returns**: Regex pattern string or None

**Patterns Checked**:
- Email: `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$`
- UUID: `^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`
- Phone: `^\+?\d[\d\s\-\(\)]{7,}$`

**Returns**: Pattern if 80%+ values match, None otherwise

---

#### numeric_bounds()

```python
def numeric_bounds(values: Iterable) -> Tuple[Optional[float], Optional[float]]
```

**Purpose**: Calculate min/max bounds for numeric values

**Parameters**:
- `values`: Iterable of values

**Returns**: Tuple of (min, max) or (None, None)

**Example**:
```python
values = [10, 20, 30, 40]
min_val, max_val = numeric_bounds(values)  # Returns (10.0, 40.0)
```

---

#### is_id_like()

```python
def is_id_like(col_name: str, dtype: str, values: Iterable) -> bool
```

**Purpose**: Detect if column is ID-like

**Parameters**:
- `col_name`: Column name
- `dtype`: Inferred data type
- `values`: Column values

**Returns**: True if column appears to be an ID

**Heuristics**:
- Column name contains "id" or equals "uuid"
- Data type is "uuid"
- Numeric, unique (90%+ distinct), non-negative

---

#### is_age_column()

```python
def is_age_column(col_name: str) -> bool
```

**Purpose**: Detect if column name indicates age

**Parameters**:
- `col_name`: Column name

**Returns**: True if column name suggests age

**Patterns**:
- Exact match: "age", "ages"
- Ends with: "_age"

---

### `app/services/reconciliation.py`

**Status**: Currently empty file

**Purpose**: Intended for data reconciliation logic

**Future Use**: May contain functions for:
- Data validation and reconciliation
- Conflict resolution
- Data merging logic

---

## Service Usage Patterns

### Error Handling

Services raise exceptions that routes catch:

```python
try:
    session = create_checkout_session(...)
except RuntimeError as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### Configuration

Services read configuration from `app/core/config.py`:

```python
from app.core.config import settings

stripe.api_key = settings.stripe_secret
```

### External Dependencies

Services handle external API calls:

```python
# Stripe API
session = stripe.checkout.Session.create(...)

# SMTP
with smtplib.SMTP(...) as server:
    server.sendmail(...)
```

### Data Processing

Services process data independently:

```python
# Schema inference
schemas = infer_from_file(file_bytes, filename)

# Type inference
type_str = guess_scalar_type(values)
```

## Best Practices

1. **Separation of Concerns**: Keep business logic in services, not routes
2. **Error Handling**: Raise specific exceptions, let routes handle HTTP errors
3. **Configuration**: Read from settings, not environment directly
4. **Idempotency**: Make operations idempotent where possible
5. **Documentation**: Document function parameters and return values
6. **Testing**: Services should be easily testable (no route dependencies)
7. **External APIs**: Handle API errors gracefully
8. **Performance**: Use sampling for large datasets (schema inference)

## Future Improvements

1. **Async Operations**: Convert to async/await for better performance
2. **Background Tasks**: Move email sending to background tasks
3. **Caching**: Cache plan definitions and subscription status
4. **Rate Limiting**: Add rate limiting for external API calls
5. **Retry Logic**: Add retry logic for external API failures
6. **Logging**: Add structured logging for service operations
7. **Metrics**: Add metrics for service performance
8. **Batch Processing**: Support batch operations for efficiency


