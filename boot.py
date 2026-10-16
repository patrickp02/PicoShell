# PicoShell safe boot.py
#
# Intentionally minimal. MicroPython initializes the built-in USB REPL and
# then runs main.py automatically. Do not bind sys.stdin with dupterm here
# and do not import main manually.
