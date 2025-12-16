# Database Documentation

This document provides comprehensive documentation for database setup, migrations, schema relationships, and optimization in the SmartSchema Backend.

## Database Setup

### PostgreSQL Requirements

- **Version**: PostgreSQL 12+ recommended
- **Extensions**: No special extensions required
- **Encoding**: UTF-8

### Connection String Format

```
postgresql://username:password@host:port/database_name
```

**Example**:
```
postgresql://postgres:mypassword@localhost:5432/smartschema_db
```

### Environment Variable

Set `DATABASE_URL` in your `.env` file:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/smartschema_db
```

## Database Schema

### Tables Overview

1. **users** - User accounts
2. **accounts** - Workspace/tenant accounts
3. **memberships** - User-account relationships with roles
4. **invitations** - Pending team invitations
5. **refresh_tokens** - Refresh token storage
6. **schema_specifications** - Data schema definitions
7. **subscriptions** - Subscription records
8. **webhook_events** - Stripe webhook idempotency
9. **app_credentials** - API credentials
10. **integrations** - Integration mappings
11. **email_verifications** - Email verification tokens
12. **password_resets** - Password reset tokens
13. **launch_tokens** - Integration launch tokens

## Database Design Diagrams

### Complete Entity Relationship Diagram (ERD)

This diagram shows all tables with their key fields and relationships:

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK "indexed"
        string first_name
        string last_name
        string password_hash
        string google_sub UK
        boolean is_active
        timestamp email_verified_at
        timestamp created_at
    }
    
    accounts {
        uuid id PK
        string name
        uuid owner_user_id FK "unique"
        timestamp created_at
    }
    
    memberships {
        uuid id PK
        uuid account_id FK "indexed"
        uuid user_id FK "indexed"
        enum role "OWNER,ADMIN,MEMBER,VIEWER"
        jsonb manage_schema_ids
        timestamp created_at
    }
    
    invitations {
        uuid id PK
        uuid account_id FK
        string email
        enum role
        string token_hash UK "indexed"
        timestamp expires_at
        timestamp accepted_at
        jsonb manage_schema_ids
        timestamp created_at
    }
    
    refresh_tokens {
        uuid id PK
        uuid user_id FK
        uuid account_id FK
        string jti "indexed"
        string token_hash UK
        string user_agent
        string ip
        timestamp expires_at
        timestamp revoked_at
        timestamp created_at
    }
    
    schema_specifications {
        uuid id PK
        string schema_name
        string description
        jsonb schema
        jsonb validators
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at "soft delete"
        uuid account_id FK "indexed"
        uuid created_by_user_id FK "indexed, nullable"
    }
    
    subscriptions {
        uuid id PK
        uuid account_id FK "indexed"
        string stripe_customer_id
        string stripe_subscription_id
        string plan "FREE,PRO"
        string status
        string raw_stripe_status
        string last_stripe_event_id
        timestamp current_period_end
        timestamp trial_ends_at
        timestamp created_at
    }
    
    webhook_events {
        uuid id PK
        string event_id UK "indexed"
        timestamp processed_at
    }
    
    app_credentials {
        uuid id PK
        uuid account_id FK
        uuid created_by FK "nullable"
        string client_id UK
        string client_secret_hash
        timestamp client_secret_expires_at
        string app_name
        jsonb authorized_js_origins
        jsonb theme
        timestamp created_at
        boolean revoked
    }
    
    integrations {
        uuid id PK
        uuid account_id FK
        uuid created_by FK "nullable"
        string name
        string description
        uuid schema_id FK
        uuid credential_id FK
        string redirect_url
        string api_endpoint
        jsonb api_headers
        string method
        jsonb behavior
        timestamp created_at
        boolean active
        integer usage
    }
    
    email_verifications {
        uuid id PK
        uuid user_id FK "indexed"
        string token_hash UK
        timestamp expires_at
        timestamp consumed_at
        timestamp created_at
    }
    
    password_resets {
        uuid id PK
        uuid user_id FK "indexed"
        string token_hash UK
        timestamp expires_at
        timestamp consumed_at
        timestamp created_at
    }
    
    launch_tokens {
        uuid id PK
        string token_hash UK
        uuid integration_id
        uuid credential_id
        uuid account_id
        timestamp expires_at
        boolean used
        timestamp created_at
    }
    
    %% Relationships
    users ||--o{ memberships : "has"
    users ||--o{ refresh_tokens : "has"
    users ||--o{ email_verifications : "has"
    users ||--o{ password_resets : "has"
    users ||--|| accounts : "owns"
    users ||--o{ schema_specifications : "creates"
    users ||--o{ app_credentials : "creates"
    users ||--o{ integrations : "creates"
    
    accounts ||--o{ memberships : "contains"
    accounts ||--o{ schema_specifications : "has"
    accounts ||--o{ subscriptions : "has"
    accounts ||--o{ app_credentials : "has"
    accounts ||--o{ integrations : "has"
    accounts ||--o{ invitations : "sends"
    
    schema_specifications ||--o{ integrations : "mapped_by"
    
    app_credentials ||--o{ integrations : "used_by"
    app_credentials ||--o{ launch_tokens : "generates"
    
    integrations ||--o{ launch_tokens : "creates"
```

### Simplified Relationship Diagram

High-level view of table relationships:

```mermaid
erDiagram
    users ||--o{ memberships : has
    users ||--o{ refresh_tokens : has
    users ||--o{ email_verifications : has
    users ||--o{ password_resets : has
    users ||--|| accounts : owns
    
    accounts ||--o{ memberships : contains
    accounts ||--o{ schema_specifications : has
    accounts ||--o{ subscriptions : has
    accounts ||--o{ app_credentials : has
    accounts ||--o{ integrations : has
    accounts ||--o{ invitations : sends
    
    schema_specifications ||--o{ integrations : mapped_by
    
    app_credentials ||--o{ integrations : used_by
    app_credentials ||--o{ launch_tokens : generates
    
    integrations ||--o{ launch_tokens : creates
```

### Table Structure Diagram

Visual representation of table structures and data types:

