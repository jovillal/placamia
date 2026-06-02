# Semantic Inventory — Initial Draft

(Discovery Phase / Non-Canonical)

This document is intended to capture the meaning of the provider workbook before any ingestion, normalization, or database modeling decisions are made.

The goal is to preserve:
- provider mental model
- business semantics
- compliance logic
- implicit workflow assumptions
before translating them into PlacamIA domain concepts.

This is a discovery artifact, not a final architecture document.

## Path A Interpretation

PlacamIA has selected Path A for MVP: direct checkout for fully parametrizable,
backend-priceable catalog items. The workbook should not be treated as an MVP
catalog, pricing table, inventory source, or checkout authority.

For MVP, the workbook is useful only as background for future curated kits,
safe recommendation language, and possible compliance metadata. Any
workbook-derived recommendation must be validated with Relieves and reviewed for
legal/compliance risk before becoming product behavior.

---

# Source Description
## Primary Source

Workbook:

- NSR10 K2 x Señalización v3.xlsx

Source owner:

- Relieves de Colombia

Observed purpose:

- compliance-oriented signage recommendation matrix
- regulatory/business classification support
- advisory workflow support for customer compliance needs

Observed characteristics:

- heavily compliance-oriented
- regulation-driven grouping
- appears recommendation-centric rather than catalog-centric
- organized around occupancy/use contexts

Confidence:

- Medium

Reason:
- The workbook has not yet been validated by the provider experts.

---

# Initial Core Discovery

The workbook does NOT currently appear to behave as:

- a product catalog
- a pricing table
- an inventory database
- a manufacturing matrix

Instead, it appears to behave more like:

- a compliance knowledge base
- a recommendation engine input
- a regulatory advisory matrix
- a business-context → signage mapping system

This distinction is architecturally critical.

---

# Workbook Sheet Inventory

| Sheet | Purpose | Possible Mapping | Confidence |
|---|---|---|---|
| `K.2 Clasificación NSR-10` | Occupancy/business classification | Future `ComplianceContext` / `BusinessType` | High |
| `Señalización por Grupo NSR-10` | Signage recommendations by occupancy group | Future recommendation rules / kit generation | High |
| `Leyenda y Normativa` | Regulatory semantics and references | Regulatory metadata / explanatory layer | Medium |
| `Reqs por Autoridad` | Authority-driven requirement mapping | Future authority/compliance logic | Medium |
| `Matriz Ente × Subgrupo` | Cross-reference between authorities and groups | Future recommendation engine support | Medium |

---

# Detailed Sheet Analysis

## `K.2 Clasificación NSR-10`

### Observed Purpose
Occupancy/business classification.

### Domain Meaning
Defines business/compliance contexts and occupancy classifications.

### Possible PlacamIA Mapping
Potential future:
- `ComplianceContext`
- `BusinessType`
- occupancy taxonomy layer

### Observations
This sheet appears to classify:
- schools
- hospitals
- commerce
- industrial facilities
- residential contexts
- custody/care facilities
- other occupancy groups

The sheet does not appear to define:
- products
- pricing
- materials
- templates

Instead, it appears to define the contextual starting point for compliance recommendations.

### Confidence
High.

---

## `Señalización por Grupo NSR-10`

### Observed Purpose
Signage recommendations by occupancy group.

### Domain Meaning
Recommendation matrix mapping occupancy groups to signage needs.

### Possible PlacamIA Mapping
Potential future:
- recommendation rules
- guided onboarding
- kit generation logic
- compliance-aware flows

### Observations
This appears to encode logic similar to:

```text
Occupancy Type
    ×
Signage Type
    →
Required / Recommended / N/A
```

This sheet may eventually become one of the most strategically important sources in the system because it appears to contain implicit provider expertise.

The structure aligns more naturally with:

- compliance guidance
- recommendation systems
- contextual kits

than with traditional ecommerce categories.

### Confidence

High.

---

## `Leyenda y Normativa`

### Observed Purpose

Regulatory semantics and references.

### Domain Meaning

Compliance metadata and explanatory context.

### Possible PlacamIA Mapping

Potential future:

- regulatory metadata
- explanatory UX layer
- compliance explanations
- recommendation justification

### Observations

This sheet appears to explain:

- terminology
- regulation references
- interpretation semantics
- recommendation meaning

Potential future uses:

- tooltips
- educational content
- inspection/compliance explanations
- audit support

### Confidence

Medium.

---

## `Reqs por Autoridad`

### Observed Purpose

Authority-driven requirement mapping.

### Domain Meaning

Enforcement/compliance matrix.

### Possible PlacamIA Mapping

Potential future:

