# Data Dictionary — YottaFlex AI Complaint Intelligence Platform

**Version**: 2.0.0  
**Generated**: 2026-10-29  
**Seed**: `20261022`  
**Scale**: Full (5,000 customers / 8,000 orders / 2,000 complaints / 6,000 messages)

---

## Overview

All data in this platform is **fully synthetic**, generated deterministically from seed `20261022`. No real customer, order, or complaint data is used. Refer to `docs/SOURCE_MANIFEST.md` for the complete synthetic data declaration.

### Timezone Convention
All `DateTime` fields are stored in **UTC**. ISO 8601 format with `+00:00` suffix.

### Numeric Precision
- All monetary amounts: `NUMERIC(10, 2)` — 2 decimal places, rounded half-up.
- Confidence scores: `FLOAT` — 0.0 to 1.0.
- Sentiment scores: `FLOAT` — −1.0 to 1.0.
- SLA hours: `FLOAT` — stored as fractional hours.

### ID Formats
| Entity | Format | Example |
|--------|--------|---------|
| Customer | `CUST-YYYY-NNNNNN` | `CUST-2026-000001` |
| Product | `PROD-YYYY-NNNNNN` | `PROD-2026-000001` |
| Order | `ORD-YYYY-NNNNNN` | `ORD-2026-000001` |
| OrderItem | `OIT-YYYY-NNNNNN-SS` | `OIT-2026-000001-01` |
| Complaint | `CMP-YYYY-NNNNNN` | `CMP-2026-000001` |
| Message | `MSG-YYYY-NNNNNN-SS` | `MSG-2026-000001-01` |
| Assignment | `ASN-CMP-YYYY-NNNNNN-NNN` | `ASN-CMP-2026-000001-001` |
| SLA Clock | `SLA-CMP-YYYY-NNNNNN` | `SLA-CMP-2026-000001` |
| Resolution | `RES-CMP-YYYY-NNNNNN` | `RES-CMP-2026-000001` |
| Survey | `SRV-CMP-YYYY-NNNNNN` | `SRV-CMP-2026-000001` |
| Team | `TEAM-NNN` | `TEAM-001` |
| Agent | `AGT-YYYY-NNNNNN` | `AGT-2026-000001` |

---

## Entity Reference

---

### 1. Customer

**Table**: `customers`  
**Record count** (full scale): 5,000  
**Description**: Synthetic customer accounts in the YottaFlex ecosystem.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key (autoincrement) |
| `customer_id` | VARCHAR(25) | NOT NULL | UQ | Business ID (`CUST-YYYY-NNNNNN`) |
| `first_name` | VARCHAR(100) | NOT NULL | — | Synthetic first name |
| `last_name` | VARCHAR(100) | NOT NULL | — | Synthetic last name |
| `email` | VARCHAR(255) | NOT NULL | UQ | Synthetic email, format: `name@domain.tld` |
| `phone` | VARCHAR(20) | NULL | — | Synthetic phone number |
| `address_line1` | VARCHAR(255) | NULL | — | Street address line 1 |
| `address_line2` | VARCHAR(255) | NULL | — | Street address line 2 |
| `city` | VARCHAR(100) | NULL | — | City name |
| `state` | VARCHAR(50) | NULL | — | State/region |
| `postal_code` | VARCHAR(20) | NULL | — | **String type** — preserves leading zeros (e.g., `01234`) |
| `country` | VARCHAR(50) | NOT NULL | — | Default: `US` |
| `vulnerability_flag` | BOOLEAN | NOT NULL | — | Synthetic vulnerability indicator; affects priority (PR-002) |
| `vulnerability_type` | VARCHAR(100) | NULL | — | Type: `elderly`, `financial_hardship`, `disabled`, etc. |
| `is_active` | BOOLEAN | NOT NULL | — | Account status |
| `account_tier` | VARCHAR(20) | NOT NULL | — | Values: `standard`, `premium`, `enterprise` |
| `loyalty_points` | INTEGER | NOT NULL | — | Synthetic loyalty balance |
| `is_synthetic` | BOOLEAN | NOT NULL | — | Always `True` — confirms synthetic origin |
| `created_at` | DATETIME | NOT NULL | — | Account creation timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | — | Last update timestamp (UTC) |