```mermaid
graph TB
    subgraph "Authentication & Users"
        users[users<br/>id: UUID PK<br/>email: STRING UK<br/>password_hash: STRING<br/>is_active: BOOLEAN<br/>email_verified_at: TIMESTAMP]
        accounts[accounts<br/>id: UUID PK<br/>name: STRING<br/>owner_user_id: UUID FK UK]
        memberships[memberships<br/>id: UUID PK<br/>account_id: UUID FK<br/>user_id: UUID FK<br/>role: ENUM<br/>manage_schema_ids: JSONB]
        invitations[invitations<br/>id: UUID PK<br/>account_id: UUID FK<br/>email: STRING<br/>role: ENUM<br/>token_hash: STRING UK<br/>expires_at: TIMESTAMP]
        refresh_tokens[refresh_tokens<br/>id: UUID PK<br/>user_id: UUID FK<br/>account_id: UUID FK<br/>jti: STRING<br/>token_hash: STRING UK<br/>expires_at: TIMESTAMP]
    end
    
    subgraph "Verification & Security"
        email_verifications[email_verifications<br/>id: UUID PK<br/>user_id: UUID FK<br/>token_hash: STRING UK<br/>expires_at: TIMESTAMP<br/>consumed_at: TIMESTAMP]
        password_resets[password_resets<br/>id: UUID PK<br/>user_id: UUID FK<br/>token_hash: STRING UK<br/>expires_at: TIMESTAMP<br/>consumed_at: TIMESTAMP]
    end
    
    subgraph "Schemas & Data"
        schema_specifications[schema_specifications<br/>id: UUID PK<br/>schema_name: STRING<br/>description: STRING<br/>schema: JSONB<br/>validators: JSONB<br/>deleted_at: TIMESTAMP<br/>account_id: UUID FK<br/>created_by_user_id: UUID FK]
    end
    
    subgraph "Integrations"
        app_credentials[app_credentials<br/>id: UUID PK<br/>account_id: UUID FK<br/>client_id: STRING UK<br/>client_secret_hash: STRING<br/>app_name: STRING<br/>authorized_js_origins: JSONB<br/>theme: JSONB]
        integrations[integrations<br/>id: UUID PK<br/>account_id: UUID FK<br/>schema_id: UUID FK<br/>credential_id: UUID FK<br/>name: STRING<br/>api_endpoint: STRING<br/>api_headers: JSONB<br/>behavior: JSONB<br/>usage: INTEGER]
        launch_tokens[launch_tokens<br/>id: UUID PK<br/>token_hash: STRING UK<br/>integration_id: UUID<br/>credential_id: UUID<br/>account_id: UUID<br/>expires_at: TIMESTAMP<br/>used: BOOLEAN]
    end
    
    subgraph "Billing"
        subscriptions[subscriptions<br/>id: UUID PK<br/>account_id: UUID FK<br/>stripe_customer_id: STRING<br/>stripe_subscription_id: STRING<br/>plan: STRING<br/>status: STRING<br/>current_period_end: TIMESTAMP<br/>trial_ends_at: TIMESTAMP]
        webhook_events[webhook_events<br/>id: UUID PK<br/>event_id: STRING UK<br/>processed_at: TIMESTAMP]
    end
    
    users -->|1:1| accounts
    users -->|1:N| memberships
    users -->|1:N| refresh_tokens
    users -->|1:N| email_verifications
    users -->|1:N| password_resets
    
    accounts -->|1:N| memberships
    accounts -->|1:N| schema_specifications
    accounts -->|1:N| subscriptions
    accounts -->|1:N| app_credentials
    accounts -->|1:N| integrations
    accounts -->|1:N| invitations
    
    schema_specifications -->|1:N| integrations
    app_credentials -->|1:N| integrations
    app_credentials -->|1:N| launch_tokens
    integrations -->|1:N| launch_tokens
```

### Data Flow Diagram

Shows how data flows through the database:

```mermaid
flowchart TD
    Start[User Signs Up] --> CreateUser[Create User Record]
    CreateUser --> CheckInvite{Invite Token?}
    
    CheckInvite -->|Yes| ValidateInvite[Validate Invitation]
    ValidateInvite -->|Valid| JoinAccount[Create Membership<br/>Join Existing Account]
    ValidateInvite -->|Invalid| CreateAccount[Create New Account]
    
    CheckInvite -->|No| CreateAccount
    CreateAccount --> CreateMembership[Create Membership<br/>Role: OWNER]
    
    JoinAccount --> CreateMembership
    CreateMembership --> CreateVerification[Create Email Verification]
    CreateVerification --> SendEmail[Send Verification Email]
    
    SendEmail --> UserClicks[User Clicks Link]
    UserClicks --> VerifyEmail[Verify Email]
    VerifyEmail --> ActivateUser[Activate User<br/>is_active = true]
    
    ActivateUser --> Login[User Logs In]
    Login --> CreateTokens[Create Access & Refresh Tokens]
    CreateTokens --> StoreRefreshToken[Store Refresh Token]
    
    StoreRefreshToken --> UseAPI[User Uses API]
    UseAPI --> CreateSchema[Create Schema]
    UseAPI --> CreateCredential[Create API Credential]
    UseAPI --> CreateIntegration[Create Integration]
    
    CreateSchema --> SchemaDB[(schema_specifications)]
    CreateCredential --> CredentialDB[(app_credentials)]
    CreateIntegration --> IntegrationDB[(integrations)]
    
    IntegrationDB --> LaunchIntegration[Launch Integration]
    LaunchIntegration --> CreateLaunchToken[Create Launch Token]
    CreateLaunchToken --> LaunchTokenDB[(launch_tokens)]
```

### Index Strategy Diagram

Visual representation of indexes and their purposes:

```mermaid
graph LR
    subgraph "Primary Keys"
        PK1[users.id<br/>PK Index]
        PK2[accounts.id<br/>PK Index]
        PK3[memberships.id<br/>PK Index]
    end
    
    subgraph "Unique Indexes"
        UK1[users.email<br/>Unique Index<br/>Fast email lookup]
        UK2[users.google_sub<br/>Unique Index<br/>OAuth lookup]
        UK3[refresh_tokens.token_hash<br/>Unique Index<br/>Token validation]
        UK4[invitations.token_hash<br/>Unique Index<br/>Invite validation]
        UK5[email_verifications.token_hash<br/>Unique Index<br/>Verification lookup]
        UK6[password_resets.token_hash<br/>Unique Index<br/>Reset validation]
        UK7[launch_tokens.token_hash<br/>Unique Index<br/>Launch validation]
        UK8[app_credentials.client_id<br/>Unique Index<br/>Credential lookup]
        UK9[webhook_events.event_id<br/>Unique Index<br/>Idempotency check]
    end
    
    subgraph "Foreign Key Indexes"
        FK1[memberships.account_id<br/>Index<br/>Account members query]
        FK2[memberships.user_id<br/>Index<br/>User memberships query]
        FK3[schema_specifications.account_id<br/>Index<br/>Account schemas query]
        FK4[schema_specifications.created_by_user_id<br/>Index<br/>User creations query]
        FK5[refresh_tokens.jti<br/>Index<br/>Token lookup]
    end
    
    subgraph "Composite Indexes"
        COMP1[memberships<br/>account_id + user_id<br/>Unique Constraint<br/>Prevent duplicates]
        COMP2[app_credentials<br/>account_id + app_name<br/>Unique Constraint<br/>Unique names per account]
    end
    
    style PK1 fill:#e1f5ff
    style PK2 fill:#e1f5ff
    style PK3 fill:#e1f5ff
    style UK1 fill:#fff4e1
    style UK2 fill:#fff4e1
    style FK1 fill:#e8f5e9
    style FK2 fill:#e8f5e9
```

