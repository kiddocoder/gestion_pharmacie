# PHARMATRACK-BI
## National Pharmaceutical Traceability Platform — Burundi
### Master Project Plan

---

> **Classification**: Government-Grade System  
> **Country**: République du Burundi  
> **Stack**: Django · DRF · PostgreSQL · Redis · Celery  
> **Architecture**: Multi-tenant ready · Regulatory-grade auditability · Movement-based stock  

---

## Table of Contents

1. [Vision & Objectives](#vision--objectives)
2. [Architecture Overview](#architecture-overview)
3. [App Module Map](#app-module-map)
4. [Phase Roadmap](#phase-roadmap)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [Key Design Decisions](#key-design-decisions)
7. [Geography — Burundi Subdivision](#geography--burundi-subdivision)
8. [Deployment Architecture](#deployment-architecture)
9. [Definition of Done Per Phase](#definition-of-done-per-phase)

---

## Vision & Objectives

**Mission**: Provide end-to-end digital traceability for every pharmaceutical product circulating in Burundi — from national import authorization to final dispensing at pharmacy or public health facility.

**Core Goals**:
- Eliminate counterfeit medicine by tracking every lot from import to patient
- Enforce authorized pricing across all private pharmacies
- Enable province-level inspection and infraction management
- Provide the Ministry of Health with real-time stock and expiry analytics
- Create an auditable, corruption-resistant financial trail

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API GATEWAY (Nginx)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │    Django REST Framework     │
              │    JWT Auth · RBAC · DRF     │
              └──────────────┬──────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     │                       │                       │
┌────▼─────┐         ┌───────▼──────┐        ┌──────▼──────┐
│  Business │         │  PostgreSQL  │        │    Redis    │
│  Services │         │  (Primary)  │        │  Cache+MQ   │
│  Layer    │         │             │        │             │
└────┬─────┘         └───────┬──────┘        └──────┬──────┘
     │                       │                       │
     │               ┌───────▼──────┐        ┌──────▼──────┐
     │               │  PgBouncer   │        │   Celery    │
     │               │ (Pool Proxy) │        │  Workers    │
     │               └──────────────┘        └─────────────┘
     │
┌────▼────────────────────────────────────────────────────────┐
│  Apps: core · users · geography · medicines · pharmacies    │
│        stock · b2b · public_sector · finance · inspection   │
│        analytics                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## App Module Map

| App | Responsibility | Key Models |
|-----|---------------|------------|
| `core` | Base models, mixins, audit log, shared utilities | `AuditLog`, `SoftDeleteMixin`, `TimestampMixin` |
| `users` | Auth, RBAC, OTP, device tracking | `User`, `Role`, `UserRole`, `OTPCode`, `DeviceToken` |
| `geography` | Administrative hierarchy seeded from JSON | `AdministrativeLevel` |
| `medicines` | National registry, lots, ATC codes | `NationalMedicine`, `NationalLot` |
| `pharmacies` | Private pharmacy lifecycle | `Pharmacy`, `PharmacyDocument` |
| `stock` | Movement-based stock engine | `StockMovement` |
| `b2b` | Wholesale orders between pharmacies | `B2BOrder`, `B2BOrderItem` |
| `public_sector` | Public health facilities, supply requests | `PublicFacility`, `SupplyRequest` |
| `finance` | Double-entry accounting | `Account`, `JournalEntry`, `JournalLine` |
| `inspection` | Field inspections, infractions, fines | `Inspection`, `Infraction`, `Fine` |
| `analytics` | Materialized views, alert queries | (DB views, no primary models) |

---

## Phase Roadmap

---

### PHASE 1 — Foundation
**Goal**: Working project skeleton with auth, RBAC, geography, and audit infrastructure.

**Deliverables**:

1. **Project Scaffold**
   - Django project with modular app structure (see App Module Map)
   - Split settings: `base.py`, `development.py`, `production.py`
   - `.env`-driven configuration via `python-decouple` or `django-environ`
   - Docker + docker-compose (Django + PostgreSQL + Redis)

2. **Custom User Model** (`users/`)
   - UUID primary key
   - Fields: `cin` (unique), `phone` (unique), `email` (unique), `status` (`PENDING|ACTIVE|SUSPENDED|REJECTED`), `administrative_level` (FK to geography)
   - Full audit fields: `created_at`, `updated_at`, `created_by`, `updated_by`
   - Custom `UserManager` with `create_user` / `create_superuser`

3. **RBAC System** (`users/`)
   - `Role` model: name, description, scope (`PRIVATE|PUBLIC|NATIONAL`)
   - `UserRole` model: user + role + optional `entity_id` (for scoped assignment)
   - Custom DRF permission classes: `HasRole`, `HasScopedRole`

4. **Administrative Hierarchy** (`geography/`)
   - Self-referencing `AdministrativeLevel` model
   - `level_type` choices: `PROVINCE`, `COMMUNE`, `ZONE`, `COLLINE`
   - `CheckConstraint` enforcing valid parent-child level combos
   - Management command: `python manage.py seed_geography` loads from Burundi JSON
   - Source: `https://github.com/mosiflow/burundi-new-subdivision-json`
   - Burundi new administrative structure: **18 Provinces** → Communes → Zones → Collines/Quartiers

5. **Audit Log** (`core/`)
   - `AuditLog` model with JSONB `old_values`/`new_values`
   - `AuditableMixin` to auto-capture on save/delete via signals
   - Stores: `actor`, `action`, `model_name`, `object_id`, `ip_address`, `timestamp`

6. **Authentication**
   - JWT access + refresh tokens (`djangorestframework-simplejwt`)
   - Refresh token rotation enabled
   - `OTPCode` model: user, code (hashed), expiry (5 min), purpose (`LOGIN|RESET|VERIFY`)
   - `DeviceToken` model: user, device fingerprint, last_seen, is_trusted, expiry (30 days)
   - Endpoints: `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/otp/verify`, `POST /v1/auth/logout`

7. **Admin Configuration**
   - `UserAdmin`: list_display (email, phone, cin, status, level), filters (status, role, province), search (email, phone, cin)
   - `AdministrativeLevelAdmin`: tree-like display with parent chain, filter by level_type
   - `AuditLogAdmin`: read-only, filter by action/model, date_hierarchy

**Acceptance Criteria**:
- [ ] `pytest` passes with >80% coverage on Phase 1 code
- [ ] `python manage.py seed_geography` loads all 18 provinces + children without error
- [ ] JWT login → access token → authenticated request flow works end-to-end
- [ ] AuditLog row created on every User create/update
- [ ] Admin site loads with proper fieldsets and filters

---

### PHASE 2 — National Medicine Registry
**Goal**: Authoritative registry of all medicines authorized to circulate in Burundi.

**Deliverables**:

1. **NationalMedicine** model
   - ATC code (World Health Organization ATC classification)
   - International Nonproprietary Name (INN)
   - Dosage form, strength, packaging
   - Authorized price (DecimalField)
   - `is_controlled` flag (narcotics, psychotropics)
   - `status`: `AUTHORIZED | BLOCKED`
   - Soft delete

2. **NationalLot** model
   - FK to `NationalMedicine`
   - Import batch number (unique per medicine)
   - Manufacturing date, expiry date
   - Quantity imported
   - `status`: `ACTIVE | BLOCKED | EXPIRED | RECALLED`
   - Auto-blocking: Celery task runs daily, sets `EXPIRED` for past-expiry lots

3. **Validation Rules**
   - Cannot create any stock movement for a `BLOCKED` or `EXPIRED` lot
   - Cannot authorize a lot for a `BLOCKED` medicine
   - Price override requires `NATIONAL_ADMIN` role

4. **DRF Endpoints**
   - `GET/POST /v1/medicines/`
   - `GET/PUT/PATCH /v1/medicines/{id}/`
   - `POST /v1/medicines/{id}/block/`
   - `GET/POST /v1/medicines/{id}/lots/`
   - `GET/PUT/PATCH /v1/lots/{id}/`
   - `POST /v1/lots/{id}/recall/`

5. **Admin**
   - Expiry alert: custom `list_display` column showing days-to-expiry with color coding
   - Filter lots by province (via stock linkage)
   - Batch action: mark lots as recalled

**Acceptance Criteria**:
- [ ] Celery beat task auto-expires lots daily
- [ ] StockMovement creation blocked on expired/blocked lot (enforced at service layer)
- [ ] ATC code format validated (regex)
- [ ] Admin shows red badge for lots expiring within 30 days

---

### PHASE 3 — Private Pharmacy System
**Goal**: Full lifecycle management of private pharmacies (wholesalers and retailers).

**Deliverables**:

1. **Pharmacy** model
   - Type: `WHOLESALER | RETAILER`
   - `national_code`: unique, auto-generated (format: `PH-PROV-XXXX`)
   - GPS coordinates (latitude, longitude)
   - FK to `AdministrativeLevel` (commune level)
   - `status`: `PENDING | APPROVED | SUSPENDED | ILLEGAL`
   - QR code: auto-generated on approval, stored in S3
   - Soft delete

2. **PharmacyDocument** model
   - FK to `Pharmacy`
   - `document_type`: `LICENSE | TAX_CLEARANCE | PHARMACIST_DIPLOMA | OTHER`
   - File upload (S3-backed)
   - `status`: `PENDING | APPROVED | REJECTED`
   - Expiry date

3. **Approval Workflow**
   - Status state machine: `PENDING → APPROVED | REJECTED`, `APPROVED → SUSPENDED`, `SUSPENDED → APPROVED | ILLEGAL`
   - Only `NATIONAL_ADMIN` or `INSPECTOR` with correct scope can approve/suspend
   - Every status transition logged to `AuditLog` with reason field

4. **QR Code Generation**
   - Triggered on `APPROVED` status transition
   - Encodes: `pharmacy_id`, `national_code`, `name`, `type`
   - Stored in S3; URL saved on model

5. **DRF Endpoints**
   - `GET/POST /v1/pharmacies/`
   - `GET/PUT/PATCH /v1/pharmacies/{id}/`
   - `POST /v1/pharmacies/{id}/approve/`
   - `POST /v1/pharmacies/{id}/suspend/`
   - `POST /v1/pharmacies/{id}/documents/`
   - `GET /v1/pharmacies/{id}/qr/`

**Acceptance Criteria**:
- [ ] QR code generated and accessible after approval
- [ ] State machine rejects invalid transitions with 400 + error code
- [ ] Documents required before approval (service-layer validation)
- [ ] Admin moderation queue shows all PENDING pharmacies with document status

---

### PHASE 4 — Stock Engine (Critical)
**Goal**: Movement-based, immutable, partition-ready stock tracking system.

**Design Principle**: Stock is NEVER stored as a balance. It is always computed as `SUM(inbound movements) - SUM(outbound movements)` for a given (entity, lot) pair.

**Deliverables**:

1. **StockMovement** model (INSERT ONLY — NEVER UPDATE OR DELETE)
   - `entity_type`: `PHARMACY | PUBLIC_FACILITY`
   - `entity_id`: UUID (FK resolved in application layer for partition flexibility)
   - `lot` FK to `NationalLot`
   - `movement_type`: `IMPORT | B2B_IN | B2B_OUT | SALE | RETURN | ADJUSTMENT | RECALL_REMOVAL`
   - `quantity`: PositiveIntegerField
   - `reference_id`: UUID (FK to source record: B2BOrder, InspectionFine, etc.)
   - `reference_type`: CharField (model name of source)
   - `created_by` FK to User
   - `created_at` (indexed, partition key)
   - **No `updated_at`** — immutable record

2. **Stock Aggregation**
   ```sql
   SELECT
       entity_type, entity_id, lot_id,
       SUM(CASE WHEN movement_type IN ('IMPORT','B2B_IN','RETURN') THEN quantity ELSE 0 END)
     - SUM(CASE WHEN movement_type IN ('B2B_OUT','SALE','RECALL_REMOVAL') THEN quantity ELSE 0 END)
     AS current_stock
   FROM stock_movement
   WHERE entity_type = %s AND entity_id = %s
   GROUP BY entity_type, entity_id, lot_id;
   ```

3. **Service Layer**
   - `StockService.get_balance(entity_type, entity_id, lot_id)` — returns current computed stock
   - `StockService.record_movement(...)` — validates, inserts, logs; raises `InsufficientStockError` on negative result
   - `StockService.process_b2b_transaction(order)` — atomic dual movement (OUT from seller, IN for buyer)
   - `StockService.process_retail_sale(pharmacy_id, lot_id, quantity, user)` — atomic single movement

4. **Negative Stock Prevention**
   - Before any outbound movement: `get_balance() >= quantity` enforced inside `atomic()`
   - `SELECT ... FOR UPDATE` on aggregate to prevent race conditions

5. **Partition Readiness**
   - Model designed with `created_at` as range partition key
   - Migration includes comment: `-- PARTITION BY RANGE (created_at)` for DBA reference
   - DB indexes: `(entity_type, entity_id, lot_id)`, `(lot_id, created_at)`, `(created_by, created_at)`

**Acceptance Criteria**:
- [ ] Concurrent sale test: two requests for last unit → only one succeeds, other gets 409
- [ ] No StockMovement row can be updated or deleted (DB-level: no update permission on table in app role)
- [ ] `get_balance()` returns correct result after 1000 mixed movements
- [ ] `process_b2b_transaction()` rolls back both movements if any error occurs

---

### PHASE 5 — B2B System
**Goal**: Regulated order flow between wholesalers and retailers with credit management.

**Deliverables**:

1. **B2BOrder** model
   - `seller` FK to Pharmacy (must be WHOLESALER)
   - `buyer` FK to Pharmacy (must be RETAILER)
   - `status`: `DRAFT → SUBMITTED → APPROVED → IN_TRANSIT → DELIVERED → CANCELLED | REJECTED`
   - `total_amount`, `credit_used`, `payment_status`
   - State machine enforced at service layer

2. **B2BOrderItem** model
   - FK to `B2BOrder`
   - FK to `NationalLot`
   - `quantity_ordered`, `quantity_delivered`
   - `unit_price` (must match `NationalMedicine.authorized_price` unless exception granted)

3. **Credit Management**
   - `PharmacyCredit` model: pharmacy, credit_limit, current_balance
   - On order approval: reserve credit atomically
   - On delivery: finalize and create `JournalEntry`
   - On cancellation: release reserved credit

4. **Dual Stock Movement** (via StockService)
   - On `DELIVERED`: atomic `B2B_OUT` for seller + `B2B_IN` for buyer
   - On `CANCELLED` after delivery: reversal movements

5. **DRF Endpoints**
   - `GET/POST /v1/b2b/orders/`
   - `GET/PUT/PATCH /v1/b2b/orders/{id}/`
   - `POST /v1/b2b/orders/{id}/submit/`
   - `POST /v1/b2b/orders/{id}/approve/`
   - `POST /v1/b2b/orders/{id}/deliver/`
   - `POST /v1/b2b/orders/{id}/cancel/`
   - `GET /v1/b2b/orders/{id}/movements/`

**Acceptance Criteria**:
- [ ] Full order lifecycle test passes with all state transitions
- [ ] Dual movement is atomic: if buyer stock insert fails, seller stock is rolled back
- [ ] Price exceeding authorized price rejected unless authorized exception
- [ ] Credit reservation prevents over-ordering in concurrent scenario

---

### PHASE 6 — Public Sector Circuit
**Goal**: Supply chain management for public health facilities (hospitals, health centers, dispensaries).

**Deliverables**:

1. **PublicFacility** model
   - Types: `NATIONAL_HOSPITAL | PROVINCIAL_HOSPITAL | HEALTH_CENTER | DISPENSARY`
   - FK to `AdministrativeLevel`
   - Managed by `PUBLIC_MANAGER` role

2. **SupplyRequest** model
   - Hierarchical: Dispensary requests from Health Center; Health Center from Provincial Hospital; etc.
   - `request_items`: JSON or related model
   - Approval chain: each level approves before passing up
   - Status: `DRAFT → SUBMITTED → PARTIALLY_APPROVED → APPROVED → FULFILLED | REJECTED`

3. **Public Stock**
   - Same `StockMovement` engine, `entity_type=PUBLIC_FACILITY`
   - `IMPORT` movements for direct national procurement
   - `B2B_IN` / `B2B_OUT` for inter-facility transfers

4. **DRF Endpoints**
   - `GET/POST /v1/public/facilities/`
   - `GET/POST /v1/public/facilities/{id}/requests/`
   - `POST /v1/public/requests/{id}/approve/`
   - `POST /v1/public/requests/{id}/fulfill/`

---

### PHASE 7 — Inspection System
**Goal**: Enable field inspectors to verify pharmacies, record infractions, and issue fines.

**Deliverables**:

1. **Inspection** model
   - FK to `Pharmacy` or `PublicFacility`
   - Inspector (FK to User, must have `INSPECTOR` role scoped to correct province)
   - `inspection_type`: `ROUTINE | COMPLAINT | FOLLOW_UP | SURPRISE`
   - `status`: `SCHEDULED → IN_PROGRESS → COMPLETED → DISPUTED`
   - `inspection_date`, `report_file` (S3)

2. **Infraction** model
   - FK to `Inspection`
   - `infraction_type`: (FK to configurable `InfractionType` catalogue)
   - `severity`: `MINOR | MAJOR | CRITICAL`
   - Description, evidence files (S3)

3. **Fine** model
   - FK to `Infraction`
   - Amount (auto-calculated from `InfractionType.base_fine` × severity multiplier)
   - `status`: `ISSUED → PAID | APPEALED | WAIVED`
   - Due date
   - On `PAID`: trigger `JournalEntry` in finance module

4. **QR Verification Endpoint**
   - `GET /v1/verify/pharmacy/{qr_token}/` — public endpoint (no auth required)
   - Returns: pharmacy name, status, license validity — no sensitive data

5. **DRF Endpoints**
   - `GET/POST /v1/inspections/`
   - `GET/PUT /v1/inspections/{id}/`
   - `POST /v1/inspections/{id}/infractions/`
   - `POST /v1/infractions/{id}/fine/`
   - `POST /v1/fines/{id}/pay/`
   - `GET /v1/verify/pharmacy/{qr_token}/`

---

### PHASE 8 — Finance (Double-Entry)
**Goal**: Immutable, balanced double-entry accounting for all financial flows.

**Deliverables**:

1. **Account** model
   - `account_type`: `ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE`
   - `account_code`: unique (e.g., `1010` for Cash)
   - FK to `Pharmacy` or `PublicFacility` (nullable for system accounts)

2. **JournalEntry** model
   - `entry_date`, `reference`, `description`
   - `status`: `DRAFT → POSTED` (POSTED = immutable)
   - `created_by`, `posted_by`, `posted_at`

3. **JournalLine** model
   - FK to `JournalEntry`
   - FK to `Account`
   - `debit` (Decimal), `credit` (Decimal)
   - **Constraint**: `debit > 0 XOR credit > 0` (never both)

4. **Balance Enforcement**
   - `CheckConstraint` on `JournalEntry`: `SUM(debit) == SUM(credit)` enforced at service layer with post-save assertion
   - Cannot post an unbalanced entry
   - Cannot modify or delete a `POSTED` entry — only reversal entries allowed

5. **Integration Points**
   - B2B delivery → auto `JournalEntry` for receivable/payable
   - Fine payment → auto `JournalEntry` for fine revenue
   - Pharmacy license fee → auto `JournalEntry`

---

### PHASE 9 — Analytics & Monitoring
**Goal**: Provide the Ministry of Health with actionable, real-time insights.

**Deliverables**:

1. **Materialized Views** (defined in migrations via `RunSQL`)
   - `mv_province_stock_summary`: current stock per province per medicine
   - `mv_expiry_alert_30days`: all lots expiring within 30 days, grouped by facility
   - `mv_pharmacy_sales_monthly`: monthly sales per pharmacy (for price compliance monitoring)

2. **Suspicious Pattern Detection**
   - Query: pharmacies selling above `NationalMedicine.authorized_price` in last 30 days
   - Query: lots with stock decreasing faster than national average (possible diversion)
   - Query: pharmacies with no stock movements in 90 days (ghost pharmacies)

3. **Scheduled Tasks** (Celery Beat)
   - Daily: refresh all materialized views
   - Daily: auto-expire lots past expiry date
   - Weekly: generate province stock reports → save to S3
   - Monthly: generate suspicious activity report → notify `NATIONAL_ADMIN`

4. **DRF Analytics Endpoints** (read-only, `NATIONAL_ADMIN` or `ANALYST` role)
   - `GET /v1/analytics/stock/province/`
   - `GET /v1/analytics/expiry-alerts/`
   - `GET /v1/analytics/suspicious-patterns/`
   - `GET /v1/analytics/sales-summary/`

---

## Data Flow Diagrams

### Medicine Traceability Flow
```
National Import
     │
     ▼
NationalLot (ACTIVE)
     │
     ▼
Wholesaler StockMovement (IMPORT)
     │
     ▼  B2BOrder (APPROVED → DELIVERED)
     ▼
Retailer StockMovement (B2B_IN)
     │
     ▼  Retail Sale
     ▼
StockMovement (SALE)
     │
     ▼
AuditLog entry at every step
```

### Stock Movement (Atomic B2B)
```
B2BService.process_delivery(order_id)
   │
   ├─ atomic() BEGIN
   │   ├─ StockService.get_balance(seller, lot) → check >= quantity
   │   ├─ StockMovement.insert(B2B_OUT, seller, lot, qty)
   │   ├─ StockMovement.insert(B2B_IN, buyer, lot, qty)
   │   ├─ B2BOrder.status = DELIVERED
   │   ├─ FinanceService.create_journal_entry(order)
   │   └─ AuditLog.write(actor, action, before/after)
   └─ atomic() COMMIT  (or full ROLLBACK on any error)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stock storage | Movement-based (no balance column) | Immutable, auditable, partition-friendly |
| PK type | UUID everywhere | No sequential ID exposure, multi-tenant safe |
| Delete strategy | Soft delete for all regulatory data | Legal requirement — data cannot be destroyed |
| Money type | `DecimalField(15,2)` | No floating point rounding errors |
| Admin framework | Default Django Admin | No external dependency risk for gov system |
| Auth | JWT + OTP + Device tracking | Defense-in-depth for sensitive platform |
| Geography seed | Management command from official JSON | Reproducible, version-controlled, official source |
| Partition key | `StockMovement.created_at` | Time-based queries dominate analytics patterns |

---

## Geography — Burundi Subdivision

The new administrative subdivision of Burundi (post-2022) is structured as:

```
République du Burundi
├── 18 Provinces
│   └── Communes (formerly Districts)
│       └── Zones
│           └── Collines (rural) / Quartiers (urban)
```

**Data Source**: `https://github.com/mosiflow/burundi-new-subdivision-json/blob/main/burundi-map.json`

**Seeding**:
```bash
python manage.py seed_geography
# Loads all levels from JSON
# Idempotent: safe to re-run (uses get_or_create)
# Reports counts per level type on completion
```

**Parent-Child Constraints** (enforced via `CheckConstraint`):
- `COMMUNE.parent.level_type == PROVINCE`
- `ZONE.parent.level_type == COMMUNE`
- `COLLINE.parent.level_type == ZONE`

---

## Deployment Architecture

```
                    Internet
                       │
               ┌───────▼────────┐
               │   Nginx (TLS)   │
               └───────┬────────┘
                       │
            ┌──────────▼──────────┐
            │  Gunicorn (Django)  │
            │  3 workers × 4     │
            └──────────┬──────────┘
                       │
         ┌─────────────┼──────────────┐
         │             │              │
┌────────▼───┐  ┌──────▼──────┐  ┌───▼─────────┐
│ PostgreSQL │  │    Redis     │  │  MinIO/S3   │
│ (Primary + │  │  (Cache+MQ) │  │  (Files)    │
│  Replica)  │  └──────┬──────┘  └─────────────┘
└────────────┘         │
               ┌───────▼─────────┐
               │  Celery Workers  │
               │  + Celery Beat   │
               └─────────────────┘
```

**Environment Variables Required** (never committed):
```
SECRET_KEY=
DATABASE_URL=
REDIS_URL=
AWS_S3_BUCKET=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
ALLOWED_HOSTS=
DEBUG=False
```

---

## Definition of Done Per Phase

A phase is **DONE** when all of the following are true:

- [ ] All models created with proper Meta, indexes, constraints, docstrings
- [ ] All migrations generated and committed (no pending changes)
- [ ] Service layer implemented with full atomic transaction coverage
- [ ] DRF serializers (read + write separated) implemented
- [ ] All endpoints documented with expected request/response shape
- [ ] Permission classes defined and applied to every ViewSet
- [ ] Django Admin configured with list_display, filters, search, fieldsets
- [ ] Unit tests written for all services (>80% coverage)
- [ ] Integration tests written for all endpoints
- [ ] AuditLog entries verified in tests for all write operations
- [ ] No `print()` statements, no bare `except:`, no `fields = '__all__'`
- [ ] `black`, `isort`, `flake8` pass with zero warnings
- [ ] Phase reviewed against `.cursor/rules` — zero violations

---

*Document maintained by the PHARMATRACK-BI development team.*  
*Last updated: 2026. For questions, contact the lead architect.*