**Relationships**:
- One customer → many orders (`orders.customer_id_fk`)
- One customer → many complaints (`complaints.customer_id_fk`)

---

### 2. Product

**Table**: `products`  
**Record count** (full scale): 200  
**Description**: Synthetic product catalog items.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `product_id` | VARCHAR(25) | NOT NULL | UQ | Business ID (`PROD-YYYY-NNNNNN`) |
| `name` | VARCHAR(255) | NOT NULL | — | Product name |
| `description` | TEXT | NULL | — | Product description |
| `category` | VARCHAR(100) | NOT NULL | — | Product category (e.g., `Electronics`, `Clothing`) |
| `subcategory` | VARCHAR(100) | NULL | — | Product subcategory |
| `brand` | VARCHAR(100) | NULL | — | Brand name |
| `sku` | VARCHAR(50) | NOT NULL | UQ | Stock Keeping Unit — unique per product |
| `unit_price` | NUMERIC(10,2) | NOT NULL | — | List price in USD. Constraint: `>= 0` |
| `currency` | VARCHAR(5) | NOT NULL | — | Default: `USD` |
| `stock_quantity` | INTEGER | NOT NULL | — | Synthetic inventory count |
| `is_active` | BOOLEAN | NOT NULL | — | Product availability |
| `is_safety_flagged` | BOOLEAN | NOT NULL | — | Safety-risk indicator — complaints on this product are P1 |
| `created_at` | DATETIME | NOT NULL | — | UTC |
| `updated_at` | DATETIME | NOT NULL | — | UTC |

**Relationships**:
- One product → many order items (`order_items.product_id_fk`)
- One product → many complaints (`complaints.product_id_fk`)

---

### 3. Order

**Table**: `orders`  
**Record count** (full scale): 8,000  
**Description**: Customer purchase orders. Each order may contain multiple products via `order_items`.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `order_id` | VARCHAR(25) | NOT NULL | UQ | Business ID (`ORD-YYYY-NNNNNN`) |
| `customer_id_fk` | INTEGER | NOT NULL | FK → customers.id | Owning customer |
| `product_id_fk` | INTEGER | NULL | FK → products.id | **Primary product** — the highest-value item in the order (for backward compatibility) |
| `quantity` | INTEGER | NOT NULL | — | Total quantity across all items. Constraint: `> 0` |
| `unit_price` | NUMERIC(10,2) | NOT NULL | — | Unit price of primary product |
| `discount_amount` | NUMERIC(10,2) | NOT NULL | — | Total discount across all items. Default: `0.00` |
| `total_amount` | NUMERIC(10,2) | NOT NULL | — | **Derived**: `SUM(order_items.line_total)`. Must equal sum of all item line totals. |
| `currency` | VARCHAR(5) | NOT NULL | — | Default: `USD` |
| `status` | VARCHAR(30) | NOT NULL | — | Values: `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`, `returned` |
| `shipping_address` | TEXT | NULL | — | Delivery address JSON |
| `tracking_number` | VARCHAR(100) | NULL | — | Carrier tracking reference |
| `ordered_at` | DATETIME | NOT NULL | — | Order placement timestamp (UTC) |
| `shipped_at` | DATETIME | NULL | — | Shipment dispatch timestamp (UTC). Must be ≥ `ordered_at` |
| `delivered_at` | DATETIME | NULL | — | Delivery confirmation timestamp (UTC). Must be ≥ `shipped_at` |
| `created_at` | DATETIME | NOT NULL | — | Record creation timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | — | Last update timestamp (UTC) |

**Integrity Rule**: `total_amount = SUM(order_items.line_total)` for all items linked to this order.

**Relationships**:
- One order → many order items (`order_items.order_id_fk`)
- One order → many complaints (`complaints.order_id_fk`)

---