### Cascade Delete Flow

Shows what happens when parent records are deleted:

```mermaid
flowchart TD
    DeleteUser[Delete User] -->|CASCADE| DeleteMemberships[Delete Memberships]
    DeleteUser -->|CASCADE| DeleteRefreshTokens[Delete Refresh Tokens]
    DeleteUser -->|CASCADE| DeleteEmailVerifications[Delete Email Verifications]
    DeleteUser -->|CASCADE| DeletePasswordResets[Delete Password Resets]
    DeleteUser -->|SET NULL| NullSchemaCreator[Set schema_specifications.created_by_user_id = NULL]
    DeleteUser -->|SET NULL| NullCredentialCreator[Set app_credentials.created_by = NULL]
    DeleteUser -->|SET NULL| NullIntegrationCreator[Set integrations.created_by = NULL]
    
    DeleteAccount[Delete Account] -->|CASCADE| DeleteAccountMemberships[Delete Memberships]
    DeleteAccount -->|CASCADE| DeleteSchemas[Delete Schema Specifications]
    DeleteAccount -->|CASCADE| DeleteSubscriptions[Delete Subscriptions]
    DeleteAccount -->|CASCADE| DeleteCredentials[Delete API Credentials]
    DeleteAccount -->|CASCADE| DeleteAccountIntegrations[Delete Integrations]
    DeleteAccount -->|CASCADE| DeleteAccountInvitations[Delete Invitations]
    
    DeleteSchema[Delete Schema<br/>Soft Delete] --> SetDeletedAt[Set deleted_at timestamp]
    SetDeletedAt --> RemoveFromMemberships[Remove schema_id from<br/>memberships.manage_schema_ids]
    SetDeletedAt --> RemoveFromInvitations[Remove schema_id from<br/>invitations.manage_schema_ids]
    SetDeletedAt --> DeleteRelatedIntegrations[Delete Related Integrations]
```

### Multi-Tenancy Isolation Diagram

Shows how data is isolated by account:

```mermaid
graph TB
    subgraph "Account A"
        UserA1[User 1]
        UserA2[User 2]
        AccountA[Account A]
        SchemaA1[Schema 1]
        SchemaA2[Schema 2]
        CredentialA1[Credential 1]
        IntegrationA1[Integration 1]
        SubscriptionA[Subscription A]
    end
    
    subgraph "Account B"
        UserB1[User 3]
        UserB2[User 4]
        AccountB[Account B]
        SchemaB1[Schema 3]
        CredentialB1[Credential 2]
        IntegrationB1[Integration 2]
        SubscriptionB[Subscription B]
    end
    
    UserA1 -->|Membership| AccountA
    UserA2 -->|Membership| AccountA
    UserB1 -->|Membership| AccountB
    UserB2 -->|Membership| AccountB
    
    AccountA --> SchemaA1
    AccountA --> SchemaA2
    AccountA --> CredentialA1
    AccountA --> IntegrationA1
    AccountA --> SubscriptionA
    
    AccountB --> SchemaB1
    AccountB --> CredentialB1
    AccountB --> IntegrationB1
    AccountB --> SubscriptionB
    
    SchemaA1 --> IntegrationA1
    CredentialA1 --> IntegrationA1
    
    SchemaB1 --> IntegrationB1
    CredentialB1 --> IntegrationB1
    
    style AccountA fill:#e3f2fd
    style AccountB fill:#fff3e0
```

### Token Lifecycle Diagram

Shows the lifecycle of various tokens:

```mermaid
stateDiagram-v2
    [*] --> EmailVerificationToken: User Signs Up
    EmailVerificationToken --> Consumed: User Clicks Link
    EmailVerificationToken --> Expired: 24 Hours Pass
    Consumed --> [*]
    Expired --> [*]
    
    [*] --> RefreshToken: User Logs In
    RefreshToken --> Rotated: User Refreshes
    RefreshToken --> Revoked: User Logs Out
    RefreshToken --> Revoked: Password Changed
    RefreshToken --> Expired: 30 Days Pass
    Rotated --> RefreshToken: New Token Created
    Revoked --> [*]
    Expired --> [*]
    
    [*] --> PasswordResetToken: User Requests Reset
    PasswordResetToken --> Consumed: User Resets Password
    PasswordResetToken --> Expired: 24 Hours Pass
    Consumed --> [*]
    Expired --> [*]
    
    [*] --> LaunchToken: Integration Launched
    LaunchToken --> Used: Frontend Calls Info Endpoint
    LaunchToken --> Expired: 5 Minutes Pass
    Used --> [*]
    Expired --> [*]
    
    [*] --> InvitationToken: Invitation Sent
    InvitationToken --> Accepted: User Signs Up
    InvitationToken --> Expired: 7 Days Pass
    Accepted --> [*]
    Expired --> [*]
```

### Table Size Estimation

Estimated table sizes and growth patterns:

```mermaid
graph LR
    subgraph "Small Tables"
        A[users<br/>~1-10K rows]
        B[accounts<br/>~1-5K rows]
        C[subscriptions<br/>~1-5K rows]
    end
    
    subgraph "Medium Tables"
        D[memberships<br/>~5-50K rows]
        E[schema_specifications<br/>~10-100K rows]
        F[app_credentials<br/>~5-20K rows]
        G[integrations<br/>~10-50K rows]
    end
    
    subgraph "High Volume Tables"
        H[refresh_tokens<br/>~50-500K rows<br/>Grows with active sessions]
        I[email_verifications<br/>~10-100K rows<br/>One per signup]
        J[password_resets<br/>~1-10K rows<br/>Infrequent]
        K[invitations<br/>~5-50K rows<br/>Grows with team growth]
        L[launch_tokens<br/>~100K-1M rows<br/>Grows with integration usage]
        M[webhook_events<br/>~10-100K rows<br/>One per Stripe event]
    end
    
    style H fill:#ffebee
    style L fill:#ffebee
```

