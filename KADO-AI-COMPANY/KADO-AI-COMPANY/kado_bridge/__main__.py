from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .kado_adapter import KadoClient
from .kado_task_dispatcher import KadoTaskDispatcher


def main():
    parser = argparse.ArgumentParser(description="Existing KADO's company sidecar CLI")
    parser.add_argument("--url", default=os.getenv("KADO_COMPANY_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token-file", default="data/api-token.txt")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    sub.add_parser("agents")
    task = sub.add_parser("submit")
    task.add_argument("title")
    task.add_argument("--kind", choices=["workspace_audit", "llm_task"], default="workspace_audit")
    task.add_argument("--input", default="{}", help="JSON task input")
    task.add_argument("--wait", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("task_id")
    args = parser.parse_args()
    token = os.getenv("KADO_API_TOKEN") or Path(args.token_file).read_text(encoding="utf-8").strip()
    with KadoClient(args.url, token) as client:
        if args.command == "submit":
            result = client.create_task(args.title, kind=args.kind, input=json.loads(args.input))
            if args.wait:
                result = KadoTaskDispatcher(client).wait(result["id"])
        elif args.command == "status":
            result = client.task(args.task_id)
        else:
            result = getattr(client, args.command)()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
