---
name: check-types
description: Run mypy --strict, regenerate API types, and run tsc --noEmit.
---
Run `./run.sh`. Fix every error. A diff in generated API types means the OpenAPI schema changed:
commit the regenerated types.
