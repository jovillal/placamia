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
   - Pricing can use the persisted Design and backend rules to calculate a
     quote.
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

- #21 Create Template model, migration, and tests
- #22 Create TemplateField model, migration, and tests
- #23 Define MVP design lifecycle

## Future Issues

- #22 Create TemplateField model, migration, and tests
- Future issue required: create Design model, migration, and tests
- Future issue required: create Design repository and service behavior with tests
- Future issue required: create design creation endpoint with validation and
  rejection tests
- Future issue required: create design detail endpoint with ownership/security
  tests
- Future issue required: connect persisted Designs to backend pricing

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

## Done When

- Templates can be browsed
- Users can create valid designs
- Invalid configurations are rejected
- Designs are persisted and retrievable
- Designs can be used for pricing
