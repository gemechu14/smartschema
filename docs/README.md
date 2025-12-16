# SmartSchema Backend Documentation

Welcome to the SmartSchema Backend documentation. This documentation provides comprehensive coverage of the entire codebase, organized by module and functionality.

## Documentation Structure

This documentation is organized into multiple files for easy navigation:

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, request flows, and database relationships
- **[API.md](API.md)** - Complete API reference with endpoints, schemas, and examples
- **[MODELS.md](MODELS.md)** - Database models documentation (SQLAlchemy models)
- **[SCHEMAS.md](SCHEMAS.md)** - Pydantic schemas documentation (request/response validation)
- **[ROUTES.md](ROUTES.md)** - API route handlers documentation
- **[SERVICES.md](SERVICES.md)** - Business logic services documentation
- **[CORE.md](CORE.md)** - Core configuration and security utilities
- **[DATABASE.md](DATABASE.md)** - Database setup, migrations, and schema documentation
- **[RECOMMENDATIONS.md](RECOMMENDATIONS.md)** - Best practices and improvement recommendations

## Quick Start Guide

### For Developers

1. **Setup**: See the main [README.md](../README.md) for installation and setup instructions
2. **API Testing**: Import `SmartSchema_API.postman_collection.json` into Postman
3. **Understanding the Code**: Start with [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
4. **API Integration**: Refer to [API.md](API.md) for endpoint documentation
5. **Database**: Check [DATABASE.md](DATABASE.md) for schema and migration information

### For API Consumers

1. **Authentication**: See [API.md](API.md) → Authentication section
2. **Endpoints**: Browse [API.md](API.md) for all available endpoints
3. **Request/Response**: Check [SCHEMAS.md](SCHEMAS.md) for data structures
4. **Postman Collection**: Use `SmartSchema_API.postman_collection.json` for testing

## Project Overview

SmartSchema Backend is a FastAPI-based application that provides:

- **User Authentication**: JWT-based auth with email verification, Google OAuth, password reset
- **Account Management**: Multi-tenant accounts with role-based access control (OWNER, ADMIN, MEMBER, VIEWER)
- **Schema Management**: Create and manage data schemas with validation rules
- **Subscriptions**: Stripe integration for PRO plan subscriptions with trial periods
- **Integrations**: API credentials and integrations for embedding schema forms
- **Dashboard**: KPIs and statistics for accounts

## Key Technologies

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Authentication**: JWT (PyJWT), Passlib for password hashing
- **Payments**: Stripe
- **Email**: SMTP (smtplib)
- **File Processing**: Pandas, pdfplumber, sqlparse

## Getting Help

- **API Issues**: Check [API.md](API.md) for endpoint details and error codes
- **Database Issues**: See [DATABASE.md](DATABASE.md) for migration and schema help
- **Security**: Review [CORE.md](CORE.md) for security implementation details
- **Improvements**: See [RECOMMENDATIONS.md](RECOMMENDATIONS.md) for best practices

## Contributing

When adding new features:

1. Update relevant documentation files
2. Add examples to Postman collection
3. Document new models in [MODELS.md](MODELS.md)
4. Document new schemas in [SCHEMAS.md](SCHEMAS.md)
5. Document new routes in [ROUTES.md](ROUTES.md)
6. Update [API.md](API.md) with new endpoints

---

**Last Updated**: December 2024


