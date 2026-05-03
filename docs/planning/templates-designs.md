# Templates & Designs

## Goal

Allow users to create customized signage designs based on predefined templates.

This is a core domain capability that transforms catalog items into
user-specific configurations that can be quoted and ordered.

## Core Concepts

- Template = reusable base design
- Design = user-customized instance derived from a template

A Design must always be based on a Template.

## Flow

1. User selects a Template
2. User customizes fields (material, size, text, etc.)
3. Backend validates options
4. Design is created and persisted
5. Design is used for quote calculation

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

## Missing Issues

- Create Design model, migration, and tests
- Create design creation endpoint with tests
- Create design detail endpoint with tests

## Constraints

- Designs must always reference a valid Template
- Invalid combinations must be rejected
- No AI-based customization (MVP rule)

## Security Considerations

- Validate all customization inputs
- Do not trust frontend-provided values
- Enforce allowed combinations of fields
- Prevent injection of invalid design data

## Done When

- Templates can be browsed
- Users can create valid designs
- Invalid configurations are rejected
- Designs are persisted and retrievable
- Designs can be used for pricing