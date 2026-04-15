# Environment Strategy

## Current approach
Local-first development.

## Environment progression
1. local
2. test
3. production

## Rules
- same codebase across environments
- different configuration by environment variables
- PostgreSQL in all environments
- migrations managed with Alembic
- no environment-specific business logic