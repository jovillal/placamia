# Provider Domain Analysis

(Discovery Phase / Non-Canonical)

## Purpose

This document captures the observed provider business model, workflow, ontology, and operational semantics before database normalization or implementation decisions are made.

The goal is to preserve:
- provider mental model
- business semantics
- compliance logic
- commercial workflow
- implicit operational assumptions

before translating them into PlacamIA domain concepts.

This is a research/discovery artifact, not a final architecture document.

## Path A Interpretation

PlacamIA has selected Path A for the MVP: direct checkout only for fully
parametrizable, backend-priceable products and kits. Read this analysis as
provider/domain context, not as approval to implement advisory, compliance, or
RFQ behavior in MVP.

For MVP purposes:

- use catalog-driven findings to identify standard products and kits
- use workbook findings only as future compliance/recommendation context
- exclude products that require manual quote review from direct checkout
- validate pricing, availability, and material/size compatibility directly with
  Relieves before implementation
- avoid compliance promises until legal/compliance review is complete

## Document Status

This document contains:
- observations
- inferred interpretations
- architectural hypotheses

Some conclusions remain speculative until validated by provider experts.

## Confidence Interpretation

- High:
  Strongly supported by direct evidence from workbook/catalog sources.

- Medium:
  Reasonable interpretation, but still requires provider validation.

- Low:
  Early hypothesis or speculative architectural inference.

---

# Sources Analyzed

## Workbook Source

- `NSR10 K2 x Señalización v3.xlsx`

Observed role:
- compliance/recommendation layer

---

## Canva/PDF Catalog Source

- `compressed.pdf`

Observed role:
- commercial/catalog layer

---

# Workbook Analysis

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

Expert take: in practice a client arrives with a need, the need may be heavily influenced by regulation/complience or it may be catalog browsing.

## Initial Interpretation

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

Expert take: correct

---

## Workbook Sheet Inventory

| Sheet | Purpose | Possible Mapping | Confidence |
|---|---|---|---|
| `K.2 Clasificación NSR-10` | Occupancy/business classification | Future `ComplianceContext` / `BusinessType` | High |
| `Señalización por Grupo NSR-10` | Signage recommendations by occupancy group | Future recommendation rules / kit generation | High |
| `Leyenda y Normativa` | Regulatory semantics and references | Regulatory metadata / explanatory layer | Medium |
| `Reqs por Autoridad` | Authority-driven requirement mapping | Future authority/compliance logic | Medium |
| `Matriz Ente × Subgrupo` | Cross-reference between authorities and groups | Future recommendation engine support | Medium |

---

## Detailed Sheet Analysis

### `K.2 Clasificación NSR-10`

#### Observed Purpose
Occupancy/business classification.

#### Domain Meaning
Defines business/compliance contexts and occupancy classifications.

#### Possible PlacamIA Mapping
Potential future:
- `ComplianceContext`
- `BusinessType`
- occupancy taxonomy layer

#### Observations
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

#### Confidence
High.

Expert take: there is context (business activity) and regulator (fireman, invime, etc.). So a restaurant will have to comply with fireman and invima regulations. It is important to understand the business activity and who regulates it.

---

### `Señalización por Grupo NSR-10`

#### Observed Purpose
Signage recommendations by occupancy group.

#### Domain Meaning
Recommendation matrix mapping occupancy groups to signage needs.

#### Possible PlacamIA Mapping
Potential future:
- recommendation rules
- guided onboarding
- kit generation logic
- compliance-aware flows

#### Observations
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

#### Confidence

High.

Expert take: given a business the displayed options must be aligned with compliance and regulations.

---

### `Leyenda y Normativa`

#### Observed Purpose

Regulatory semantics and references.

#### Domain Meaning

Compliance metadata and explanatory context.

#### Possible PlacamIA Mapping

Potential future:

- regulatory metadata
- explanatory UX layer
- compliance explanations
- recommendation justification

#### Observations

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

