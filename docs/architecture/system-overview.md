# System Overview

## Purpose
PlacamIA allows users to browse, customize, price, purchase, and track
industrial safety signage using predefined templates and deterministic,
rules-based customization.

AI-assisted generation, recommendations, and variations are outside the MVP.

## Current architecture
- mobile-first product vision
- backend implemented as a modular monolith
- single PostgreSQL database
- FastAPI API with SQLAlchemy persistence and Alembic migrations
- Expo mobile placeholder using static/mock contract data until remaining
  customer API contracts are implemented
- provider-neutral payment and manufacturing adapter boundaries inside the
  modular monolith; provider-scoped Payment identity and safe transaction/event
  history are persisted, while Wompi Web Checkout remains the pending first
  real payment integration and current runtime behavior stays deterministic/local

## Main backend responsibilities
- authentication, authorization, and customer ownership enforcement
- product and kit catalog behavior
- template persistence with required Product pricing anchors plus deterministic
  Design customization validation and persistence
- direct-checkout eligibility and backend-owned Product, Kit, and owner-scoped
  persisted Design pricing previews
- Product checkout, orders, and verified payment processing; Kit and Design
  order creation remain separate work
- paid-order provider handoff and production lifecycle tracking
- cancellation requests, shipment events, and delivery tracking
- admin/operator authorization and audit logging for protected mutations

## Explicitly deferred responsibilities

- AI-assisted customization, recommendations, or variations
- project grouping or collaborative workspaces
- credit or gamified accounting systems
- RFQ/manual-quote workflows
- real fulfillment-provider and carrier integrations beyond the current
  adapter boundaries
- payment providers beyond the selected, pending Wompi Web Checkout integration
