"""Orchestration: the work queue (GitHub Issues) + intake streams.

Sub-project 5a of the agent-company capstone: a durable, queryable work queue
on GitHub Issues (stream/status labels + a hand-rolled yaml meta block) and the
maintenance stream (canary drift -> Issue). Invoked as
``python -m bookieskit.orchestration <cmd>``. All logic is offline-testable
behind an injectable ``GhRunner`` and an injected canary runner.
"""