### 4. OrderItem *(bridge table)*

**Table**: `order_items`  
**Record count** (full scale): ~11,240 (avg. 1.4 items/order)  
**Description**: Normalized line items in an order — implements the many-to-many relationship between orders and products.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `order_item_id` | VARCHAR(30) | NOT NULL | UQ | Business ID (`OIT-YYYY-NNNNNN-SS`) |
| `order_id_fk` | INTEGER | NOT NULL | FK → orders.id (CASCADE) | Parent order |
| `product_id_fk` | INTEGER | NOT NULL | FK → products.id | Product in this line |
| `quantity` | INTEGER | NOT NULL | — | Line item quantity. Constraint: `> 0` |
| `unit_price` | NUMERIC(10,2) | NOT NULL | — | Price per unit at time of order. Constraint: `>= 0` |
| `discount_amount` | NUMERIC(10,2) | NOT NULL | — | Discount applied to this line. Default: `0.00` |
| `line_total` | NUMERIC(10,2) | NOT NULL | — | **Derived**: `quantity * unit_price - discount_amount`. Constraint: `>= 0` |
| `created_at` | DATETIME | NOT NULL | — | UTC |

**Arithmetic Rule**: `line_total = quantity * unit_price - discount_amount` (enforced in generator and validated by `order_items_arithmetic_consistency`).

---

### 5. Complaint

**Table**: `complaints`  
**Record count** (full scale): 2,000  
**Description**: Core complaint records submitted by customers.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `complaint_id` | VARCHAR(25) | NOT NULL | UQ | Business ID (`CMP-YYYY-NNNNNN`) |
| `customer_id_fk` | INTEGER | NULL | FK → customers.id | Owning customer. Nullable to support `COMPLAINT_WITHOUT_CUSTOMER` anomaly injection. |
| `order_id_fk` | INTEGER | NULL | FK → orders.id | Referenced order. When set, `orders.customer_id_fk` MUST equal `complaints.customer_id_fk`. |
| `category_id_fk` | INTEGER | NULL | FK → categories.id | Complaint category |
| `product_id_fk` | INTEGER | NULL | FK → products.id | Product linked to this complaint. When `order_id_fk` is set, product must be in that order's items (or explicitly documented exception). |
| `subject` | VARCHAR(500) | NOT NULL | — | Short complaint subject line |
| `description` | TEXT | NOT NULL | — | Full complaint text |
| `channel` | VARCHAR(30) | NOT NULL | — | Values: `email`, `phone`, `web`, `chat`, `social_media`, `in_store` |
| `status` | VARCHAR(30) | NOT NULL | — | Values: `open`, `in_progress`, `pending_customer`, `escalated`, `resolved`, `closed`, `reopened` |
| `priority` | VARCHAR(5) | NOT NULL | — | Values: `P1`, `P2`, `P3`, `P4` |
| `category_code` | VARCHAR(50) | NULL | — | Category code mirror for query performance |
| `classification_confidence` | FLOAT | NULL | — | Classifier confidence (0.0–1.0) |
| `classification_evidence` | TEXT | NULL | — | JSON: matched keywords and evidence |
| `classification_rule_id` | VARCHAR(20) | NULL | — | Classifier rule ID |
| `classification_rule_version` | VARCHAR(20) | NULL | — | Classifier rule version |
| `priority_rule_applied` | VARCHAR(20) | NULL | — | Priority rule ID (e.g., `PR-001`) |
| `priority_explanation` | TEXT | NULL | — | Human-readable priority rationale |
| `sentiment` | VARCHAR(20) | NOT NULL | — | Values: `positive`, `neutral`, `negative` |
| `sentiment_score` | FLOAT | NULL | — | −1.0 (very negative) to 1.0 (very positive) |
| `is_safety_incident` | BOOLEAN | NOT NULL | — | True if safety-risk category. Requires `priority = P1`. |
| `is_refund_pending` | BOOLEAN | NOT NULL | — | Refund status flag |
| `is_reopened` | BOOLEAN | NOT NULL | — | True if complaint was previously resolved and reopened |
| `reopen_count` | INTEGER | NOT NULL | — | Number of times reopened. Default: `0` |
| `is_escalated` | BOOLEAN | NOT NULL | — | True if escalated to higher-tier support |
| `escalation_reason` | TEXT | NULL | — | Reason for escalation |
| `is_anomaly` | BOOLEAN | NOT NULL | — | True if record was modified by anomaly injection (NOT present in clean baseline) |
| `anomaly_id` | VARCHAR(50) | NULL | — | Anomaly identifier (injection-layer only; not exported in clean baseline) |
| `anomaly_type` | VARCHAR(100) | NULL | — | Anomaly type (injection-layer only) |
| `created_at` | DATETIME | NOT NULL | — | Complaint submission timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | — | Last update timestamp (UTC) |
| `resolved_at` | DATETIME | NULL | — | Resolution timestamp. Must be ≥ `created_at` if set. |
| `closed_at` | DATETIME | NULL | — | Closure timestamp. Must be ≥ `resolved_at` if set. |
| `first_response_at` | DATETIME | NULL | — | First agent response timestamp. Must be ≥ `created_at` if set. |