### Query Pattern Diagram

Common query patterns and their performance:

```mermaid
graph TD
    subgraph "Fast Queries - Indexed"
        Q1[Find User by Email<br/>users.email UK<br/>O log n]
        Q2[Find Membership<br/>memberships account_id + user_id<br/>O log n]
        Q3[Validate Token<br/>token_hash UK<br/>O log n]
        Q4[List Account Schemas<br/>schema_specifications.account_id<br/>O n with index]
    end
    
    subgraph "Medium Queries - Join Required"
        Q5[Get User Memberships<br/>memberships.user_id + join accounts<br/>O n log n]
        Q6[Get Account Team<br/>memberships.account_id + join users<br/>O n log n]
        Q7[Get Integration Details<br/>integrations + join schema + credential<br/>O n log n]
    end
    
    subgraph "Slow Queries - Full Scan"
        Q8[Find All Active Users<br/>users.is_active<br/>O n - needs index]
        Q9[Search Schemas by Name<br/>schema_specifications.schema_name<br/>O n - needs index]
    end
    
    style Q1 fill:#c8e6c9
    style Q2 fill:#c8e6c9
    style Q3 fill:#c8e6c9
    style Q4 fill:#c8e6c9
    style Q5 fill:#fff9c4
    style Q6 fill:#fff9c4
    style Q7 fill:#fff9c4
    style Q8 fill:#ffcdd2
    style Q9 fill:#ffcdd2
```

### Role-Based Access Pattern

Shows how different roles access data:

```mermaid
graph TB
    subgraph "OWNER Role"
        O1[Full Access to All Schemas]
        O2[Full Access to All Integrations]
        O3[Manage Team Members]
        O4[Manage Subscriptions]
        O5[Create/Delete Credentials]
        O6[Rename Account]
    end
    
    subgraph "ADMIN Role"
        A1[Full Access to All Schemas]
        A2[Full Access to All Integrations]
        A3[Manage Team Members<br/>Cannot change OWNER]
        A4[Create/Delete Credentials]
        A5[Cannot manage subscriptions]
    end
    
    subgraph "MEMBER Role"
        M1[Access Only Assigned Schemas<br/>manage_schema_ids]
        M2[Access Only Related Integrations]
        M3[Create Integrations<br/>for assigned schemas]
        M4[View Credentials]
        M5[Cannot manage team]
    end
    
    subgraph "VIEWER Role"
        V1[View Only Assigned Schemas<br/>manage_schema_ids]
        V2[View Only Related Integrations]
        V3[Read-only access]
        V4[Cannot create/modify]
    end
    
    style O1 fill:#c8e6c9
    style O2 fill:#c8e6c9
    style A1 fill:#fff9c4
    style A2 fill:#fff9c4
    style M1 fill:#e1f5ff
    style M2 fill:#e1f5ff
    style V1 fill:#f3e5f5
    style V2 fill:#f3e5f5
```

### Database Access Flow

Shows the flow of data access through the application:

```mermaid
sequenceDiagram
    participant API
    participant Auth as Auth Layer
    participant DB as Database
    participant Cache as Cache (Future)
    
    API->>Auth: Request with Bearer Token
    Auth->>DB: Validate Token (refresh_tokens)
    Auth->>DB: Get User (users)
    Auth->>DB: Get Membership (memberships)
    Auth->>API: User + Account + Role
    
    API->>DB: Query Account Resources
    Note over DB: Filter by account_id<br/>Apply role-based filtering
    
    alt OWNER/ADMIN
        DB->>API: All Resources
    else MEMBER/VIEWER
        DB->>DB: Filter by manage_schema_ids
        DB->>API: Filtered Resources
    end
    
    API->>Cache: Store Result (Future)
    API->>API: Format Response
    API->>Client: Return Data
```

### Detailed Table Structures

#### users Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | User unique identifier |
| email | VARCHAR(320) | UNIQUE, NOT NULL, INDEXED | User email (username) |
| first_name | VARCHAR(120) | NULLABLE | User's first name |
| last_name | VARCHAR(120) | NULLABLE | User's last name |
| password_hash | VARCHAR(255) | NULLABLE | Hashed password (null for OAuth-only) |
| google_sub | VARCHAR(128) | UNIQUE, NULLABLE | Google OAuth subject ID |
| is_active | BOOLEAN | NOT NULL, DEFAULT FALSE | Account activation status |
| email_verified_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Email verification timestamp |
| created_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Account creation timestamp |

**Indexes**: `id` (PK), `email` (UNIQUE), `google_sub` (UNIQUE)

---

#### accounts Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Account unique identifier |
| name | VARCHAR(255) | NOT NULL | Account/workspace name |
| owner_user_id | UUID | FOREIGN KEY → users.id, NOT NULL, UNIQUE | Account owner user ID |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Account creation timestamp |

**Indexes**: `id` (PK), `owner_user_id` (UNIQUE FK)

**Unique Constraint**: One account per owner (`uq_account_owner`)

---

#### memberships Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Membership unique identifier |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL, INDEXED | Account ID |
| user_id | UUID | FOREIGN KEY → users.id, NOT NULL, INDEXED | User ID |
| role | ENUM | NOT NULL, DEFAULT 'MEMBER' | Role: OWNER, ADMIN, MEMBER, VIEWER |
| manage_schema_ids | JSONB | NULLABLE | Array of schema UUIDs (for MEMBER/VIEWER) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Membership creation timestamp |

**Indexes**: `id` (PK), `account_id` (FK), `user_id` (FK)

**Unique Constraint**: One membership per user-account pair (`uq_membership`)

---

#### invitations Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Invitation unique identifier |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL | Account ID |
| email | VARCHAR(320) | NOT NULL | Invitee email address |
| role | ENUM | NOT NULL, DEFAULT 'MEMBER' | Role to assign on acceptance |
| token_hash | VARCHAR(128) | UNIQUE, NOT NULL, INDEXED | SHA256 hash of invitation token |
| expires_at | TIMESTAMP | NOT NULL | Expiration timestamp |
| accepted_at | TIMESTAMP | NULLABLE | Acceptance timestamp (null = pending) |
| manage_schema_ids | JSONB | NULLABLE | Schema permissions to apply |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Invitation creation timestamp |

