# Empty on purpose: its presence makes pytest add the repo root to
# sys.path, so `from carapace import ...` resolves in tests/ without a
# package __init__.py there.