**Priority Rules**:
| Rule | Condition | Priority |
|------|-----------|----------|
| PR-001 | Safety incident (`is_safety_incident = True`) | **P1** (immutable) |
| PR-002 | Vulnerable customer + negative sentiment | P1 |
| PR-003 | Order value > $500 + negative sentiment | P2 |
| PR-004 | Recurrent customer (≥ 3 prior complaints) | Upgrade 1 level |
| PR-005 | Order value $200–$500 + negative sentiment | P3 |
| PR-006 | Standard negative sentiment | P3 |
| PR-007 | Non-negative sentiment (general inquiry) | **P4** |

---

### 6. ComplaintMessage

**Table**: `complaint_messages`  
**Record count** (full scale): 6,000 exactly  
**Description**: Message thread entries for each complaint. Variable count per complaint (1–7 messages), total always equals 6,000.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `message_id` | VARCHAR(30) | NOT NULL | UQ | Business ID (`MSG-YYYY-NNNNNN-SS`) |
| `complaint_id_fk` | INTEGER | NOT NULL | FK → complaints.id | Parent complaint |
| `message_type` | VARCHAR(30) | NOT NULL | — | Values: `customer_message`, `agent_response`, `internal_note`, `resolution_update` |
| `sender_type` | VARCHAR(20) | NOT NULL | — | Values: `customer`, `agent`, `system` |
| `sender_id` | VARCHAR(50) | NULL | — | Customer ID or Agent ID |
| `sender_name` | VARCHAR(150) | NULL | — | Display name |
| `body` | TEXT | NOT NULL | — | Message content |
| `is_customer_visible` | BOOLEAN | NOT NULL | — | Whether customer can see this message |
| `channel` | VARCHAR(30) | NOT NULL | — | Matches complaint channel |
| `delivery_status` | VARCHAR(20) | NOT NULL | — | Values: `pending`, `delivered`, `failed` |
| `sequence_number` | INTEGER | NOT NULL | — | Message order within complaint thread |
| `sent_at` | DATETIME | NOT NULL | — | Message sent timestamp (UTC). Must be ≥ complaint `created_at`. |
| `created_at` | DATETIME | NOT NULL | — | Record creation timestamp (UTC) |
| `is_anomaly` | BOOLEAN | NOT NULL | — | Anomaly injection flag |
| `anomaly_id` | VARCHAR(50) | NULL | — | Anomaly identifier |

---

### 7. Category

**Table**: `categories`  
**Record count**: 10 (fixed)  
**Description**: Complaint classification categories.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `code` | VARCHAR(50) | NOT NULL | UQ | Category code (e.g., `PRODUCT_SAFETY`, `REFUND`) |
| `name` | VARCHAR(100) | NOT NULL | — | Human-readable name |
| `description` | TEXT | NULL | — | Category description |
| `keywords` | TEXT | NOT NULL | — | JSON array of classification keywords |
| `safety_risk` | BOOLEAN | NOT NULL | — | If `True`, complaints in this category are forced to P1 |
| `is_active` | BOOLEAN | NOT NULL | — | Whether category is in use |
| `config_version` | VARCHAR(20) | NOT NULL | — | Rule version |
| `created_at` | DATETIME | NOT NULL | — | UTC |