**Indexes**: `id` (PK), `token_hash` (UNIQUE)

---

#### refresh_tokens Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Token record identifier |
| user_id | UUID | FOREIGN KEY → users.id, NOT NULL | User ID |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL | Account ID |
| jti | VARCHAR(64) | NOT NULL, INDEXED | JWT ID (unique token identifier) |
| token_hash | VARCHAR(128) | UNIQUE, NOT NULL | SHA256 hash of refresh token |
| user_agent | VARCHAR(255) | NULLABLE | Browser/client user agent |
| ip | VARCHAR(64) | NULLABLE | Client IP address |
| expires_at | TIMESTAMP | NOT NULL | Token expiration timestamp |
| revoked_at | TIMESTAMP | NULLABLE | Revocation timestamp (null = active) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Token creation timestamp |

**Indexes**: `id` (PK), `jti` (INDEX), `token_hash` (UNIQUE)

---

#### schema_specifications Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Schema unique identifier |
| schema_name | VARCHAR | NOT NULL | Schema display name |
| description | VARCHAR | NULLABLE | Human-readable description |
| schema | JSONB | NOT NULL | Schema definition (columns array) |
| validators | JSONB | NOT NULL | Validation rules object |
| created_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Creation timestamp |
| updated_at | TIMESTAMP WITH TIME ZONE | NULLABLE, ON UPDATE NOW | Last update timestamp |
| deleted_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Soft delete timestamp |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL, INDEXED, CASCADE DELETE | Account ID |
| created_by_user_id | UUID | FOREIGN KEY → users.id, NULLABLE, INDEXED, SET NULL ON DELETE | Creator user ID |

**Indexes**: `id` (PK), `account_id` (FK), `created_by_user_id` (FK)

**Soft Delete**: Filter `deleted_at IS NULL` in queries

---

#### subscriptions Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Subscription unique identifier |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL, INDEXED, CASCADE DELETE | Account ID |
| stripe_customer_id | VARCHAR(255) | NULLABLE | Stripe customer ID |
| stripe_subscription_id | VARCHAR(255) | NULLABLE | Stripe subscription ID |
| plan | VARCHAR(64) | NOT NULL | Plan: 'FREE' or 'PRO' |
| status | VARCHAR(64) | NOT NULL | Canonical status (active, canceled, etc.) |
| raw_stripe_status | VARCHAR(64) | NULLABLE | Original Stripe status |
| last_stripe_event_id | VARCHAR(255) | NULLABLE | Last processed webhook event ID |
| current_period_end | TIMESTAMP WITH TIME ZONE | NULLABLE | End of current billing period |
| trial_ends_at | TIMESTAMP WITH TIME ZONE | NULLABLE | End of trial period |
| created_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Creation timestamp |

**Indexes**: `id` (PK), `account_id` (FK)

---

#### webhook_events Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Event record identifier |
| event_id | VARCHAR(255) | UNIQUE, NOT NULL, INDEXED | Stripe event ID |
| processed_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Processing timestamp |

**Indexes**: `id` (PK), `event_id` (UNIQUE)

**Purpose**: Idempotency tracking for Stripe webhooks

---

#### app_credentials Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Credential unique identifier |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL | Account ID |
| created_by | UUID | FOREIGN KEY → users.id, NULLABLE, SET NULL ON DELETE | Creator user ID |
| client_id | VARCHAR | UNIQUE, NOT NULL | Public client identifier |
| client_secret_hash | VARCHAR | NOT NULL | SHA256 hash of client secret |
| client_secret_expires_at | TIMESTAMP | NULLABLE | Secret expiration (null = never) |
| app_name | VARCHAR | NOT NULL | Human-friendly app name |
| authorized_js_origins | JSONB | NOT NULL | Array of allowed JavaScript origins |
| theme | JSONB | NULLABLE | Theme customization object |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Creation timestamp |
| revoked | BOOLEAN | NOT NULL, DEFAULT FALSE | Revocation flag |

**Indexes**: `id` (PK), `client_id` (UNIQUE)

**Unique Constraint**: Unique app name per account (`uq_app_credentials_account_app_name`)

---

#### integrations Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Integration unique identifier |
| account_id | UUID | FOREIGN KEY → accounts.id, NOT NULL | Account ID |
| created_by | UUID | FOREIGN KEY → users.id, NULLABLE, SET NULL ON DELETE | Creator user ID |
| name | VARCHAR | NOT NULL | Integration display name |
| description | VARCHAR | NULLABLE | Integration description |
| schema_id | UUID | FOREIGN KEY → schema_specifications.id, NOT NULL | Schema ID |
| credential_id | UUID | FOREIGN KEY → app_credentials.id, NOT NULL | API credential ID |
| redirect_url | VARCHAR | NULLABLE | Redirect URL for browser flows |
| api_endpoint | VARCHAR | NULLABLE | Backend API endpoint URL |
| api_headers | JSONB | NULLABLE | Static headers object |
| method | VARCHAR | NULLABLE | HTTP method (default: POST) |
| behavior | JSONB | NULLABLE | Behavior configuration flags |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Creation timestamp |
| active | BOOLEAN | NOT NULL, DEFAULT TRUE | Active status |
| usage | INTEGER | NOT NULL, DEFAULT 0 | Usage counter |

**Indexes**: `id` (PK)

---

#### email_verifications Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Verification record identifier |
| user_id | UUID | FOREIGN KEY → users.id, NOT NULL, INDEXED, CASCADE DELETE | User ID |
| token_hash | VARCHAR(128) | UNIQUE, NOT NULL | SHA256 hash of verification token |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Expiration timestamp (24 hours) |
| consumed_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Consumption timestamp |
| created_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Creation timestamp |

**Indexes**: `id` (PK), `token_hash` (UNIQUE), `user_id` (FK)

---

#### password_resets Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Reset record identifier |
| user_id | UUID | FOREIGN KEY → users.id, NOT NULL, INDEXED, CASCADE DELETE | User ID |
| token_hash | VARCHAR(128) | UNIQUE, NOT NULL | SHA256 hash of reset token |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Expiration timestamp (24 hours) |
| consumed_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Consumption timestamp |
| created_at | TIMESTAMP WITH TIME ZONE | NOT NULL, DEFAULT NOW | Creation timestamp |

**Indexes**: `id` (PK), `token_hash` (UNIQUE), `user_id` (FK)

---