#### Confidence

Medium.

Expert take: Terms of use should make clear that we are not giving garantees for inspection results.
Upgrade to high confidence

---

### `Reqs por Autoridad`

#### Observed Purpose

Authority-driven requirement mapping.

#### Domain Meaning

Enforcement/compliance matrix.

#### Possible PlacamIA Mapping

Potential future:

- authority-based compliance logic
- recommendation weighting
- inspection-driven flows

#### Observations

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

#### Confidence

Medium.

Expert take: most clients are in need of help with compliance regulations.
Upgrado to high confidence.

---

### `Matriz Ente × Subgrupo`
#### Observed Purpose

Cross-reference between authorities and occupancy subgroups.

#### Domain Meaning

Normalized compliance matrix.

#### Possible PlacamIA Mapping

Potential future:

- recommendation engine support
- rule normalization layer
- compliance relationship mapping

#### Observations

This sheet appears to function as:

- a crosswalk
- a normalization layer
- a rule relationship matrix

Potential future uses:

- dynamic recommendations
- compliance scoring
- automated guidance generation

#### Confidence

Medium.

Expert take: It would be a good thing to validate this sheet with lawyers, its pending, however the interpretation is correct.
Upgrade to high confidence but the data can change because its wrong or because regulation changes. The derived rules must be easily modified.

---

## Workbook Conclusions

### Current Interpretation

The workbook currently appears to behave more like:

- a compliance knowledge base
- a recommendation matrix
- a regulatory advisory system

than:

- a product catalog
- a pricing sheet
- an inventory system

### Important Architectural Discovery

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

Expert take: correct


### Current Missing Information

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

### Current Recommendation

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
- only then define ingestion architecture

---

# Canva Catalog Analysis

## Initial Interpretation

The Canva/PDF appears to represent:
- the commercial layer of the provider workflow
- customer-facing catalog structure
- configurable signage offerings
- pricing examples
- material and printing options

Unlike the workbook, the catalog is commerce-oriented rather than compliance-oriented.

---

## Configurable Product Model

The catalog appears to behave more like a configurable product system than a fixed SKU catalog.

Observed configurable dimensions include:
- material
- size
- printing type
- customization

Interpretation:
The provider workflow appears configuration-oriented rather than inventory-oriented.

This strongly supports:
- template-driven commerce
- configurable pricing
- quote-oriented workflows

rather than strict SKU ecommerce.

---

## Observed Product Families

Examples:
- Evacuación
- Reglamentaria
- Señalización
- Protección
- Precaución
- Informativas
- Preventivas
- Transitorias

Interpretation:
These appear to behave as signage semantic categories.

---

## Materials as First-Class Concepts

Observed materials:
- Acrílico transparente
- Acrílico opal
- Polietileno
- Acero
- Bronce
- Lámina de aluminio

Interpretation:
Materials appear to be configurable production dimensions rather than product categories.

Expert take: we are missing materials, the db should be able to handle that. We are also missing printing options, these change pricing, currently they have engraving and plotter.

---

## Printing Types

Observed printing types:
- Fotoluminiscente
- Reflectivo
- Mate
- Brillante

Interpretation:
Printing type appears to be another configurable pricing/manufacturing dimension.

Expert take: these are plotter types, we need to include engraving.

---

## Sizes

Observed standardized sizes:
- 20x10
- 30x15
- 50x30
- others

Interpretation:
Sizes appear semi-standardized and reusable across multiple signage templates.

---

## Customization Model

The catalog explicitly supports customer customization.

Evidence:
“Envíanos la idea de diseño...”

Interpretation:
The provider workflow already assumes:
- template reuse
- custom variants
- configurable designs

This strongly validates the distinction between:
- Template
- Design

inside PlacamIA.

---

## Pricing Observations

Observed characteristics:
- “DESDE $X”
- approximate pricing
- size-dependent pricing
- material-dependent pricing
- configurable pricing

