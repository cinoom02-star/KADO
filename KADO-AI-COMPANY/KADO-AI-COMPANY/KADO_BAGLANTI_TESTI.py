"""A real local SDK -> backend -> task -> audited result test.

This does NOT test an existing KADO process, a WhatsApp account, or voice calls.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

from kado_bridge import KadoClient, KadoTaskDispatcher


def main():
    parser = argparse.ArgumentParser(description="KADO Company bridge real task exchange test (no WhatsApp claim)")
    parser.add_argument("--url", default=os.getenv("KADO_COMPANY_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token-file", default="data/api-token.txt")
    args = parser.parse_args()
    try:
        token = os.getenv("KADO_API_TOKEN") or Path(args.token_file).read_text(encoding="utf-8").strip()
        with KadoClient(args.url, token) as client:
            health = client.health()
            key = "sdk-live-test:" + str(uuid.uuid4())
            task = client.create_task("KADO SDK gerçek dosya denetimi", kind="workspace_audit", input={}, idempotency_key=key)
            duplicate = client.create_task("KADO SDK gerçek dosya denetimi", kind="workspace_audit", input={}, idempotency_key=key)
            if duplicate["id"] != task["id"]:
                raise AssertionError("Idempotency key did not preserve task identity")
            result = KadoTaskDispatcher(client).wait(task["id"])
            passed = result["status"] == "APPROVED"
            print(json.dumps({"passed": passed, "health": health, "task": result,
                              "idempotency_verified": True, "tested": "SDK to company backend real task exchange",
                              "not_tested": ["existing Windows KADO", "WhatsApp account", "voice", "incoming/outgoing calls"]},
                             ensure_ascii=False, indent=2))
            return 0 if passed else 1
    except Exception as exc:
        print(json.dumps({"passed": False, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
