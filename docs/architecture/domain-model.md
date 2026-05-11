# Domain Model

## Core entities
- User
- Product
- Kit
- KitItem
- Template
- TemplateField
- Design
- Project
- Quote
- Order
- Payment
- ProductionJob
- Shipment
- AIVariation
- CreditTransaction

## Critical rule
Templates and Designs are separate entities.

### Kit
Represents a curated bundle of catalog products.

Current MVP data fields:
- id
- name
- description
- is_active
- created_at
- updated_at

Current MVP relationship rules:
- Kit may have many KitItems
- Kit is read-only in customer-facing MVP catalog behavior
- Kit does not store pricing, discount, checkout, or provider handoff behavior

### KitItem
Represents one product entry inside a Kit.

Current MVP data fields:
- id
- kit_id
- product_id
- quantity
- created_at
- updated_at

Current MVP relationship rules:
- KitItem belongs to one Kit
- KitItem links to one existing Product
- KitItem stores quantity metadata only
- KitItem does not duplicate Product metadata or pricing

### Template
Represents a reusable, catalog-level base design.

Current MVP data fields:
- id
- name
- description
- is_active
- created_at
- updated_at

### TemplateField
Represents a configurable input definition attached to a Template.

Current MVP data fields:
- id
- template_id
- field_name
- field_type
- is_required
- allowed_values
- display_order
- is_active
- created_at
- updated_at

Current MVP relationship rules:
- TemplateField belongs to one Template
- Template may have many TemplateFields
- TemplateField defines allowed customization inputs
- TemplateField does not store user customization values
- MVP field_type values are text, select, number, and boolean
- allowed_values is used only by field types that explicitly support it

### Design
Represents a user-customized instance derived from a template.

Current MVP data fields:
- id
- template_id
- customization_values
- created_at
- updated_at

Current MVP relationship rules:
- Design belongs to one valid Template
- Template may have many Designs
- Design stores validated user customization values
- Design does not store TemplateField definitions
- Design stores customization_values as a JSON object
- Design customization values are keyed by TemplateField field_name
- Design customization values contain only backend-validated field values
- AI-assisted variation generation is out of scope for MVP

## Early relationship ideas
- User creates many Projects
- Project contains many Designs
- Template has many TemplateFields
- Design belongs to one Template
- Project may produce one or more Quotes
- Quote may become an Order
- Order may have Payments, ProductionJobs, and Shipments