Interpretation:
Pricing appears quote-oriented rather than strict-SKU oriented.

---

## Catalog Conclusions

The catalog does not appear to behave like:
- warehouse inventory
- fixed SKU ecommerce

Instead, it appears to function more like:
- configurable signage commerce
- visual sales support
- guided quotation system

---

# Cross-Source Discoveries

## Emerging Provider Workflow

Current interpretation:

```text
Business Context
    ↓
Compliance Need
    ↓
Recommended Signage
    ↓
Material / Size / Printing Type
    ↓
Customization
    ↓
Quotation
```

## Emerging PlacamIA Ontology

| Concept            | Status             |
| ------------------ | ------------------ |
| Category           | Validated          |
| Product            | Validated          |
| Template           | Strongly validated |
| Design             | Strongly validated |
| Kit                | Validated          |
| ComplianceContext  | Emerging           |
| RecommendationRule | Emerging           |

## Important Architectural Discovery

The provider workflow appears:

- compliance-first

rather than:

- catalog-first

This distinction is strategically important.

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

# Open Questions for Provider Experts

Follow-up questions that still need partner validation are tracked in
`docs/research/provider-partner-question-log.md`.

## Workbook / Compliance Logic
1. Is the workbook operationally used today? Ans: No, this is not being currently used. Its an initiative by one employee to parametrize compliance and regulatory needs.
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
    Ans: clients tend to arrive with exact needs about failed inspections
7. Are quantities manually determined? Ans: yes
8. Are kits currently implicit/manual? Ans: implicit
9. Are there predefined “inspection packages” today? Ans: yes (these are used as recomendations)

## Catalog / Canva
10. Is the Canva catalog the current commercial catalog? Ans: yes
11. Who maintains the Canva catalog? Ans: Daniela, manual
12. Is pricing inside Canva authoritative? (Is it the final price?) Ans: No, price mostly depends on material and size, there are clear rules.
13. How often are prices updated? Ans: base prices depend on material providers (if a type of material becomes more expensive the price rizes).
14. Are the prices fixed or approximate? Ans: Fixed
15. Are quotes manually adjusted? Ans: Yes, there may be discounts for quantity or others.

## Products & Templates
16. What defines a “product” operationally today? Ans: Operationally a product is something that can be sold (a plaque, an extinguisher, bubble gum...)
17. Are “Salida de Emergencia” variations considered:
    - separate products?
    - templates?
    - variants? 
    Ans: depends, if its different from existing inventory they are considered different products. There are templates. Personalizations are variants.
18. Which dimensions affect pricing?
    - material
    - size
    - printing type
    - customization
    - quantity
    Ans: all affect pricing
19. Are sizes standardized? Ans: No, only by recomendation
20. Are materials standardized? Ans: Yes. But some materials may have different width.

## Assets & Manufacturing
21. Where are original images/assets stored? Ans: In a local computer, in Corel Draw.
22. Are editable design files available? Ans: Yes
23. Are print-ready files available? Ans: Yes
24. Are products manufactured internally or outsourced? Ans: some things are outsourced
25. Are there manufacturing constraints by:
    - material Ans: by availability
    - dimensions Ans: by printing means
    - quantity Ans: by availability, this mostly affects delivery time. There are products that are ready, others must be printed. So delivery time is also a variable.

## Commerce & Operations
26. Are there SKUs today? Ans: No
27. Are there internal product codes? Ans: No
28. Is inventory tracked? Ans: No
29. Is the catalog quote-driven or inventory-driven? Ans: Both
30. Should PlacamIA eventually become the canonical source of truth? Ans: No for now.

---

# Current Recommendations

Do NOT:

- normalize aggressively yet
- define final DB mappings yet
- ingest workbook/catalog directly into production schema

Instead:

1. continue semantic analysis
2. validate findings with provider experts
3. reconcile provider ontology with PlacamIA domain concepts
4. identify missing operational/product sources
5. only then define ingestion architecture
