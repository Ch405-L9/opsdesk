"""Deterministic assessment.

Every function here is pure: it takes `(inputs, config)` and returns a value. No I/O, no
clock, no randomness. Identical inputs always produce identical output.

Phase 1A ships signatures only. Each raises NotImplementedError naming the owner decision
that gates it, so no assessment behaviour can be written before the policy exists.
"""
