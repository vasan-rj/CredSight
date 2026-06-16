# Fraud Signals & Consent Policy (synthetic stand-in)

> Synthetic policy covering data consent and alternate-data gaming signals.

## Consent-first ingestion
Alternate data may be pulled only against a valid Account Aggregator consent artefact, and
only within the consented scope. The consent reference is recorded in the audit trail with
every data pull.

## Circular UPI flows
UPI value concentrated among a small set of related payers, with elevated reversal rates,
is a gaming signal. Such cases are flagged with evidence and routed to manual review; the
flag does not by itself decide the outcome.

## Pre-application inflow spike
A final-month bank inflow well above the trailing average suggests possible pre-application
inflation of cash-flow. This is flagged with evidence and reviewed by a human.

## Fraud flags force review
Any fraud-severity reconciliation flag forces the case to the human-in-the-loop gate
before any offer or action, irrespective of the computed score.