- authority-based compliance logic
- recommendation weighting
- inspection-driven flows

### Observations

This sheet appears to relate:

- regulatory authorities
- enforcement bodies
- compliance expectations
- occupancy/business requirements

Potential future strategic value:

- "prepare for inspection" workflows
- authority-aware recommendations
- compliance-oriented onboarding

This sheet suggests the provider workflow may already be heavily inspection-driven.

### Confidence

Medium.

---

## `Matriz Ente × Subgrupo`
### Observed Purpose

Cross-reference between authorities and occupancy subgroups.

### Domain Meaning

Normalized compliance matrix.

### Possible PlacamIA Mapping

Potential future:

- recommendation engine support
- rule normalization layer
- compliance relationship mapping

### Observations

This sheet appears to function as:

- a crosswalk
- a normalization layer
- a rule relationship matrix

Potential future uses:

- dynamic recommendations
- compliance scoring
- automated guidance generation

### Confidence

Medium.

---

# General Workbook Conclusions
## Current Interpretation

The workbook currently appears to behave more like:

- a compliance knowledge base
- a recommendation matrix
- a regulatory advisory system

than:

- a product catalog
- a pricing sheet
- an inventory system

## Important Architectural Discovery

The provider workflow appears to be:

```text
Business Context
    ↓
Compliance Need
    ↓
Recommended Signage
    ↓
Quotation
```

rather than:
```text
Catalog Browsing
    ↓
Product Selection
    ↓
Checkout
```
This distinction is architecturally important.

---

## Current Missing Information

The workbook does not yet appear to contain:

- product SKUs
- pricing tables
- materials
- dimensions
- image assets
- manufacturing constraints
- inventory information

Additional sources will likely be required for:

- commerce catalog population
- pricing
- assets
- manufacturing data

## Current Recommendation

Do NOT:

- ingest workbook rows directly into the production schema
- normalize aggressively yet
- treat workbook structure as final domain structure

Instead:

- continue semantic analysis
- validate findings with provider experts
- analyze Canva catalog separately
- identify missing commerce/product sources
- reconcile provider ontology with PlacamIA domain concepts

only then define ingestion architecture

---

# Observed Business Ontology

## Important Discovery

The provider appears to think primarily in terms of:

```text
Business / Occupancy Context
    ↓
Compliance Need
    ↓
Required Signage
    ↓
Physical Products
```

NOT:
```text
Product Catalog
    ↓
Customer Browsing
    ↓
Purchase
```

This appears to match the real-world sales workflow described by the founding team.

Example:

```text
School
    ↓
Potential inspection risk
    ↓
Required signage package
    ↓
Quotation
```
This discovery strongly influences:

- UX philosophy
- kit modeling
- onboarding flow
- recommendation logic
- future compliance-aware features

---

# Current Interpretation of Existing PlacamIA Concepts

## Category

Current likely meaning:

- evacuation
- fire safety
- prohibition
- EPP
- electrical hazard
- environmental

Interpretation:
Taxonomy of sign types.

Status:
Still appears valid.

## Product

Current likely meaning:
A sellable physical signage item.

Examples:

- Emergency exit sign
- Fire extinguisher sign
- No smoking sign

Status:
Still valid.

## Template

Current likely meaning:
Reusable visual/signage design definition.

Examples:

- Emergency exit visual layout
- Directional arrow design

Status:
Still valid.

## Design

Current likely meaning:
Customized instance derived from a template.

Examples:

- Custom text
- Material selection
- Size selection

Status:
Still valid.

## Kit

Current likely meaning:
Pre-grouped signage solution for a business context.

Examples:

- School kit
- Restaurant kit
- Warehouse kit
- Construction kit

Interpretation:
This concept now appears much more strategically important than originally assumed.

Status:
Potentially core UX/business concept.

---

# Potential Missing Domain Concepts

The workbook strongly suggests PlacamIA may eventually require concepts not yet formally modeled.

## ComplianceContext (Potential Future Concept)

Examples:

- School
- Hospital
- Restaurant
- Warehouse
- Residential building
- Construction site

Possible responsibilities:

- Applicable regulations
- Recommended signage
- Recommended kits
- Authority mappings
- Compliance checklists

Status:
Not currently modeled.

Confidence:
Medium-high.

## RecommendationRule (Potential Future Concept)

Observed need:
The workbook appears to encode:

```text
Occupancy Type
    ×
Sign Type
    →
Required / Recommended / N/A
```
Potential future role:

- guided onboarding
- recommendation engine
- dynamic kit generation
- compliance-aware UX

Status:
Not currently modeled.

Confidence:
High.

---

# Vocabulary Mapping

