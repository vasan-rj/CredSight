"""Deterministic decisioning core. THE LLM NEVER TOUCHES ANYTHING IN THIS PACKAGE.

A fixed feature pipeline + a versioned model => same inputs always produce the same
score, reproducible months later (ref-doc 04). Build this first.
"""
