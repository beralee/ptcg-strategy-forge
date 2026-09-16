"""Reviewed read-only service operations shared by SDK and CLI."""
import json
import re
from urllib.parse import quote, urlsplit
import urllib.request
from .replays import NoRedirect


def capabilities():
    return {"document_type": "forge_service_capabilities_v1", "schema_version": 1, "status": "unverified",
            "profile": "dojo", "verification": "offline_contract_snapshot",
            "capabilities": {"recent_games": True, "recent_game_limit": 60, "single_replay": True,
                             "history_pagination": False, "decision_trace": False, "cli_authentication": True,
                             "range_resume": False, "release_idempotency": "archive_sha256_v1"},
            "next_action": "forge service capabilities --origin https://api.ptcg.skillserver.cn",
            "scope": "finite_recent_query_not_complete_history"}


def matches(origin, release_id):
    parsed = urlsplit(origin or "")
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
            or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})):
        raise ValueError("service_origin_invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", release_id):
        raise ValueError("service_release_id_invalid")
    origin = origin.rstrip("/")
    url = origin + "/v1/ladder/releases/" + quote(release_id, safe="") + "/profile?game_limit=60"
    from .replays import NetworkBudget
    from .jobs import state_root
    budget = NetworkBudget(state_root())
    budget.register(origin, 4, 2)
    try:
        with budget.acquire(origin, 4, 2):
            with urllib.request.build_opener(NoRedirect()).open(url, timeout=20) as response:
                payload = response.read(4*1024**2 + 1)
        if len(payload) > 4*1024**2:
            raise ValueError("service_response_budget_exceeded")
        profile = json.loads(payload)
        games = profile["recent_games"]
        if not isinstance(games, list) or len(games) > 60:
            raise ValueError("service_profile_schema_invalid")
        entries = []
        seen = set()
        for game in games:
            series = game["series_id"]
            if not isinstance(series, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", series):
                raise ValueError("service_profile_schema_invalid")
            if game.get("replay_available") is True and series not in seen:
                entries.append({"id": series, "url": origin + "/v1/ladder/matches/" + quote(series, safe="") + "/replay"})
                seen.add(series)
        return {"document_type": "forge_matches_v1", "status": "completed", "release_id": release_id,
                "scope": "recent_60_only", "complete_history": False, "scanned": len(games), "entries": entries}
    except (OSError, KeyError, TypeError, ValueError) as error:
        code = str(error)
        raise ValueError(code if code.startswith("service_") else "service_request_failed") from error
    finally:
        budget.unregister()
