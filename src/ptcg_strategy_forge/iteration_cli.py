"""Additive CLI routes; all operations delegate to the same SDK services."""
from pathlib import Path
import json
import re
from urllib.parse import quote, urlsplit
from urllib.request import build_opener

from .replays import NoRedirect


def register(commands, workspace_commands):
    rules = workspace_commands.add_parser("rules")
    rules.add_argument("operation", choices=("compile", "lint"))
    rules.add_argument("path", type=Path)
    rules.add_argument("--source", type=Path)
    rules.add_argument("--output", type=Path)
    rules.set_defaults(iteration_handler=run)
    quick = workspace_commands.add_parser("test")
    quick.add_argument("path", type=Path)
    quick.add_argument("--case", action="append")
    quick.add_argument("--changed", action="store_true")
    quick.add_argument("--watch", action="store_true")
    quick.set_defaults(iteration_handler=run)
    release = workspace_commands.add_parser("release")
    release.add_argument("operation", choices=("prepare", "status", "submit"))
    release.add_argument("path", type=Path)
    release.add_argument("--author-id")
    release.add_argument("--public-key", type=Path)
    release.add_argument("--submission")
    release.add_argument("--profile", default="dojo")
    release.add_argument("--private-key", type=Path)
    release.add_argument("--retry-unaccepted", action="store_true")
    release.add_argument("--refresh", action="store_true")
    release.set_defaults(iteration_handler=run)
    authoring = commands.add_parser("authoring")
    authoring.add_argument("operation", choices=("metadata",))
    authoring.set_defaults(iteration_handler=run)
    explain = workspace_commands.add_parser("explain")
    explain.add_argument("path", type=Path)
    explain.add_argument("--scenario", required=True)
    explain.add_argument("--artifact", type=Path)
    explain.add_argument("--baseline", type=Path)
    explain.set_defaults(iteration_handler=run)
    scenario = workspace_commands.add_parser("scenario")
    scenario.add_argument("operation", choices=("generate", "from-replay", "counterfactual"))
    scenario.add_argument("path", type=Path)
    scenario.add_argument("--scenario")
    scenario.add_argument("--permutation", help="Comma-separated old positions in the new order.")
    scenario.add_argument("--trace")
    scenario.add_argument("--decision")
    scenario.add_argument("--base-authority", type=Path)
    scenario.add_argument("--field")
    scenario.add_argument("--value", help="A JSON scalar for one public fact.")
    scenario.add_argument("--expected", help="JSON array of explicit developer expected current indexes.")
    scenario.set_defaults(iteration_handler=run)
    native = workspace_commands.add_parser("native-traces")
    native.add_argument("operation", choices=("import", "inspect"))
    native.add_argument("path", type=Path)
    native.add_argument("--source", type=Path)
    native.add_argument("--trace")
    native.set_defaults(iteration_handler=run)
    resource = commands.add_parser("resources")
    resource.add_argument("operation", choices=("status",))
    resource.set_defaults(iteration_handler=run)
    train = workspace_commands.add_parser("train")
    train.add_argument("operation", choices=("bc",))
    train.add_argument("path", type=Path)
    train.add_argument("--dataset", required=True)
    train.add_argument("--split", required=True)
    train.add_argument("--config", type=Path)
    train.add_argument("--epochs", type=int, default=8)
    train.add_argument("--seed", type=int, default=20260909)
    train.add_argument("--resume", action="store_true")
    train.add_argument("--allow-fixture", action="store_true")
    train.set_defaults(iteration_handler=run)
    evaluate = workspace_commands.add_parser("evaluate")
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--mode", choices=("offline", "engine"), default="offline")
    evaluate.add_argument("--run", required=True)
    evaluate.set_defaults(iteration_handler=run)
    compare = workspace_commands.add_parser("compare")
    compare.add_argument("path", type=Path)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--baseline", required=True)
    compare.set_defaults(iteration_handler=run)
    upgrade = workspace_commands.add_parser("upgrade")
    upgrade.add_argument("path", type=Path)
    upgrade.add_argument("--dry-run", action="store_true")
    upgrade.set_defaults(iteration_handler=run)
    version = workspace_commands.add_parser("version")
    version.add_argument("operation", choices=("bump",))
    version.add_argument("path", type=Path)
    version.add_argument("--part", choices=("major", "minor", "patch"), default="patch")
    version.set_defaults(iteration_handler=run)
    jobs = commands.add_parser("jobs", help="Inspect, cancel, or resume persisted local tasks.")
    jobs.add_argument("operation", choices=("list", "status", "cancel", "resume", "retry"))
    jobs.add_argument("job_id", nargs="?")
    jobs.set_defaults(iteration_handler=run)
    cards = commands.add_parser("cards", help="Search the pinned local UID catalog.")
    cards.add_argument("operation", choices=("search", "inspect"))
    cards.add_argument("query")
    cards.set_defaults(iteration_handler=run)
    service = commands.add_parser("service", help="Inspect reviewed service capabilities.")
    service.add_argument("operation", choices=("capabilities",))
    service.add_argument("--profile", choices=("dojo",), default="dojo")
    service.add_argument("--origin")
    service.set_defaults(iteration_handler=run)
    account = commands.add_parser("account")
    account.add_argument("operation", choices=("login", "whoami", "logout", "signing-keys", "register-signing-key"))
    account.add_argument("--profile", default="dojo")
    account.add_argument("--origin")
    login = account.add_mutually_exclusive_group()
    login.add_argument("--email")
    login.add_argument("--username")
    login.add_argument("--api-key-stdin", action="store_true")
    account.add_argument("--public-key", type=Path)
    account.add_argument("--label", default="Forge signing key")
    account.set_defaults(iteration_handler=run)
    matches = workspace_commands.add_parser("matches")
    matches.add_argument("operation", choices=("list",))
    matches.add_argument("path", type=Path)
    matches.add_argument("--origin", required=True)
    matches.add_argument("--release-id", required=True)
    matches.set_defaults(iteration_handler=run)
    replays = workspace_commands.add_parser("replays")
    operations = replays.add_subparsers(dest="operation", required=True)
    for name in ("sync", "verify", "inspect"):
        parser = operations.add_parser(name)
        parser.add_argument("path", type=Path)
        parser.set_defaults(iteration_handler=run)
        if name == "sync":
            source = parser.add_mutually_exclusive_group(required=True)
            source.add_argument("--manifest", type=Path, help="Frozen JSON list of id, url, optional sha256.")
            source.add_argument("--release-id")
            parser.add_argument("--origin")
            parser.add_argument("--concurrency", type=int, default=4)
            parser.add_argument("--requests-per-second", type=float, default=2)
            parser.add_argument("--max-games", type=int, default=1000)
            parser.add_argument("--max-bytes", type=int, default=1024**3)
            parser.add_argument("--resume", action="store_true")
        else:
            parser.add_argument("--collection", required=True)
    dataset = workspace_commands.add_parser("dataset")
    operations = dataset.add_subparsers(dest="operation", required=True)
    for name in ("build", "audit", "stats", "split", "export"):
        parser = operations.add_parser(name)
        parser.add_argument("path", type=Path)
        parser.set_defaults(iteration_handler=run)
        if name == "build":
            sources = parser.add_mutually_exclusive_group(required=True)
            sources.add_argument("--source", type=Path, action="append")
            sources.add_argument("--collection")
            parser.add_argument("--allow-fixture", action="store_true")
        else:
            parser.add_argument("--dataset", required=True)
        if name == "split":
            parser.add_argument("--seed", type=int, default=20260908)
            parser.add_argument("--ratios", default="80,10,10")
        if name == "export":
            parser.add_argument("--output", required=True, type=Path)


