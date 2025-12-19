# SmartSchema Backend

A FastAPI-based backend application for SmartSchema, featuring authentication, schema management, subscriptions, integrations, and billing.

## Project Structure

```
SmartSchema-Backend/
├── alembic/              # Database migration scripts
├── app/
│   ├── api/              # API routes and dependencies
│   │   └── routes/       # Route handlers
│   ├── core/             # Core configuration and security
│   ├── db/               # Database session and models
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic services
│   └── main.py           # FastAPI application entry point
├── migrations/           # Additional migration files
├── scripts/              # Utility scripts
├── alembic.ini           # Alembic configuration
├── requirements.txt      # Python dependencies
└── vercel.json           # Vercel deployment configuration
```

## Prerequisites

- Python 3.9+ (recommended: Python 3.10 or higher)
- PostgreSQL database
- pip (Python package manager)

## Installation Steps

### 1. Clone the Repository
```bash
git clone <repository-url>
cd SmartSchema-Backend
```

### 2. Create a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Note:** The project uses `python-dotenv` but it's not listed in `requirements.txt`. You may need to install it separately:
```bash
pip install python-dotenv
```

### 4. Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

#### Required Environment Variables

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/smartschema_db

# Application Configuration
APP_NAME=SmartSchema
APP_BASE_URL=https://app.smartschema.io  # or http://localhost:3000 for local dev

# JWT Authentication
JWT_SECRET=your-secret-key-change-this-in-production
JWT_ISSUER=locimapper-api
ACCESS_TOKEN_TTL_MIN=15
REFRESH_TOKEN_TTL_DAYS=30

# Email Configuration (SMTP)
SMTP_SERVER=smtp.gmail.com  # or your SMTP server
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_FROM_NAME=SmartSchema

# Google OAuth (if using Google authentication)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://app.smartschema.io/auth/google/callback

# Stripe Configuration (for billing/subscriptions)
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRICE_ID_PRO=price_your_pro_plan_price_id

# Optional Configuration (with defaults)
INVITE_EXP_DAYS=7
EMAIL_VERIFY_EXP_HOURS=24
EMAIL_VERIFY_RESEND_COOLDOWN_S=60
PASSWORD_RESET_EXP_HOURS=24
LAUNCH_TOKEN_TTL_SECONDS=300
```

### 5. Set Up PostgreSQL Database

1. Install PostgreSQL if not already installed
2. Create a new database:
```sql
CREATE DATABASE smartschema_db;
```

3. Update `DATABASE_URL` in your `.env` file with your database credentials

### 6. Run Database Migrations

```bash
# Upgrade to latest migration
alembic upgrade head

# Or if you need to see migration status
alembic current
alembic history
```

### 7. Start the Development Server

```bash
# Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python module
python -m uvicorn app.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **API Documentation**: http://localhost:8000/gibberish-xyz-123

## API Endpoints

The application includes the following route modules:
- `/api/auth` - Authentication endpoints
- `/api/accounts` - Account management
- `/api/schemas` - Schema management
- `/api/subscriptions` - Subscription management
- `/api/integrations` - Integration endpoints
- `/api/mapper` - Mapping functionality
- `/api/dashboard` - Dashboard data
- `/api/contact` - Contact form
- `/api/public-plans` - Public plan information
- `/api/stripe-webhook` - Stripe webhook handler

## Development Notes

### Database Migrations

- Create a new migration:
  ```bash
  alembic revision --autogenerate -m "description of changes"
  ```

- Apply migrations:
  ```bash
  alembic upgrade head
  ```

- Rollback migration:
  ```bash
  alembic downgrade -1
  ```

### CORS Configuration

The application is configured to allow requests from:
- `https://app.smartschema.io`
- `https://www.app.smartschema.io`
- `http://localhost:3000` (for local development)
- `https://smartschema.io`
- `https://www.smartschema.io`

Update CORS origins in `app/main.py` if needed.

### Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Stripe Dashboard
3. Create a Price for the PRO plan and note the Price ID
4. Set up webhook endpoint in Stripe Dashboard pointing to `/api/stripe-webhook`
5. Copy the webhook signing secret to `STRIPE_WEBHOOK_SECRET`

## Deployment

### Vercel Deployment

The project includes `vercel.json` for Vercel deployment. To deploy:

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Deploy:
   ```bash
   vercel
   ```

3. Set environment variables in Vercel dashboard

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify `DATABASE_URL` is correct
   - Ensure PostgreSQL is running
   - Check database credentials

2. **Missing python-dotenv**
   - Install: `pip install python-dotenv`

3. **Migration Errors**
   - Ensure database exists
   - Check `DATABASE_URL` in `.env`
   - Verify Alembic configuration in `alembic.ini`

4. **Import Errors**
   - Ensure virtual environment is activated
   - Verify all dependencies are installed: `pip install -r requirements.txt`

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Alembic Documentation: https://alembic.sqlalchemy.org/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Stripe API Documentation: https://stripe.com/docs/api



