**Defined categories**:
`PRODUCT_SAFETY`, `BILLING_DISPUTE`, `REFUND`, `DELIVERY_ISSUE`, `MISSING_ORDER`, `PRODUCT_QUALITY`, `DAMAGED_PRODUCT`, `WRONG_ITEM`, `CUSTOMER_SERVICE`, `OTHER`

---

### 8. PriorityRule

**Table**: `priority_rules`  
**Record count**: 7 (PR-001 through PR-007)  
**Description**: Business rules for priority assignment.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `rule_id` | VARCHAR(20) | NOT NULL | UQ | Rule identifier (e.g., `PR-001`) |
| `name` | VARCHAR(100) | NOT NULL | — | Rule name |
| `description` | TEXT | NOT NULL | — | Rule description |
| `priority_code` | VARCHAR(5) | NULL | — | Target priority (`P1`–`P4`) or `NULL` if upgrade |
| `priority_upgrade` | INTEGER | NULL | — | Levels to upgrade (used for PR-004 recurrence rule) |
| `condition` | TEXT | NOT NULL | — | YAML/human-readable condition |
| `precedence` | INTEGER | NOT NULL | — | Rule evaluation order (lower = higher precedence) |
| `is_active` | BOOLEAN | NOT NULL | — | Rule status |
| `config_version` | VARCHAR(20) | NOT NULL | — | Version |
| `effective_date` | VARCHAR(10) | NOT NULL | — | ISO date string |

---

### 9. Assignment

**Table**: `assignments`  
**Record count** (full scale): 2,000  
**Description**: Maps complaints to support teams and agents.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `assignment_id` | VARCHAR(40) | NOT NULL | UQ | Business ID |
| `complaint_id_fk` | INTEGER | NOT NULL | FK → complaints.id | Complaint being assigned |
| `team_id_fk` | INTEGER | NULL | FK → teams.id | Assigned team |
| `agent_id_fk` | INTEGER | NULL | FK → agents.id | Assigned agent |
| `assignment_type` | VARCHAR(30) | NOT NULL | — | Values: `initial`, `reassignment`, `escalation` |
| `assigned_by` | VARCHAR(50) | NOT NULL | — | Assigning actor (`system`, agent ID) |
| `reason` | TEXT | NULL | — | Assignment reason |
| `rule_applied` | VARCHAR(50) | NULL | — | Assignment rule ID |
| `is_current` | BOOLEAN | NOT NULL | — | True for the active assignment. Constraint: at most 1 `is_current=True` per complaint (clean data) |
| `assigned_at` | DATETIME | NOT NULL | — | UTC |

---

### 10. SLAClock

