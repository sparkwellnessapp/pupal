"""Operational entry points run as `python -m app.scripts.<name>`.

These are COMMANDS, not endpoints. A timer-driven query has no business being
reachable from the internet (028 §7), so the re-ask digest is a Cloud Run Job
on a Cloud Scheduler trigger rather than an HTTP route with a shared secret.
"""
