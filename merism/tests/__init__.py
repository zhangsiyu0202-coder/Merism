"""Merism top-level test suite — boundary and cross-cutting tests.

Domain-specific tests live next to the code they exercise
(``merism/recruitment/tests/``, ``merism/knowledge/tests/``, etc.). This
directory holds tests that don't belong to any single domain:

- Boundary / import-time guards
- Model convention enforcement (``merism_`` prefix, ``team_id`` presence)
- Harness self-tests

Run with: ``pytest merism/tests``.
"""