**Table**: `sla_clocks`  
**Record count** (full scale): 2,000  
**Description**: SLA tracking record per complaint. One-to-one with complaints.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `sla_id` | VARCHAR(40) | NOT NULL | UQ | Business ID (`SLA-CMP-YYYY-NNNNNN`) |
| `complaint_id_fk` | INTEGER | NOT NULL | FK → complaints.id (UQ) | Parent complaint |
| `priority` | VARCHAR(5) | NOT NULL | — | Complaint priority at SLA creation |
| `resolution_hours` | FLOAT | NOT NULL | — | Target resolution time in hours (from SLA policy). Constraint: `> 0` |
| `first_response_hours` | FLOAT | NOT NULL | — | Target first-response time in hours |
| `escalation_hours` | FLOAT | NOT NULL | — | Hours until escalation threshold |
| `start_time` | DATETIME | NOT NULL | — | SLA clock start (= complaint `created_at`) |
| `original_deadline` | DATETIME | NOT NULL | — | `start_time + resolution_hours` |
| `current_deadline` | DATETIME | NOT NULL | — | `original_deadline + accumulated_paused_hours` |
| `first_response_deadline` | DATETIME | NOT NULL | — | `start_time + first_response_hours` |
| `escalation_threshold_time` | DATETIME | NOT NULL | — | `start_time + escalation_hours` |
| `accumulated_paused_hours` | FLOAT | NOT NULL | — | Total hours clock was paused. Constraint: `>= 0` |
| `last_paused_at` | DATETIME | NULL | — | Timestamp when clock was last paused |
| `status` | VARCHAR(20) | NOT NULL | — | Values: `running`, `paused`, `breached`, `completed` |
| `is_breached` | BOOLEAN | NOT NULL | — | True if `resolved_at > current_deadline` |
| `breached_at` | DATETIME | NULL | — | Timestamp when breach was detected |
| `is_escalated` | BOOLEAN | NOT NULL | — | True if escalation threshold was crossed |
| `escalated_at` | DATETIME | NULL | — | Escalation timestamp |
| `first_response_met` | BOOLEAN | NULL | — | Whether first response deadline was met |
| `completed_at` | DATETIME | NULL | — | SLA completion timestamp (= resolution time) |
| `deadline_change_reason` | TEXT | NULL | — | Reason if deadline was extended |
| `is_anomaly` | BOOLEAN | NOT NULL | — | Anomaly injection flag |
| `anomaly_id` | VARCHAR(50) | NULL | — | Anomaly identifier |
| `config_version` | VARCHAR(20) | NOT NULL | — | SLA config version |
| `created_at` | DATETIME | NOT NULL | — | UTC |
| `updated_at` | DATETIME | NOT NULL | — | UTC |

**SLA Event Types** (in `sla_events` table):
- `created` — Clock started
- `paused` — Clock paused (e.g., awaiting customer)
- `resumed` — Clock resumed after pause
- `escalated` — Escalation threshold crossed
- `breached` — SLA deadline missed
- `completed` — Complaint resolved within SLA
- `deadline_extended` — Deadline manually extended

---

### 11. Resolution

**Table**: `resolutions`  
**Record count** (full scale): ~1,081  
**Description**: Formal resolution records for resolved/closed complaints.

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `resolution_id` | VARCHAR(30) | NOT NULL | UQ | Business ID |
| `complaint_id_fk` | INTEGER | NOT NULL | FK → complaints.id | Resolved complaint |
| `resolution_type` | VARCHAR(50) | NOT NULL | — | Values: `refund_issued`, `replacement_sent`, `apology_credit`, `resolved_no_action`, `investigation_closed` |
| `description` | TEXT | NOT NULL | — | Resolution description |
| `refund_amount` | NUMERIC(10,2) | NULL | — | Refund amount (USD). Only set when `resolution_type = refund_issued` |
| `refund_currency` | VARCHAR(5) | NULL | — | Currency code. Default: `USD` if refund present |
| `refund_approved` | BOOLEAN | NULL | — | Refund approval status |
| `refund_processed_at` | DATETIME | NULL | — | Refund processing timestamp (UTC) |
| `resolved_by_agent_id` | VARCHAR(50) | NULL | — | Agent ID who resolved |
| `resolved_by_team_id` | VARCHAR(20) | NULL | — | Team code |
| `is_superseded` | BOOLEAN | NOT NULL | — | True if complaint was later reopened (resolution invalidated) |
| `resolved_at` | DATETIME | NOT NULL | — | Resolution timestamp (UTC) |
| `created_at` | DATETIME | NOT NULL | — | Record creation timestamp (UTC) |

---

### 12. Survey

**Table**: `surveys`  
**Record count** (full scale): ~368  
**Description**: Customer satisfaction surveys. Only generated for closed complaints (60% response rate).

