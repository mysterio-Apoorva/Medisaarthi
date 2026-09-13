"""AI provider boundary for MediKiosk.

The active clinical workflow imports only ``providers`` so legacy experiments
cannot make startup depend on an unavailable cloud SDK or module path.
"""