#### launch_tokens Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Launch token identifier |
| token_hash | VARCHAR | UNIQUE, NOT NULL | SHA256 hash of launch token |
| integration_id | UUID | NOT NULL | Integration ID |
| credential_id | UUID | NOT NULL | Credential ID |
| account_id | UUID | NOT NULL | Account ID |
| expires_at | TIMESTAMP | NOT NULL | Expiration timestamp (5 minutes) |
| used | BOOLEAN | NOT NULL, DEFAULT FALSE | Usage flag (single-use) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Creation timestamp |

**Indexes**: `id` (PK), `token_hash` (UNIQUE)

---

### Foreign Key Constraints

#### Cascade Deletes

- `accounts` → `memberships`: CASCADE (delete account deletes memberships)
- `accounts` → `schema_specifications`: CASCADE
- `accounts` → `subscriptions`: CASCADE
- `accounts` → `app_credentials`: CASCADE (implicit via account deletion)
- `accounts` → `integrations`: CASCADE (implicit via account deletion)
- `accounts` → `invitations`: CASCADE (implicit via account deletion)
- `users` → `email_verifications`: CASCADE
- `users` → `password_resets`: CASCADE
- `users` → `refresh_tokens`: CASCADE
- `users` → `memberships`: CASCADE (via user deletion)

#### Set Null on Delete

- `users` → `schema_specifications.created_by_user_id`: SET NULL
- `users` → `app_credentials.created_by`: SET NULL
- `users` → `integrations.created_by`: SET NULL
- `users` → `accounts.owner_user_id`: Prevented (cannot delete account owner)

### Indexes

#### Primary Keys

All tables use UUID primary keys with indexes.

#### Foreign Key Indexes

- `users.email` (unique index)
- `users.google_sub` (unique index)
- `memberships.account_id` (indexed)
- `memberships.user_id` (indexed)
- `schema_specifications.account_id` (indexed)
- `schema_specifications.created_by_user_id` (indexed)
- `refresh_tokens.jti` (indexed)
- `refresh_tokens.token_hash` (unique index)
- `invitations.token_hash` (unique index)
- `email_verifications.token_hash` (unique index)
- `password_resets.token_hash` (unique index)
- `launch_tokens.token_hash` (unique index)
- `webhook_events.event_id` (unique index)

### Unique Constraints

- `users.email` - Unique email addresses
- `users.google_sub` - Unique Google OAuth subjects
- `accounts.owner_user_id` - One account per owner
- `memberships(account_id, user_id)` - One membership per user-account pair
- `app_credentials(account_id, app_name)` - Unique app names per account
- `app_credentials.client_id` - Unique client IDs
- `refresh_tokens.token_hash` - Unique refresh token hashes
- `invitations.token_hash` - Unique invitation tokens
- `email_verifications.token_hash` - Unique verification tokens
- `password_resets.token_hash` - Unique reset tokens
- `launch_tokens.token_hash` - Unique launch tokens
- `webhook_events.event_id` - Unique Stripe event IDs

## Migrations

### Alembic Setup

Migrations are managed using Alembic. Configuration is in `alembic.ini` and `alembic/env.py`.

### Migration Commands

#### Check Current Migration

```bash
alembic current
```

#### View Migration History

```bash
alembic history
```

#### Create New Migration

```bash
alembic revision --autogenerate -m "description of changes"
```

**Note**: Review generated migration before applying.

#### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific migration
alembic upgrade <revision_id>

# Apply next migration
alembic upgrade +1
```

#### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

### Migration Files

Migrations are stored in `alembic/versions/` directory.

**Naming Convention**: `{revision_id}_{description}.py`

**Example**: `1eebd5520f1f_create_schema_specifications.py`

### Migration Best Practices

1. **Review Auto-generated**: Always review auto-generated migrations
2. **Test Migrations**: Test migrations on development database first
3. **Backup Database**: Backup database before applying migrations
4. **One Change Per Migration**: Keep migrations focused
5. **Reversible Migrations**: Make migrations reversible when possible
6. **Data Migrations**: Handle data migrations separately if needed

### Common Migration Patterns

#### Adding a Column

```python
def upgrade():
    op.add_column('table_name',
        sa.Column('new_column', sa.String(), nullable=True)
    )

def downgrade():
    op.drop_column('table_name', 'new_column')
```

#### Adding Foreign Key

```python
def upgrade():
    op.create_foreign_key(
        'fk_name', 'child_table', 'parent_table',
        ['child_column'], ['parent_column'],
        ondelete='CASCADE'
    )

def downgrade():
    op.drop_constraint('fk_name', 'child_table', type_='foreignkey')
```

#### Adding Index

```python
def upgrade():
    op.create_index('ix_table_column', 'table_name', ['column'])

def downgrade():
    op.drop_index('ix_table_column', 'table_name')
```

## Query Optimization

### Index Usage

Ensure queries use indexes:

```python
# Good: Uses index on email
user = db.query(User).filter(User.email == email).first()

# Good: Uses index on account_id
schemas = db.query(SchemaSpecification).filter(
    SchemaSpecification.account_id == account_id
).all()
```

### Eager Loading

Use eager loading for relationships:

```python
# Load memberships with accounts
memberships = db.query(Membership).join(Account).filter(
    Membership.user_id == user.id
).all()
```

### Query Optimization Tips

1. **Use Indexes**: Ensure WHERE clauses use indexed columns
2. **Limit Results**: Use `.limit()` for large result sets
3. **Select Specific Columns**: Use `.with_entities()` to select only needed columns
4. **Avoid N+1 Queries**: Use `.join()` or eager loading
5. **Use Count Efficiently**: Use `func.count()` instead of loading all rows

### Example Optimized Queries

```python
# Count without loading all rows
count = db.query(func.count(SchemaSpecification.id)).filter(
    SchemaSpecification.account_id == account_id,
    SchemaSpecification.deleted_at == None
).scalar()

# Eager load relationships
memberships = (
    db.query(Membership, Account)
    .join(Account)
    .filter(Membership.user_id == user.id)
    .all()
)