| Field | Type | Nullable | Key | Description |
|-------|------|----------|-----|-------------|
| `id` | INTEGER | NOT NULL | PK | Internal surrogate key |
| `survey_id` | VARCHAR(30) | NOT NULL | UQ | Business ID |
| `complaint_id_fk` | INTEGER | NOT NULL | FK → complaints.id | Surveyed complaint |
| `rating` | INTEGER | NOT NULL | — | Rating 1–5. Weights: 1→5%, 2→10%, 3→20%, 4→35%, 5→30% |
| `feedback` | TEXT | NULL | — | Optional text feedback (60% have feedback) |
| `submitted_by` | VARCHAR(50) | NULL | — | Customer ID |
| `submitted_before_closure` | BOOLEAN | NOT NULL | — | **Anomaly flag**: True only for injected anomalies — clean data always False |
| `is_anomaly` | BOOLEAN | NOT NULL | — | Anomaly injection flag |
| `anomaly_id` | VARCHAR(50) | NULL | — | Anomaly identifier |
| `submitted_at` | DATETIME | NOT NULL | — | Survey submission timestamp (UTC). Must be ≥ complaint `closed_at` in clean data |
| `created_at` | DATETIME | NOT NULL | — | Record creation timestamp (UTC) |

---

## Anomaly Framework

### Clean Baseline vs. Anomaly Injection

| Mode | Data | Anomaly flags | Ground truth |
|------|------|--------------|--------------|
| **Clean baseline** | `is_anomaly = False` for all records | Not set | Not generated |
| **Anomaly injection** | Selected records mutated | `is_anomaly = True`, `anomaly_id` set | Saved to `ground_truth.csv`/`ground_truth.json` |

### Six Canonical Anomaly Types

| Code | Description | Injected table |
|------|-------------|----------------|
| `PRIORITY_MISMATCH` | Safety complaint assigned P3/P4 instead of P1 | `complaints` |
| `SLA_BACKDATED` | SLA deadline set before complaint creation | `sla_clocks` |
| `SURVEY_BEFORE_CLOSURE` | Survey submitted on open/unresolved complaint | `surveys` |
| `DUPLICATE_ASSIGNMENT` | Two concurrent `is_current=True` assignments | `assignments` |
| `MISSING_STATUS_EVENT` | Complaint lacks its initial `open` status event | `complaint_status_events` |
| `REFUND_WITHOUT_RESOLUTION` | Refund recorded in status event but no Resolution record | `resolutions` |

### Detector Independence Rule

The `AnomalyDetector` class in `backend/app/anomaly/detector.py` **never reads** `ground_truth.csv`, `ground_truth.json`, or any evaluation metadata. It detects anomalies purely from database state. Ground-truth comparison is performed only by the evaluation layer after detection completes.

---

## Export Schema

### Public Export Fields
The following fields are included in CSV/JSON exports but internal fields (`is_anomaly`, `anomaly_id`, `anomaly_type`) are included for transparency in the anomaly injection exports but not present in the clean baseline exports from the generator.

### Baseline Export Files
| File | Entity | Format |
|------|--------|--------|
| `csv/customers.csv` | Customer | CSV |
| `csv/products.csv` | Product | CSV |
| `csv/orders.csv` | Order | CSV |
| `csv/order_items.csv` | OrderItem | CSV |
| `csv/complaints.csv` | Complaint | CSV |
| `csv/messages.csv` | ComplaintMessage | CSV |
| `csv/assignments.csv` | Assignment | CSV |
| `csv/sla_clocks.csv` | SLAClock | CSV |
| `csv/sla_events.csv` | SLAEvent | CSV |
| `csv/resolutions.csv` | Resolution | CSV |
| `csv/surveys.csv` | Survey | CSV |
| `csv/status_events.csv` | ComplaintStatusEvent | CSV |
| `csv/complaint_relationships.csv` | ComplaintRelationship | CSV |
| `csv/categories.csv` | Category | CSV |
| `csv/priority_rules.csv` | PriorityRule | CSV |
| `csv/teams.csv` | Team | CSV |
| `csv/agents.csv` | Agent | CSV |
| `json/*.json` | All entities | JSON |
| `sql/complaint_intelligence_dump.sql` | All tables | SQL |

