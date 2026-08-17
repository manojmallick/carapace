"""Async write-back dispatch.

The agent's process never writes to CockroachDB. On a full miss it
fire-and-forgets an event to the carapace-writeback Lambda
(InvocationType="Event"), which owns the only write-capable credential.
A slow or failed write can therefore never block the agent's response.

For local development without a deployed Lambda, set
CARAPACE_LOCAL_WRITEBACK=1: the SAME handler code runs in a background
thread with the write URL. The boundary stays intact either way -- the
reasoning path only ever calls dispatch_writeback() with a payload.
"""

import json
import os
import threading

import boto3

from . import config


def dispatch_writeback(payload: dict) -> str:
    if os.environ.get("CARAPACE_LOCAL_WRITEBACK") == "1":
        return _dispatch_local(payload)
    try:
        boto3.client("lambda", region_name=config.AWS_REGION).invoke(
            FunctionName=config.WRITEBACK_LAMBDA,
            InvocationType="Event",  # async: returns 202 immediately
            Payload=json.dumps(payload).encode(),
        )
        return "ok"
    except Exception as exc:  # noqa: BLE001 -- a failed write must never raise into the read path
        return f"error: {exc}"


def _dispatch_local(payload: dict) -> str:
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
    from writeback_handler import handler

    threading.Thread(target=handler, args=(payload, None), daemon=True).start()
    return "ok(local)"