# Use exists for existence checks
exists = db.query(
    db.query(User).filter(User.email == email).exists()
).scalar()
```

## Soft Deletes

### Implementation

Some models use soft deletes via `deleted_at` column:

- `schema_specifications.deleted_at`

### Querying Soft-Deleted Records

Always filter out soft-deleted records:

```python
# Active schemas only
schemas = db.query(SchemaSpecification).filter(
    SchemaSpecification.account_id == account_id,
    SchemaSpecification.deleted_at == None
).all()
```

### Soft Delete Benefits

1. **Data Recovery**: Can recover accidentally deleted data
2. **Audit Trail**: Maintains history of deletions
3. **Referential Integrity**: Maintains foreign key relationships
4. **Cascade Handling**: Prevents cascade delete issues

## JSONB Fields

### Usage

Several models use JSONB for flexible schema:

- `memberships.manage_schema_ids`: Array of UUID strings
- `schema_specifications.schema`: Schema definition object
- `schema_specifications.validators`: Validation rules object
- `integrations.behavior`: Behavior configuration object
- `app_credentials.authorized_js_origins`: Array of origin strings
- `app_credentials.theme`: Theme customization object
- `integrations.api_headers`: Headers object

### Querying JSONB

```python
# Check if array contains value
memberships = db.query(Membership).filter(
    Membership.manage_schema_ids.contains([schema_id])
).all()

# Query JSONB object
integrations = db.query(Integration).filter(
    Integration.behavior['require_all'].astext == 'true'
).all()
```

### JSONB Best Practices

1. **Index JSONB**: Create GIN indexes for frequently queried JSONB fields
2. **Validate Structure**: Validate JSON structure in application code
3. **Use Schemas**: Define expected structure in Pydantic schemas
4. **Avoid Deep Nesting**: Keep JSONB structure relatively flat

## Database Maintenance

### Regular Tasks

1. **Vacuum**: Run `VACUUM ANALYZE` regularly
2. **Index Maintenance**: Rebuild indexes if needed
3. **Statistics Update**: Keep statistics up to date
4. **Backup**: Regular database backups
5. **Monitor Performance**: Monitor slow queries

### Backup Strategy

**Development**:
- Manual backups before major changes
- Use pg_dump for backups

**Production**:
- Automated daily backups
- Point-in-time recovery (PITR) if available
- Test restore procedures regularly

### Monitoring

Monitor these metrics:

1. **Connection Pool**: Monitor active connections
2. **Query Performance**: Track slow queries
3. **Table Sizes**: Monitor table growth
4. **Index Usage**: Ensure indexes are being used
5. **Lock Contention**: Monitor for deadlocks

## Common Issues and Solutions

### Issue: Migration Fails

**Symptoms**: Migration fails with error

**Solutions**:
1. Check database connection
2. Verify DATABASE_URL is correct
3. Check for conflicting migrations
4. Review migration SQL for syntax errors
5. Rollback and fix migration

### Issue: Slow Queries

**Symptoms**: Queries take long time

**Solutions**:
1. Add indexes on frequently queried columns
2. Use EXPLAIN ANALYZE to identify bottlenecks
3. Optimize query structure
4. Consider denormalization for read-heavy queries
5. Use connection pooling

### Issue: Foreign Key Violations

**Symptoms**: Cannot delete record due to foreign key constraint

**Solutions**:
1. Delete child records first
2. Use CASCADE delete if appropriate
3. Set foreign key to NULL if using SET NULL
4. Check for orphaned records

### Issue: Unique Constraint Violations

**Symptoms**: Cannot insert duplicate unique value

**Solutions**:
1. Check for existing record before insert
2. Use upsert (INSERT ... ON CONFLICT)
3. Handle gracefully in application code
4. Validate uniqueness before insert

## Performance Tuning

### Connection Pooling

Configure connection pooling in `app/db/session.py`:

```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before use
    pool_size=10,        # Number of connections to maintain
    max_overflow=20      # Additional connections allowed
)
```

### Query Optimization

1. **Use Indexes**: Ensure all foreign keys and frequently queried columns are indexed
2. **Limit Results**: Always use `.limit()` for potentially large result sets
3. **Select Only Needed**: Use `.with_entities()` to select specific columns
4. **Avoid N+1**: Use joins or eager loading for relationships
5. **Use Aggregates**: Use SQL aggregates instead of loading all rows

### Database Configuration

Recommended PostgreSQL settings:

```sql
-- Increase shared buffers
shared_buffers = 256MB

-- Increase work memory for sorts
work_mem = 16MB

