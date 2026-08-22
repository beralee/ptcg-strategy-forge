from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes, load_json_bytes_strict


class CompetitionClientError(RuntimeError):
    pass


class CompetitionServiceClient:
    def __init__(self, endpoint: str, *, allow_insecure_loopback: bool = False) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
            raise CompetitionClientError("competition_endpoint_invalid")
        if parsed.scheme != "https" and not (
            allow_insecure_loopback and parsed.hostname in ("127.0.0.1", "localhost", "::1")
        ):
            raise CompetitionClientError("competition_https_required")
        self.endpoint = endpoint.rstrip("/")

    def json(
        self,
        path: str,
        *,
        method: str = "GET",
        value: object | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        body = canonical_json_v1_bytes(value) if value is not None else None
        response = self.request(path, method=method, body=body, token=token)
        parsed = load_json_bytes_strict(response)
        if type(parsed) is not dict:
            raise CompetitionClientError("competition_response_invalid")
        return parsed

    def request(
        self,
        path: str,
        *,
        method: str,
        body: bytes | None,
        token: str | None = None,
        content_type: str = "application/json",
    ) -> bytes:
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.endpoint + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as error:
            body_value = error.read()
            try:
                value = load_json_bytes_strict(body_value)
                code = value.get("error_code", "competition_http_error")
            except Exception:
                code = "competition_http_error"
            raise CompetitionClientError(f"{code} (HTTP {error.code})") from error
        except URLError as error:
            raise CompetitionClientError("competition_service_unavailable") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Use the PtcgDAP developer competition service.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8876")
    parser.add_argument("--allow-insecure-loopback", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    apply = commands.add_parser("apply")
    apply.add_argument("--author-id", required=True)
    apply.add_argument("--display-name", required=True)
    apply.add_argument("--email", required=True)
    apply.add_argument("--statement", required=True)

    status = commands.add_parser("application-status")
    status.add_argument("--application-id", required=True)
    claim = commands.add_parser("claim-credential")
    claim.add_argument("--application-id", required=True)

    list_applications = commands.add_parser("list-applications")
    _add_pagination_arguments(list_applications)
    review = commands.add_parser("review")
    review.add_argument("--application-id", required=True)
    review.add_argument("--decision", choices=("approved", "rejected"), required=True)
    review.add_argument("--reason", required=True)

    upload = commands.add_parser("upload")
    upload.add_argument("--package", type=Path, required=True)
    list_releases = commands.add_parser("list-releases")
    _add_pagination_arguments(list_releases)
    developer = commands.add_parser("developer")
    developer.add_argument("--developer-id", required=True)
    _add_pagination_arguments(developer)

    profile = commands.add_parser("create-profile")
    profile.add_argument("--profile", type=Path, required=True)
    list_profiles = commands.add_parser("list-profiles")
    _add_pagination_arguments(list_profiles)
    activate = commands.add_parser("activate-profile")
    activate.add_argument("--profile-id", required=True)

    matches = commands.add_parser("matches")
    matches.add_argument("--profile-id")
    _add_pagination_arguments(matches)
    leaderboard = commands.add_parser("leaderboard")
    leaderboard.add_argument("--profile-id", required=True)
    leaderboard.add_argument("--group-by", choices=("strategy", "deck", "author"), required=True)
    _add_pagination_arguments(leaderboard)
    matchups = commands.add_parser("matchups")
    matchups.add_argument("--profile-id", required=True)
    _add_pagination_arguments(matchups)
    replay = commands.add_parser("download-replay")
    replay.add_argument("--match-id", required=True)
    replay.add_argument("--output", type=Path, required=True)
    suspend = commands.add_parser("suspend-developer")
    suspend.add_argument("--developer-id", required=True)
    suspend.add_argument("--reason", required=True)

    args = parser.parse_args()
    client = CompetitionServiceClient(
        args.endpoint, allow_insecure_loopback=args.allow_insecure_loopback
    )
    admin_token = os.environ.get("PTCGDAP_COMPETITION_ADMIN_TOKEN")
    command = args.command
    if command == "apply":
        result = client.json(
            "/v1/developer-applications",
            method="POST",
            value={
                "requested_author_id": args.author_id,
                "display_name": args.display_name,
                "contact_email": args.email,
                "statement": args.statement,
            },
        )
    elif command == "application-status":
        result = client.json(
            f"/v1/developer-applications/{quote(args.application_id, safe='')}",
            token=_credential("PTCGDAP_APPLICATION_TOKEN"),
        )
    elif command == "claim-credential":
        result = client.json(
            f"/v1/developer-applications/{quote(args.application_id, safe='')}/credential-exchange",
            method="POST",
            value={},
            token=_credential("PTCGDAP_APPLICATION_TOKEN"),
        )
    elif command == "list-applications":
        result = client.json(
            "/v1/admin/developer-applications?" + urlencode(_pagination(args)),
            token=_required(admin_token, "admin"),
        )
    elif command == "review":
        result = client.json(
            f"/v1/admin/developer-applications/{quote(args.application_id, safe='')}/review",
            method="POST",
            value={"decision": args.decision, "reason": args.reason},
            token=_required(admin_token, "admin"),
        )
    elif command == "upload":
        package = args.package.resolve()
        if not package.is_file() or package.is_symlink():
            raise CompetitionClientError("competition_package_missing")
        body = client.request(
            "/v1/competition-releases",
            method="POST",
            body=package.read_bytes(),
            token=_credential("PTCGDAP_DEVELOPER_TOKEN"),
            content_type="application/vnd.ptcgdap.competition-strategy",
        )
        result = load_json_bytes_strict(body)
    elif command == "list-releases":
        result = client.json(
            "/v1/competition-releases?" + urlencode(_pagination(args))
        )
    elif command == "developer":
        result = client.json(
            f"/v1/competition-developers/{quote(args.developer_id, safe='')}?"
            + urlencode(_pagination(args))
        )
    elif command == "create-profile":
        value = load_json_bytes_strict(args.profile.resolve().read_bytes())
        result = client.json(
            "/v1/admin/competition-profiles",
            method="POST",
            value=value,
            token=_required(admin_token, "admin"),
        )
    elif command == "list-profiles":
        result = client.json(
            "/v1/competition-profiles?" + urlencode(_pagination(args))
        )
    elif command == "activate-profile":
        result = client.json(
            f"/v1/admin/competition-profiles/{quote(args.profile_id, safe='')}/activate",
            method="POST",
            value={},
            token=_required(admin_token, "admin"),
        )
    elif command == "matches":
        query = _pagination(args)
        if args.profile_id:
            query["profile_id"] = args.profile_id
        result = client.json("/v1/competition-matches?" + urlencode(query))
    elif command == "leaderboard":
        result = client.json(
            "/v1/competition-leaderboards?"
            + urlencode(
                {
                    "profile_id": args.profile_id,
                    "group_by": args.group_by,
                    **_pagination(args),
                }
            )
        )
    elif command == "matchups":
        result = client.json(
            "/v1/competition-matchups?"
            + urlencode({"profile_id": args.profile_id, **_pagination(args)})
        )
    elif command == "download-replay":
        output = args.output.resolve()
        if output.exists():
            raise CompetitionClientError("competition_replay_output_exists")
        body = client.request(
            f"/v1/competition-matches/{quote(args.match_id, safe='')}/replay",
            method="GET",
            body=None,
        )
        load_json_bytes_strict(body)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(body)
        result = {"downloaded": True, "output": str(output), "bytes": len(body)}
    elif command == "suspend-developer":
        result = client.json(
            f"/v1/admin/competition-developers/{quote(args.developer_id, safe='')}/suspend",
            method="POST",
            value={"reason": args.reason},
            token=_required(admin_token, "admin"),
        )
    else:
        raise AssertionError(command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _credential(name: str) -> str:
    return _required(os.environ.get(name), name)


def _add_pagination_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor")


def _pagination(args: argparse.Namespace) -> dict[str, object]:
    value: dict[str, object] = {"limit": args.limit}
    if args.cursor:
        value["cursor"] = args.cursor
    return value


def _required(value: str | None, label: str) -> str:
    if not value:
        raise CompetitionClientError(f"{label}_token_missing")
    return value


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompetitionClientError as error:
        raise SystemExit(str(error)) from None
