"""
soul-agent-validator CLI (also available as soul-validator)

Usage:
    soul-agent-validator serve                    # Start the web server (port 8080)
    soul-agent-validator validate <github_url>    # Validate a repo from the CLI
    soul-validator serve                          # Also works
    soul-validator validate <github_url>          # Also works
"""
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        prog="soul-agent-validator",
        description="Rules-as-Markdown AI agent governance validator"
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the validator web server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--reload", action="store_true")

    validate = sub.add_parser("validate", help="Validate a GitHub repo")
    validate.add_argument("repo_url", help="GitHub repo URL to validate")
    validate.add_argument("--submitter", default="cli")

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        from soul_validator.server import create_app
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)

    elif args.command == "validate":
        import asyncio, json, sys
        from pathlib import Path
        _root = Path(__file__).parent.parent
        sys.path.insert(0, str(_root))
        from engine.rule_loader import RuleLoader
        from engine.validator import Validator

        rules_dir = _root / "rules"
        rules = RuleLoader(rules_dir).load_all()
        validator = Validator(rules=rules, rules_version="v1.0.0")

        async def run():
            from engine.validator import SubmitRequest
            report = await validator.validate(
                repo_url=args.repo_url,
                submitter=args.submitter,
                team="cli",
            )
            print(json.dumps(report.to_dict(), indent=2))

        asyncio.run(run())

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
