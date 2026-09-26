"""Invoke the deployed StockAdvisor runtime on Amazon Bedrock AgentCore.

Usage:
    uv run python scripts/invoke.py examples/request.json [--arn ARN] [--region ap-south-1]
                                                          [--session-id ID]

The runtime ARN comes from --arn or the AGENT_RUNTIME_ARN environment variable
(`agentcore status` prints it after a deploy). The session id must be at least 33
characters; a fresh uuid4 is used when none is given.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

MIN_SESSION_ID_LENGTH = 33


def make_client(region: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "bedrock-agentcore", region_name=region, config=Config(read_timeout=600)
    )


def invoke(
    arn: str,
    body: dict[str, Any],
    region: str = "ap-south-1",
    session_id: str | None = None,
    client=None,
) -> str:
    """Send `body` to the runtime and return the raw response text."""
    session_id = session_id or str(uuid.uuid4())
    if len(session_id) < MIN_SESSION_ID_LENGTH:
        raise ValueError(f"session id must be at least {MIN_SESSION_ID_LENGTH} characters")
    if client is None:
        client = make_client(region)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    raw = response["response"].read()
    return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)


def resolve_arn(arg: str | None) -> str:
    arn = arg or os.environ.get("AGENT_RUNTIME_ARN")
    if not arn:
        raise SystemExit(
            "no runtime ARN: pass --arn or set AGENT_RUNTIME_ARN "
            "(run `agentcore status` after deploying to find it)"
        )
    return arn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="JSON file with the requirements object")
    parser.add_argument("--arn", help="agent runtime ARN (or env AGENT_RUNTIME_ARN)")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    parser.add_argument("--session-id", help="reuse a session id (>= 33 chars)")
    args = parser.parse_args(argv)

    arn = resolve_arn(args.arn)
    body = json.loads(args.request.read_text(encoding="utf-8"))
    text = invoke(arn, body, region=args.region, session_id=args.session_id)
    try:
        parsed = json.loads(text)
    except ValueError:
        print(text)
        return 0
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    return 1 if isinstance(parsed, dict) and "error" in parsed else 0


if __name__ == "__main__":
    sys.exit(main())