| Provider Concept             | Possible PlacamIA Concept            | Confidence  |
| ---------------------------- | ------------------------------------ | ----------- |
| Grupo NSR-10                 | ComplianceContext                    | Medium-high |
| Tipo de señal                | Product category OR template family  | Medium      |
| Requerido                    | RecommendationRule                   | High        |
| Subgrupo                     | Business subtype / occupancy subtype | Medium      |
| Ente regulador               | Authority / compliance metadata      | Medium      |
| Paquete implícito de señales | Kit                                  | Medium-high |

---

# What the Workbook Appears NOT to Contain

Current first-pass observations suggest the workbook does NOT primarily contain:

- product SKUs
- canonical product identifiers
- material matrices
- size matrices
- pricing tables
- image assets
- manufacturing constraints
- inventory
- provider operational production data

Implication:
This workbook alone is likely insufficient to populate the MVP commerce catalog database.

Additional sources are likely required:

- Canva catalog
- provider asset repositories
- pricing sheets
- manufacturing references

---

# Architectural Implications

## 1. Compliance May Be the True Entry Point

The provider workflow appears compliance-first rather than catalog-first.

This suggests future UX may benefit from:

- guided onboarding
- business-type selection
- inspection/compliance flows
- recommendation-driven shopping

rather than pure catalog browsing.

## 2. Kits May Be More Important Than Categories

The workbook structure aligns more naturally with:

- compliance kits
- business-context bundles

than with traditional ecommerce categories.

## 3. Recommendation Logic May Become Core IP

The workbook appears to encode valuable business knowledge:

- what signage is needed
- for which contexts
- under which regulations

This may eventually become:

- a recommendation engine
- compliance assistant
- dynamic kit generator
- inspection-preparation flow

## 4. Provider Knowledge Should Not Be Flattened Prematurely

Directly converting workbook rows into:

- products
- categories
- prices

would likely destroy implicit business semantics.

The workbook should first be understood semantically before normalization.

---

# Missing Information

The following information has not yet been identified:

- authoritative product catalog (Which source is considered the “official truth” for products?)
- pricing source
- material definitions
- size definitions
- image repository
- SKU strategy
- manufacturing limitations
- asset ownership
- update workflow
- canonical source of truth

---

# Open Questions for Provider Experts

## Workbook / Compliance Logic
1. Is the workbook operationally used today?
2. Which workbook sheets are considered the official reference during client recommendations?
3. Who maintains the workbook?
4. How often is it updated?
5. Are workbook recommendations standardized or advisory?

## Recommendation Workflow
6. Does the recommendation process begin with:
    - occupancy type?
    - regulation?
    - inspection risk?
    - customer request?
7. Are quantities manually determined?
8. Are kits currently implicit/manual?
9. Are there predefined “inspection packages” today?

## Catalog / Canva
10. Is the Canva catalog the current commercial catalog?
11. Who maintains the Canva catalog?
12. Is pricing inside Canva authoritative? (Is it the final price?)
13. How often are prices updated?
14. Are the prices fixed or approximate?
15. Are quotes manually adjusted?

## Products & Templates
16. What defines a “product” operationally today?
17. Are “Salida de Emergencia” variations considered:
    - separate products?
    - templates?
    - variants?
18. Which dimensions affect pricing?
    - material
    - size
    - printing type
    - customization
    - quantity
19. Are sizes standardized?
20. Are materials standardized?

## Assets & Manufacturing
21. Where are original images/assets stored?
22. Are editable design files available?
23. Are print-ready files available?
24. Are products manufactured internally or outsourced?
25. Are there manufacturing constraints by:
    - material
    - dimensions
    - quantity

## Commerce & Operations
26. Are there SKUs today?
27. Are there internal product codes?
28. Is inventory tracked?
29. Is the catalog quote-driven or inventory-driven?
30. Should PlacamIA eventually become the canonical source of truth?

---

# Confidence Assessment
| Area                                                            | Confidence  |
| --------------------------------------------------------------- | ----------- |
| Workbook is compliance-oriented                                 | High        |
| Workbook is not primarily a commerce catalog                    | High        |
| Compliance grouping maps more naturally to kits than categories | Medium-high |
| Recommendation logic exists implicitly in workbook              | High        |
| Future missing domain concepts likely exist                     | Medium      |
| Workbook alone can populate MVP DB                              | Low         |

---

# Current Recommendation

Do NOT:

- ingest workbook directly into production schema
- define final DB mappings yet
- normalize aggressively yet

Instead:

1. continue semantic analysis
2. validate findings with provider experts
3. analyze Canva catalog next
4. identify missing commerce/product sources
5. reconcile provider ontology with PlacamIA domain model
6. only then define ingestion architecture
