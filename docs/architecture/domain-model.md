# Domain Model

## Core entities
- User
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

### Template
Represents a reusable, catalog-level base design.

Current MVP data fields:
- id
- name
- description
- is_active
- created_at
- updated_at

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
- AI-assisted variation generation is out of scope for MVP

## Early relationship ideas
- User creates many Projects
- Project contains many Designs
- Template has many TemplateFields
- Design belongs to one Template
- Project may produce one or more Quotes
- Quote may become an Order
- Order may have Payments, ProductionJobs, and Shipments
