"""Reconciliation & enrichment — the hard last mile, the moat (ref-doc 03 §3).

Cross-validate turnover across GST vs bank vs UPI, resolve disagreements with documented
rules, flag fraud/gaming with rule-backed evidence, tag seasonality, derive features.

Every flag is rule-backed and logged with evidence. The LLM triages/explains rule hits;
it NEVER invents them.
"""
