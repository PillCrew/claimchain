"""Deterministic evaluation benchmark for claimchain.

Every case pins a ground-truth snapshot (``TokenTruth``) and the set of claims a
perfect system should extract from the agent's prose, each with the verdict it
should receive. The runner measures extraction precision/recall/F1 and verdict
accuracy so regressions are caught by CI and the README can quote real numbers.
"""
