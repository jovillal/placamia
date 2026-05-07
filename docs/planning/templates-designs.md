# Templates & Designs

## Goal

Allow users to create customized signage designs based on predefined templates.

This is a core domain capability that transforms catalog items into
user-specific configurations that can be quoted and ordered.

## Core Concepts

- Template = reusable base design
- TemplateField = configurable input definition attached to a Template
- Design = user-customized instance derived from a template

A Design must always be based on a Template.

Templates, TemplateFields, and Designs have separate responsibilities:

- Template stores catalog-level reusable design metadata, such as name,
  description, active state, and timestamps.
- TemplateField stores the allowed customization inputs for a Template, such as
  field name, field type, required state, allowed values, and display order.
- Design stores one user's validated customization values for one Template.
  Design records do not redefine Template metadata or TemplateField rules.

## TemplateField Semantics

MVP TemplateFields support this explicit `field_type` set:

- `text`
- `select`
- `number`
- `boolean`

Unknown `field_type` values are invalid. Future field types require planning
document updates before implementation.

`allowed_values` is interpreted by `field_type`:

| field_type | allowed_values interpretation |
| --- | --- |
| `text` | Must be null. The submitted value is free text, validated by backend text rules. |
| `select` | Must be a non-empty list. The submitted value must match exactly one listed value. |
| `number` | Must be null for MVP. The submitted value is numeric, with min/max rules deferred until explicitly planned. |
| `boolean` | Must be null. The submitted value must be true or false. |

Backend validation is the source of truth for `field_type`, `allowed_values`,
and submitted customization values.

## Flow

1. User selects a Template
2. User customizes fields (material, size, text, etc.)
3. Backend validates options
4. Design is created and persisted
5. Design is used for quote calculation

## MVP Design Lifecycle

1. Template selected
   - User chooses one active Template.
   - Backend verifies the Template exists and is available for customization.
2. Customization submitted
   - User submits values for the TemplateFields defined for that Template.
   - The request must reference the selected Template.
3. Customization validated
   - Backend validates required fields, field types, allowed values, and
     supported combinations.
   - Backend rejects invalid customization combinations.
   - Frontend validation is helpful for usability, but it is not trusted as the
     source of truth.
4. Design persisted
   - Backend creates a Design only after validation succeeds.
   - Design is immutable after creation (MVP assumption).
   - Rejected Design creation must not persist a Design record or partial
     customization data.
5. Design available for pricing
   - Pricing must use persisted validated Design data and backend pricing rules
     to calculate a quote.
   - Pricing must not trust frontend-calculated amounts.

## Persistence Model

Every Design must reference exactly one valid Template.

Design is immutable after creation (MVP assumption). If a user needs a changed
configuration, the backend should create a new Design instead of mutating the
existing one.

Minimum MVP Design fields:

- id
- template_id
- customization_values
- created_at
- updated_at

`customization_values` stores the validated user selections for the referenced
Template at a high level. The exact storage type will be defined by the Design
model implementation issue, but it must preserve enough structured data for
pricing and order creation to validate and use the Design deterministically.

## Current MVP Assumptions

The MVP intentionally keeps Design persistence simple.

Current assumptions:

- Designs are immutable after creation
- Designs belong to exactly one Template
- TemplateFields define the allowed customization structure
- `customization_values` is validated at the service layer, not the database
  layer
- Design validation happens before persistence
- Pricing will consume persisted validated Design data
- Design editing/versioning is out of scope for MVP
- Collaborative/shared Design workflows are out of scope for MVP

## Scope

- Template retrieval (read-only)
- Design creation
- Design persistence
- Design validation

## Related Endpoints

- GET /api/v1/templates
- GET /api/v1/templates/{id}
- POST /api/v1/designs
- GET /api/v1/designs/{id}

## Child Issues

Completed:

- #21 Create Template model, migration, and tests
- #22 Create TemplateField model, migration, and tests
- #23 Define MVP design lifecycle

Planned:

- #90 Define Design customization contract
- #91 Create Design model, migration, repository/service, and tests
- #92 Create Design validation service with rejection tests

## Future Issues

- Future issue required: create POST /api/v1/designs endpoint with validation
  and rejection tests
- Future issue required: create GET /api/v1/designs/{id} endpoint with
  ownership/security tests
- Future issue required: connect persisted Designs to backend pricing
- Future issue required: define Design serialization and normalization rules if
  pricing/order requirements require stricter structure guarantees

## Constraints

- Designs must always reference a valid Template
- Invalid combinations must be rejected
- No AI-based customization (MVP rule)
- No Design record may be created for invalid customization input
- Design is immutable after creation (MVP assumption)

## Security Considerations

- Validate all customization inputs
- Do not trust frontend-provided values
- Enforce allowed combinations of fields
- Prevent injection of invalid design data
- Do not trust frontend-provided ownership fields
- Rejected design creation must not mutate persisted data
- Future user-specific Design endpoints must derive ownership from
  authenticated requests, not frontend-provided identifiers

## Done When

- Templates can be browsed
- Users can create valid designs
- Invalid configurations are rejected
- Designs are persisted and retrievable
- Designs can be used for pricing
