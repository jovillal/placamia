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

## Early relationship ideas
- User creates many Projects
- Project contains many Designs
- Template has many TemplateFields
- Design belongs to one Template
- Design may have many AIVariations
- Project may produce one or more Quotes
- Quote may become an Order
- Order may have Payments, ProductionJobs, and Shipments