from .services import capabilities, matches


def run(args):
    from .sdk import StrategyWorkspace, _ROOT
    if args.command == "resources":
        from .resources_gate import windows_snapshot, validate_snapshot
        snapshot = windows_snapshot()
        try:
            validate_snapshot(snapshot)
            code = None
        except ValueError as error:
            code = str(error)
        return {"document_type": "forge_resource_status_v1", "status": "available" if code is None else "waiting",
                **snapshot, "waiting_reason": code}
    if args.command == "jobs":
        from .jobs import JobStore
        store = JobStore()
        if args.operation == "list":
            return {"document_type": "forge_jobs_v1", "status": "completed", "jobs": store.list()}
        if not args.job_id:
            raise ValueError("job_id_required")
        if args.operation in {"status", "cancel"}:
            return getattr(store, args.operation)(args.job_id)
        job = store.status(args.job_id)
        if job["operation"] == "training.bc":
            inputs = dict(job["input"])
            workspace = StrategyWorkspace.open(inputs.pop("workspace"))
            return workspace.training.bc(**inputs, resume=True)
        if job["operation"] != "replays.sync":
            raise ValueError("job_resume_operation_unsupported")
        inputs = dict(job["input"])
        workspace = StrategyWorkspace.open(inputs.pop("workspace"))
        entries = inputs.pop("entries")
        return workspace.replays.sync(entries, **inputs, resume=True)
    if args.command == "cards":
        from .authoring import search_cards
        return search_cards(args.query, exact=args.operation == "inspect")
    if args.command == "authoring":
        from .authoring import authoring_metadata
        return authoring_metadata()
    if args.command == "service":
        if args.origin:
            from .control_client import ControlClient
            return ControlClient(args.origin).capabilities()
        return capabilities()
    if args.command == "account":
        from .control_client import AccountStore, ControlClient
        import getpass
        import sys
        store = AccountStore()
        if args.operation == "logout":
            return store.logout(args.profile)
        if args.operation == "login":
            if not args.origin:
                raise ValueError("account_origin_required")
            if args.email or args.username:
                client = ControlClient(args.origin).login_password(args.username or args.email,
                    getpass.getpass("Account password: "), username=bool(args.username))
            else:
                token = sys.stdin.readline(1024).strip() if args.api_key_stdin else getpass.getpass("API key: ")
                client = ControlClient(args.origin, token)
            return store.login(args.profile, client)
        client = store.client(args.profile)
        if args.operation == "whoami":
            return {"status": "authenticated", "profile": args.profile, "origin": client.origin, **client.me()}
        if args.operation == "signing-keys":
            return {"status": "completed", **client.request('/v1/developer/signing-keys')}
        if not args.public_key:
            raise ValueError("release_public_key_required")
        from .control_client import register_public_key
        return register_public_key(client, args.public_key, args.label)
    workspace = StrategyWorkspace.open(args.path)
    if args.workspace_command == "rules":
        from .authoring import workspace_rules
        if args.operation == "compile" and (args.source is None or args.output is None):
            raise ValueError("authoring_input_invalid")
        return workspace_rules(workspace, source=args.source if args.operation == "compile" else None, output=args.output)
    if args.workspace_command == "test":
        if args.watch:
            try:
                for report in workspace.debugging.watch(cases=args.case):
                    print(json.dumps(report, ensure_ascii=False), flush=True)
            except KeyboardInterrupt:
                return {"document_type": "forge_watch_report_v1", "status": "stopped", "full_acceptance": False}
        return workspace.debugging.test(cases=args.case, changed=args.changed)
    if args.workspace_command == "release":
        from .release_workflow import ReleaseLedger, prepare_release
        if args.operation == "submit":
            if not args.private_key:
                raise ValueError("release_private_key_required")
            from .control_client import AccountStore
            from .control_release import submit_release
            return submit_release(workspace, AccountStore().client(args.profile), args.private_key,
                                  retry_unaccepted=args.retry_unaccepted)
        if args.operation == "status":
            if not args.submission:
                raise ValueError("release_submission_id_required")
            if args.refresh:
                from .control_client import AccountStore
                from .control_release import refresh_release
                return refresh_release(workspace, AccountStore().client(args.profile), args.submission)
            return ReleaseLedger(workspace.root).status(args.submission)
        if args.public_key is None:
            raise ValueError("release_preparation_inputs_required")
        if not args.author_id:
            from .control_client import AccountStore
            from .control_release import prepare_authenticated_release
            return prepare_authenticated_release(workspace, AccountStore().client(args.profile), args.public_key)
        return prepare_release(workspace, args.author_id, args.public_key)
    if args.workspace_command == "explain":
        if args.baseline:
            return workspace.debugging.compare(args.scenario, args.baseline)
        return workspace.debugging.explain(args.scenario, artifact=args.artifact)
    if args.workspace_command == "native-traces":
        if args.operation == "import":
            if args.source is None:
                raise ValueError("native_trace_source_required")
            return workspace.native_traces.import_trace(args.source)
        if not args.trace:
            raise ValueError("native_trace_identity_required")
        return workspace.native_traces.inspect(args.trace)
    if args.workspace_command == "scenario":
        if args.operation == "counterfactual":
            if not args.scenario or not args.field or args.value is None or args.expected is None:
                raise ValueError("scenario_counterfactual_inputs_required")
            return workspace.debugging.counterfactual(args.scenario, pointer=args.field, value=json.loads(args.value), expected=json.loads(args.expected))
        if args.operation == "generate":
            if not args.scenario or not args.permutation:
                raise ValueError("scenario_generation_inputs_required")
            return workspace.debugging.generate(args.scenario, permutation=[int(i) for i in args.permutation.split(",")])
        if not args.trace or not args.decision or args.base_authority is None:
            raise ValueError("scenario_replay_inputs_required")
        return workspace.debugging.from_replay(args.trace, args.decision, base_authority=json.loads(args.base_authority.read_bytes()))
    if args.workspace_command == "train":
        config = {"epochs": args.epochs, "seed": args.seed}
        if args.config:
            loaded = json.loads(args.config.read_bytes())
            if not isinstance(loaded, dict) or set(loaded) - {"epochs", "seed"}:
                raise ValueError("training_config_invalid")
            config.update(loaded)
        return workspace.training.bc(args.dataset, args.split, **config, resume=args.resume, allow_fixture=args.allow_fixture)
    if args.workspace_command == "evaluate":
        if args.mode == "engine":
            raise ValueError("evaluation_engine_unavailable")
        return workspace.training.evaluate(args.run)
    if args.workspace_command == "compare":
        return workspace.training.compare(args.candidate, args.baseline)
    if args.workspace_command == "upgrade":
        return workspace.upgrade(dry_run=args.dry_run)
    if args.workspace_command == "version":
        return workspace.bump_version(part=args.part)
    if args.workspace_command == "matches":
        return matches(args.origin, args.release_id)
    if args.workspace_command == "replays":
        if args.operation == "sync":
            query = {"source": "explicit_manifest"}
            if args.manifest:
                if args.manifest.stat().st_size > 1024**2:
                    raise ValueError("replay_manifest_budget_exceeded")
                entries = json.loads(args.manifest.read_bytes())
            else:
                discovered = matches(args.origin, args.release_id)
                entries = discovered["entries"]
                query = {"release_id": args.release_id, "scope": discovered["scope"]}
            return workspace.replays.sync(entries, concurrency=args.concurrency,
                requests_per_second=args.requests_per_second, max_games=args.max_games,
                max_bytes=args.max_bytes, resume=args.resume, query=query)
        return getattr(workspace.replays, args.operation)(args.collection)
    store = workspace.dataset
    if args.operation == "build":
        sources = args.source
        if args.collection:
            if workspace.replays.verify(args.collection)["status"] != "passed":
                raise ValueError("dataset_collection_integrity_failed")
            collection = workspace.replays.inspect(args.collection)
            sources = [workspace.replays.blobs / (row["sha256"] + ".json") for row in collection["objects"]]
        return store.build(sources, allow_fixture=args.allow_fixture)
    if args.operation == "split":
        return store.split(args.dataset, seed=args.seed, ratios=tuple(int(v) for v in args.ratios.split(",")))
    if args.operation == "export":
        return store.export(args.dataset, args.output)
    return getattr(store, args.operation)(args.dataset)