-- Enable query logging for slow queries
log_min_duration_statement = 1000  -- Log queries > 1 second
```

## Table Relationships (Textual Description)

This section describes all table relationships in plain English to help understand how data is connected.

### Core User and Account Relationships

**users → accounts (One-to-One)**
- One user can own exactly one account (via `accounts.owner_user_id`)
- Each account has exactly one owner user
- This is a unique relationship (one account per owner)
- When a user signs up, they automatically become the owner of a new account

**users → memberships (One-to-Many)**
- One user can have many memberships (can belong to multiple accounts/workspaces)
- Each membership links a user to an account with a specific role
- A user can be a member of multiple accounts simultaneously
- Each membership has a role: OWNER, ADMIN, MEMBER, or VIEWER

**accounts → memberships (One-to-Many)**
- One account can have many memberships (can have many team members)
- Each membership represents one user's access to that account
- When an account is deleted, all its memberships are automatically deleted (CASCADE)

**accounts → invitations (One-to-Many)**
- One account can send many invitations
- Each invitation is sent to an email address to join that account
- Invitations include the role the user will have when they accept
- When an account is deleted, all its invitations are automatically deleted (CASCADE)

### Authentication and Security Relationships

**users → refresh_tokens (One-to-Many)**
- One user can have many refresh tokens (multiple devices/sessions)
- Each refresh token is tied to a specific user and account
- Tokens are used to maintain user sessions across multiple devices
- When a user is deleted, all their refresh tokens are automatically deleted (CASCADE)

**users → email_verifications (One-to-Many)**
- One user can have many email verification records (if verification is resent)
- Each verification record contains a token to verify the user's email
- Only the most recent verification is typically valid
- When a user is deleted, all their verification records are automatically deleted (CASCADE)

**users → password_resets (One-to-Many)**
- One user can have many password reset records (multiple reset requests)
- Each reset record contains a token to reset the user's password
- Only the most recent reset token is typically valid
- When a user is deleted, all their password reset records are automatically deleted (CASCADE)

### Schema and Data Relationships

**accounts → schema_specifications (One-to-Many)**
- One account can have many schema specifications
- Each schema belongs to exactly one account
- Schemas define the structure of data for that account
- When an account is deleted, all its schemas are automatically deleted (CASCADE)

**users → schema_specifications (One-to-Many, Optional)**
- One user can create many schema specifications
- The `created_by_user_id` field tracks who created each schema
- This relationship is optional (nullable) - if a user is deleted, the schema remains but `created_by_user_id` is set to NULL (SET NULL on delete)
- This preserves data even if the creator leaves the account

**schema_specifications → integrations (One-to-Many)**
- One schema can be used by many integrations
- Each integration maps data to a specific schema
- Multiple integrations can use the same schema for different purposes
- If a schema is deleted (soft delete), related integrations may become invalid

### Integration and Credential Relationships

**accounts → app_credentials (One-to-Many)**
- One account can have many API credentials
- Each credential is used to authenticate API requests for that account
- Credentials are scoped to a specific account
- When an account is deleted, all its credentials are automatically deleted (CASCADE)

**users → app_credentials (One-to-Many, Optional)**
- One user can create many API credentials
- The `created_by` field tracks who created each credential
- This relationship is optional (nullable) - if a user is deleted, the credential remains but `created_by` is set to NULL (SET NULL on delete)

**app_credentials → integrations (One-to-Many)**
- One API credential can be used by many integrations
- Each integration uses a specific credential to authenticate API calls
- Multiple integrations can share the same credential
- If a credential is revoked, all integrations using it will fail

**app_credentials → launch_tokens (One-to-Many)**
- One API credential can generate many launch tokens
- Launch tokens are temporary tokens used to initialize integrations
- Each launch token is tied to a specific credential and integration
- Launch tokens expire after 5 minutes and are single-use

**accounts → integrations (One-to-Many)**
- One account can have many integrations
- Each integration belongs to exactly one account
- Integrations connect schemas to external APIs
- When an account is deleted, all its integrations are automatically deleted (CASCADE)

**users → integrations (One-to-Many, Optional)**
- One user can create many integrations
- The `created_by` field tracks who created each integration
- This relationship is optional (nullable) - if a user is deleted, the integration remains but `created_by` is set to NULL (SET NULL on delete)

**integrations → launch_tokens (One-to-Many)**
- One integration can have many launch tokens (multiple launches)
- Each launch token is generated when an integration is launched
- Launch tokens are temporary and expire quickly
- Each token can only be used once

### Billing Relationships

**accounts → subscriptions (One-to-One)**
- One account can have exactly one subscription
- Each subscription belongs to exactly one account
- Subscriptions track billing status and plan (FREE or PRO)
- When an account is deleted, its subscription is automatically deleted (CASCADE)

**webhook_events (Standalone)**
- Webhook events table is independent (no foreign keys)
- Used for idempotency tracking of Stripe webhook events
- Prevents processing the same Stripe event multiple times
- Each event ID is unique across all accounts

### Membership Role and Permissions

**memberships → schema_specifications (Many-to-Many via manage_schema_ids)**
- Memberships can have access to specific schemas via the `manage_schema_ids` JSONB field
- This is a many-to-many relationship stored as an array of schema UUIDs
- Only MEMBER and VIEWER roles use this field (OWNER and ADMIN have access to all schemas)
- When a schema is deleted, it should be removed from all `manage_schema_ids` arrays

**invitations → schema_specifications (Many-to-Many via manage_schema_ids)**
- Invitations can include specific schema permissions via the `manage_schema_ids` JSONB field
- When a user accepts an invitation, these permissions are copied to their membership
- This allows inviting users with limited schema access

### Summary of Relationship Types

**One-to-One Relationships:**
- users ↔ accounts (via owner_user_id)
- accounts ↔ subscriptions

**One-to-Many Relationships:**
- users → memberships
- users → refresh_tokens
- users → email_verifications
- users → password_resets
- users → schema_specifications (created_by)
- users → app_credentials (created_by)
- users → integrations (created_by)
- accounts → memberships
- accounts → invitations
- accounts → schema_specifications
- accounts → subscriptions
- accounts → app_credentials
- accounts → integrations
- schema_specifications → integrations
- app_credentials → integrations
- app_credentials → launch_tokens
- integrations → launch_tokens

**Many-to-Many Relationships (via JSONB arrays):**
- memberships ↔ schema_specifications (via manage_schema_ids)
- invitations ↔ schema_specifications (via manage_schema_ids)

**Cascade Delete Behavior:**
- Deleting a user deletes: memberships, refresh_tokens, email_verifications, password_resets
- Deleting an account deletes: memberships, schema_specifications, subscriptions, app_credentials, integrations, invitations
- Deleting a schema (soft delete) may invalidate related integrations

**Set Null on Delete Behavior:**
- Deleting a user sets to NULL: schema_specifications.created_by_user_id, app_credentials.created_by, integrations.created_by
- This preserves data while removing the reference to the deleted user

### Relationship Cardinality Quick Reference

| Parent Table | Child Table | Relationship | Delete Behavior |
|--------------|-------------|---------------|-----------------|
| users | accounts | One-to-One (owner) | Prevented (cannot delete owner) |
| users | memberships | One-to-Many | CASCADE |
| users | refresh_tokens | One-to-Many | CASCADE |
| users | email_verifications | One-to-Many | CASCADE |
| users | password_resets | One-to-Many | CASCADE |
| users | schema_specifications | One-to-Many (created_by) | SET NULL |
| users | app_credentials | One-to-Many (created_by) | SET NULL |
| users | integrations | One-to-Many (created_by) | SET NULL |
| accounts | memberships | One-to-Many | CASCADE |
| accounts | invitations | One-to-Many | CASCADE |
| accounts | schema_specifications | One-to-Many | CASCADE |
| accounts | subscriptions | One-to-One | CASCADE |
| accounts | app_credentials | One-to-Many | CASCADE |
| accounts | integrations | One-to-Many | CASCADE |
| schema_specifications | integrations | One-to-Many | None (soft delete) |
| app_credentials | integrations | One-to-Many | None |
| app_credentials | launch_tokens | One-to-Many | None |
| integrations | launch_tokens | One-to-Many | None |

## Best Practices

1. **Always Use Migrations**: Never modify schema manually
2. **Test Migrations**: Test migrations on development first
3. **Backup Before Migrations**: Always backup before applying migrations
4. **Use Transactions**: Wrap related operations in transactions
5. **Handle Errors**: Always handle database errors gracefully
6. **Use Indexes**: Index foreign keys and frequently queried columns
7. **Monitor Performance**: Monitor query performance regularly
8. **Use Soft Deletes**: Use soft deletes for important data
9. **Validate Data**: Validate data in application, not just database
10. **Document Schema**: Document schema changes in migration messages

