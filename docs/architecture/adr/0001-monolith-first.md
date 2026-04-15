# ADR 0001: Modular monolith first

## Status
Accepted

## Context
The project is at MVP stage and needs high iteration speed, low operational complexity, and clear ownership.

## Decision
Use a modular monolith for the backend.

## Consequences
### Positive
- simpler local setup
- easier debugging
- faster development
- lower coordination overhead

### Negative
- future extraction of services may require refactoring

## Review trigger
Revisit when scaling, team size, or domain boundaries justify service separation.