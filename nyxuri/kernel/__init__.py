"""Kernel — the resident skeleton (unit-model.md §2 physical carrying).

Four modules, star-layered with transaction as the only composer:
registry (blueprint's sole reader) · resolver (pure dependency math) ·
ledger (state.json's sole writer) · transaction (the single side-effect
path). The kernel is not a unit: it cannot be switched off.
"""
