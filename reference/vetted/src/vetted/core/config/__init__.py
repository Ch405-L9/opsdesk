"""Configuration schemas and loading.

Two distinct stages, kept separate on purpose:

1. Structural validation parses and type-checks the shipped configuration. It must pass, so
   import, lint, type check, test, and CLI help all work.
2. Readiness validation is requested only when full assessment execution is wanted. It fails
   with a clear error while any policy key remains UNRESOLVED (A-3, A-4).
"""
