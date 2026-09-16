from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from .resources import resource_root
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = resource_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ptcgdap.author_strategy_developer import (  # noqa: E402
    DeveloperToolError,
    build_development_package,
    install_development_package,
    scaffold_workspace,
    simulate_public_window,
    validate_development_package,
)
from tools.ptcgdap.build_author_strategy_package import write_or_check_contracts  # noqa: E402
from tools.ptcgdap.build_competitive_policy_v2_contract import (  # noqa: E402
    write_or_check as write_or_check_competitive_v2_contract,
)
from tools.build_developer_supported_cards import verify_supported_cards_delivery  # noqa: E402
from tools.ptcgdap.publish_strategy_release import PublishError, publish  # noqa: E402
from scripts.ai.ptcgdap.ucis_sdk import UcisDeveloperSdk, UcisSdkError  # noqa: E402
from scripts.ai.ptcgdap.author_strategy_package import (  # noqa: E402
    CABT_CONTRACT_SHA256,
    CARD_CATALOG_SHA256,
)
from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensorizer  # noqa: E402
from scripts.ai.ptcgdap.ptcgai_model_package import (  # noqa: E402
    build_model_manifest,
    canonical_bytes,
)

from .provenance import verify_snapshot
from .ptcgai_ort import (
    OrtActorError,
    conformance as model_conformance,
    import_onnx_to_ort,
    inspect_onnx,
    inspect_ort,
    write_linear_actor_onnx,
)
from .reviewed_decks import customize_reviewed_workspace, reviewed_deck_ids
from .release_signing import (
    build_registered_release,
    generate_release_key,
    resign_registered_release,
)
from .ucis_runtime import PublicBattleFacts, UcisRuntimeError
from .scenarios import (
    SUITE_DOCUMENT_TYPE,
    assert_public_report,
    generate_demo_scenarios,
    is_competitive_scenario,
    load_json,
    simulate_competitive_public_frame,
    write_json,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _ucis_qualification(root: Path) -> dict[str, object]:
    contract_root = root / "contracts/ptcgdap"
    path = contract_root / "ucis_catalog_qualification_v1.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("ucis_catalog_qualification_invalid") from error
    if type(document) is not dict:
        raise ValueError("ucis_catalog_qualification_invalid")
    payload = dict(document)
    expected = payload.pop("evidence_sha256", None)
    actual = hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest().upper()
    if (
        expected != actual
        or document.get("qualification_status") != "passed"
        or document.get("failure_reasons") != []
    ):
        raise ValueError("ucis_catalog_qualification_invalid")
    scope = document.get("scope")
    performance_scope = document.get("performance_scope")
    operation_scope = document.get("representative_live_operation_scope")
    if any(type(value) is not dict for value in (scope, performance_scope, operation_scope)):
        raise ValueError("ucis_catalog_qualification_invalid")
    linked = (
        (
            contract_root / "ucis_performance_qualification_v1.json",
            performance_scope.get("evidence_sha256"),
        ),
        (
            contract_root / "corresponding_card_whole_battle_input_index_v1.json",
            operation_scope.get("evidence_sha256"),
        ),
    )
    for linked_path, linked_expected in linked:
        try:
            linked_document = json.loads(linked_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("ucis_catalog_qualification_invalid") from error
        if type(linked_document) is not dict:
            raise ValueError("ucis_catalog_qualification_invalid")
        linked_payload = dict(linked_document)
        linked_hash = linked_payload.pop("evidence_sha256", None)
        linked_actual = hashlib.sha256(
            json.dumps(
                linked_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest().upper()
        if linked_hash != linked_actual or linked_hash != linked_expected:
            raise ValueError("ucis_catalog_qualification_invalid")
    return {
        "accepted": True,
        "evidence_sha256": expected,
        "maximum_claim": document.get("maximum_claim", ""),
        "declared_usable": scope.get("declared_usable", -1),
        "explicit_unsupported": scope.get("explicit_unsupported", -1),
        "representative_operation_claim": operation_scope.get("claim", ""),
        "performance_status": performance_scope.get("qualification_status", ""),
    }


def _emit(report: dict[str, object], report_path: Path | None) -> None:
    if report_path is not None:
        write_json(report_path, report)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    console_encoding = getattr(sys.stdout, "encoding", None)
    if console_encoding:
        try:
            rendered.encode(console_encoding, errors="strict")
        except (LookupError, UnicodeEncodeError):
            rendered = json.dumps(report, ensure_ascii=True, indent=2)
    print(rendered)


def _customize_workspace(
    workspace: Path,
    package_id: str,
    package_version: str,
    author_id: str,
    author_name: str,
    strategy_name: str | None,
    summary: str | None,
) -> None:
    path = workspace / "package/strategy_package.json"
    manifest = load_json(path)
    manifest["package_id"] = package_id
    manifest["package_version"] = package_version
    manifest["author"] = {"author_id": author_id, "display_name": author_name}
    manifest["strategy"] = {
        "display_name": strategy_name or package_id,
        "summary": summary or "Data-only current-window strategy developed with PTCG Strategy Forge.",
    }
    write_json(path, manifest)
    policy_ir_path = workspace / "package/policy/policy_ir.json"
    policy_ir = load_json(policy_ir_path)
    policy_ir["graph_id"] = package_id
    write_json(policy_ir_path, policy_ir)
    adapter_path = workspace / "package/policy/adapter.json"
    adapter = load_json(adapter_path)
    adapter["adapter_id"] = package_id
    write_json(adapter_path, adapter)


def _write_workspace_guides(workspace: Path) -> list[str]:
    manifest = load_json(workspace / "package/strategy_package.json")
    strategy = manifest["strategy"]
    deck = manifest["deck"]
    strategy_name = str(strategy["display_name"])
    deck_name = str(deck["display_name"])
    blueprint = f"""# {strategy_name} 策略思考蓝图

> 牌组：{deck_name}
> 状态：DRAFT。先用公开事实和场景证据填完蓝图，再调整规则 priority。

## 1. 不可变决策边界

```text
agent(raw_observation) -> list[int]
```

- 每次只从当前 `select.option` 窗口选择索引；旧索引、旧分数和旧证明不跨窗口复用。
- 任何已接受选择或信息变化后都重观察、重建公开事实并重新绑定语义目标。
- Base Graph 拥有合法性、mandatory/terminal、hard tier、veto、fallback 和最终裁决。
- 作者 adapter 只表达公开目标、macro 和同层 tie-break；不执行引擎动作，也不读取隐藏信息。

## 2. Match Agenda

- 主要获胜路线：TODO
- 备用获胜路线：TODO
- 最快奖赏日程（按攻击窗口，不按自然回合）：TODO
- 稳健奖赏日程：TODO
- 当前应保护的引擎、攻击手和一奖桥：TODO
- 何时从铺场切换到终结：TODO

## 3. 公开事实与身份

- 只使用本包 `deck_manifest.json` 中审核过的本地 UID。
- 对手隐藏手牌、牌序、盖放奖赏、私有 RNG 和搜索 capability 不进入策略输入或报告。
- 决策所需公开事实：TODO
- 关键身份/角色映射（攻击手、引擎、检索、加速、回收、换位）：TODO

## 4. Resource Ledger

| 资源或额度 | 当前用途 | 必须保留给 | 可消费条件 | 过度投入风险 |
|---|---|---|---|---|
| 支援者额度 | TODO | TODO | TODO | TODO |
| 手贴/能量 | TODO | TODO | TODO | TODO |
| 备战位 | TODO | TODO | TODO | TODO |
| 关键检索/回收 | TODO | TODO | TODO | TODO |

## 5. 候选路线与攻击窗口

| Route | 当前收益 | 对手可信回应 | 下一攻击手连续性 | 最小资源支付 | 切换条件 |
|---|---|---|---|---|---|
| Rule floor | TODO | TODO | TODO | TODO | TODO |
| Route A | TODO | TODO | TODO | TODO | TODO |
| Route B | TODO | TODO | TODO | TODO | TODO |

只在公共证明或已验证场景支持时离开 Rule floor。不要把“退到备战区”自动视为保奖成功；同时评估对手抓取与自己的攻击窗口是否变慢。

## 6. 信息动作与重规划检查点

抽牌、检索、揭示、奖赏变化、随机结果和新交互窗口都可能改变最优路线：

| 信息动作 | 新增公开信息 | 必须失效的旧假设 | 重观察后的条件后缀 |
|---|---|---|---|
| TODO | TODO | TODO | TODO |

条件后缀只保存语义债务和目标，不保存未来索引或预造动作。每次仍只执行一个当前窗口动作。

## 7. 类型化交互

- 检索目标策略：TODO
- 弃牌/能量支付策略：TODO
- 换位与出战目标策略：TODO
- 伤害/指示物分配策略：TODO
- 明确允许 whiff/空选择的窗口：TODO

## 8. Hard Guards 与回滚

- 当前可直接获胜时禁止的无关动作：TODO
- 会丢失当前攻击窗口的资源消费：TODO
- 无精确可支付击倒时禁止的抓取/换位：TODO
- 信息不足、未知枚举或策略失败时的确定性 fallback：Base Graph
- 回滚单位：上一份 exact `package_id + package_version + archive_sha256`

## 9. Adapter 规则映射

| rule_id | goal_stage | 公开前置条件 | 目标 option 语义 | Base 可阻止原因 |
|---|---|---|---|---|
| TODO | acquire/deploy/fund/ready/execute/maintain/recover | TODO | TODO | TODO |

## 10. RED→GREEN 场景矩阵

每个 macro 至少覆盖：正向、关键条件缺失、错误目标、option 重排、mandatory/terminal、hard tier/veto、未知 UID 和隐藏信息污染。

再为关键判断增加 metamorphic 配对：每次只改变一个事实（例如目标 HP、剩余奖赏、能量数量、抓取能力或攻击窗口），期望决策随阈值正确翻转。

## 11. 完成门

- [ ] 蓝图中的所有 TODO 已被规则、场景或明确非目标关闭。
- [ ] `check` 双构建字节一致、严格校验通过、场景全部 GREEN。
- [ ] 报告中无隐藏信息、raw authority、ticket、command 或凭据。
- [ ] 已区分开发模拟、Godot 引擎见证、CABT 对齐与 production 权限。
- [ ] 失败按 observation / identity / policy / Base adjudication / interaction / engine 分层归因。
"""
    workspace_readme = f"""# {strategy_name} 开发工作区

这是一个可构建为 data-only `.ptcgai` 的完整开发工作区。开发时只需要围绕同一个 `workspace` 生命周期操作：

1. 运行 `status`，查看本工作区应该编辑什么、缺少什么、产物会写到哪里。
2. 在 `STRATEGY-BLUEPRINT.md` 写清公开事实、路线、资源债务和信息检查点。
3. 修改 `package/policy/adapter.json`；模型模式再替换 `package/model/actor.ort`，但始终保留规则 fallback。
4. 在 `SUPPORTED-CARDS.json` 用本地 UID 核对当前游戏可用卡牌与交互状态。
5. 在 `scenarios/` 增加 RED→GREEN、option 重排和单事实 metamorphic 用例。
6. 依次 inspect、check、build；通过后再安装：

```powershell
python forge.py workspace status <本工作区路径>
python forge.py workspace inspect <本工作区路径>
python forge.py workspace check <本工作区路径>
python forge.py workspace build <本工作区路径>
python forge.py workspace install <本工作区路径>
```

PowerShell 用户也可以把 `python forge.py` 替换为 `.\\forge.ps1`。`check` 通过只代表开发包确定性、合同与公开窗口场景通过；不授予引擎、CABT 或 production 权限。
"""
    sdk_guide = f"""# {strategy_name} 的 UCIS 上手卡

本工作区是 data-only `.ptcgai`：Python SDK 只用于开发检查，不会装进游戏。

```powershell
.\\forge.ps1 workspace inspect <本工作区路径>
.\\forge.ps1 workspace check <本工作区路径>
```

`workspace inspect` 是日常入口；需要查看完整 UCIS 能力表或教学样例时，再使用高级命令 `ucis catalog` 与 `ucis walkthrough`。先确认场景是合法的命名化 Context/Option 组合，再编辑 adapter。每次选择接受后旧 index 失效；跨窗口只保留公开语义目标、稳定 UID 或资源债务，并在新 observation 上重新绑定。精确数量、重复分配、NUMBER/YES_NO、奖赏时钟和能量债务的可执行代码位于 Forge `demo/marnie-forge/sdk_walkthrough.py`。

`SUPPORTED-CARDS.json` 是创建工作区时复制的 qualification-locked 卡牌清单。`usable=true` 表示该本地 UID 的声明交互路径可用，不等于官方完整规则结果一致或已有牌组策略模板；显示名称不在此身份合同中，不能替代 UID。

当前包牌组：{deck_name}。Base Graph 仍拥有合法性、mandatory/terminal、hard tier、veto、fallback 和最终裁决。
"""
    supported_cards_source = ROOT / "data/developer/supported-cards-v1.json"
    if not supported_cards_source.is_file():
        raise ValueError("supported_cards_delivery_missing")
    (workspace / "STRATEGY-BLUEPRINT.md").write_text(blueprint, encoding="utf-8")
    (workspace / "README.md").write_text(workspace_readme, encoding="utf-8")
    (workspace / "UCIS-SDK.md").write_text(sdk_guide, encoding="utf-8")
    (workspace / "SUPPORTED-CARDS.json").write_bytes(supported_cards_source.read_bytes())
    return ["README.md", "STRATEGY-BLUEPRINT.md", "UCIS-SDK.md", "SUPPORTED-CARDS.json"]


def doctor() -> dict[str, object]:
    checks: list[dict[str, object]] = []
    version_ok = sys.version_info >= (3, 13)
    checks.append({"id": "python", "accepted": version_ok, "version": sys.version.split()[0]})
    try:
        snapshot = verify_snapshot(ROOT)
    except (OSError, UnicodeError, ValueError) as error:
        snapshot = {"accepted": False, "file_count": 0, "failures": [{"error_code": str(error)}]}
    checks.append({"id": "sdk-snapshot", **snapshot})
    try:
        supported_cards = verify_supported_cards_delivery()
    except (OSError, UnicodeError, ValueError) as error:
        supported_cards = {"accepted": False, "error_code": str(error)}
    checks.append({"id": "supported-cards", **supported_cards})
    try:
        ucis = UcisDeveloperSdk.load(ROOT)
        ucis_catalog = ucis.capability_catalog()
        ucis_closure = dict(ucis_catalog["closure"])
        ucis_legacy = dict(ucis_catalog["legacy_closure"])
        ucis_coverage = dict(ucis_catalog["coverage_metrics"])
        ucis_qualification = _ucis_qualification(ROOT)
        ucis_ok = (
            len(ucis_catalog["primitives"]) == 16
            and all(
                ucis_closure.get(key) == 0
                for key in (
                    "unregistered",
                    "legacy_author_visible",
                    "custom_prompt_builder",
                    "silent_fallback",
                )
            )
            and all(
                ucis_legacy.get(key) == 0
                for key in (
                    "legacy_author_visible",
                    "legacy_write_entrypoints",
                    "dual_authority",
                    "custom_prompt_builder",
                )
            )
            and all(
                row.get("numerator") == row.get("denominator")
                for row in ucis_coverage.values()
            )
            and bool(ucis_qualification["accepted"])
        )
        ucis_error = ""
    except (OSError, UnicodeError, ValueError, UcisSdkError) as error:
        ucis_ok = False
        ucis_error = str(error)
        ucis_catalog = {}
        ucis_qualification = {}
    checks.append(
        {
            "id": "ucis-sdk",
            "accepted": ucis_ok,
            "ucis_generation": ucis_catalog.get("ucis_generation", -1),
            "contract_generation": ucis_catalog.get("contract_generation", -1),
            "registry_sha256": ucis_catalog.get("registry_sha256", ""),
            "catalog_scope_sha256": ucis_catalog.get("catalog_scope_sha256", ""),
            "primitive_count": len(ucis_catalog.get("primitives", ())),
            "supported_primitives": list(ucis_catalog.get("primitives", ())),
            "unsupported_capabilities": list(
                ucis_catalog.get("unsupported_capabilities", ())
            ),
            "qualification": ucis_qualification,
            "error_code": ucis_error,
        }
    )
    try:
        write_or_check_contracts(check=True)
        contract_ok = True
        contract_error = ""
    except SystemExit as error:
        contract_ok = False
        contract_error = str(error)
    checks.append({"id": "contract-drift", "accepted": contract_ok, "error_code": contract_error})
    try:
        write_or_check_competitive_v2_contract(check=True)
        competitive_contract_ok = True
        competitive_contract_error = ""
    except SystemExit as error:
        competitive_contract_ok = False
        competitive_contract_error = str(error)
    checks.append(
        {
            "id": "competitive-v2-contract-drift",
            "accepted": competitive_contract_ok,
            "error_code": competitive_contract_error,
        }
    )
    try:
        template = validate_development_package(
            ROOT / "data/ptcgdap/author_strategy_packages/ptcgdap-author-strategy-release-candidate.ptcgai"
        )
        template_ok = template.get("status") == "valid"
    except (DeveloperToolError, OSError):
        template_ok = False
    checks.append({"id": "template-package", "accepted": template_ok})
    return {
        "document_type": "ptcg_strategy_forge_doctor_report_v1",
        "schema_version": 1,
        "status": "passed" if all(bool(row.get("accepted")) for row in checks) else "failed",
        "checks": checks,
    }


def ucis_catalog_report() -> dict[str, object]:
    sdk = UcisDeveloperSdk.load(ROOT)
    catalog = sdk.capability_catalog()
    closure = dict(catalog["closure"])
    qualification = _ucis_qualification(ROOT)
    return {
        "document_type": "ptcg_strategy_forge_ucis_catalog_report_v1",
        "schema_version": 1,
        "status": "passed" if qualification["accepted"] else "failed",
        "ucis_generation": catalog["ucis_generation"],
        "contract_generation": catalog["contract_generation"],
        "registry_sha256": catalog["registry_sha256"],
        "catalog_scope_sha256": catalog["catalog_scope_sha256"],
        "primitive_count": len(catalog["primitives"]),
        "supported_primitives": list(catalog["primitives"]),
        "usable_effects": int(closure.get("compiled", 0)) + int(closure.get("automatic", 0)),
        "unsupported_effects": int(closure.get("unsupported", 0)),
        "unsupported_capabilities": list(catalog["unsupported_capabilities"]),
        "closure": closure,
        "qualification": qualification,
        "claims": {
            "catalog_scoped": True,
            "full_rule_a3": False,
            "production_authority": False,
        },
    }


def inspect_ucis_scenario(path: Path) -> dict[str, object]:
    scenario = load_json(path)
    if is_competitive_scenario(scenario):
        from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error
        frame = scenario.get("frame")
        error = _frame_error(frame)
        if error:
            raise ValueError(error)
        report = {"document_type": "forge_competitive_scenario_inspection_v1", "schema_version": 1,
                  "status": "passed", "scenario_id": scenario.get("scenario_id", ""),
                  "window": {**copy.deepcopy(frame["select_semantics"]), "options": copy.deepcopy(frame["options"])},
                  "public_facts": copy.deepcopy(frame["public_state"]),
                  "claims": {"public_only": True, "engine_execution": False, "production_authority": False}}
        assert_public_report(report)
        return report
    raw = scenario.get("raw_observation") if type(scenario) is dict else None
    if type(raw) is not dict:
        raise ValueError("ucis_scenario_observation_invalid")
    sdk = UcisDeveloperSdk.load(ROOT)
    window = sdk.parse_selection(raw)
    bindings = scenario.get("local_uid_bindings", {})
    option_bindings = bindings.get("options", []) if type(bindings) is dict else []
    local_uids: dict[int, str | None] = {}
    if type(option_bindings) is list:
        for binding in option_bindings:
            if (
                type(binding) is dict
                and type(binding.get("index")) is int
                and (
                    binding.get("local_card_uid") is None
                    or type(binding.get("local_card_uid")) is str
                )
            ):
                local_uids[binding["index"]] = binding.get("local_card_uid")
    options = [
        {
            "index": option_view.index,
            "option_type": option_view.option_type_name,
            "fields": dict(option_view.fields),
            "semantic_fingerprint": option_view.semantic_fingerprint,
            "local_card_uid": local_uids.get(option_view.index),
        }
        for option_view in window.options
    ]
    try:
        facts = PublicBattleFacts.parse(raw)
        public_facts: dict[str, object] = {
            "turn": facts.turn,
            "turn_action_count": facts.turn_action_count,
            "acting_player_index": facts.acting_player_index,
            "acting_prizes_remaining": facts.acting_prizes_remaining,
            "opponent_prizes_remaining": facts.opponent_prizes_remaining,
            "acting_active_energy_units": facts.acting_active_energy_units,
            "opponent_active_energy_units": facts.opponent_active_energy_units,
            "acting_bench_free": facts.acting_bench_free,
            "opponent_bench_free": facts.opponent_bench_free,
        }
    except UcisRuntimeError:
        public_facts = {"available": False}
    report = {
        "document_type": "ptcg_strategy_forge_ucis_scenario_inspection_v1",
        "schema_version": 1,
        "status": "passed",
        "scenario_id": scenario.get("scenario_id", ""),
        "window": {
            "select_type": window.select_type_name,
            "context": window.context_name,
            "min_count": window.min_count,
            "max_count": window.max_count,
            "remain_damage_counter": window.remain_damage_counter,
            "remain_energy_cost": window.remain_energy_cost,
            "options": options,
        },
        "public_facts": public_facts,
        "claims": {
            "public_only": True,
            "engine_execution": False,
            "production_authority": False,
        },
    }
    assert_public_report(report)
    return report


def run_ucis_sdk_walkthrough() -> dict[str, object]:
    process = subprocess.run(
        [sys.executable, str(ROOT / "demo/marnie-forge/sdk_walkthrough.py")],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        report = json.loads(process.stdout) if process.returncode == 0 else {}
    except json.JSONDecodeError:
        report = {}
    if type(report) is not dict or report.get("status") != "passed":
        return {
            "document_type": "ptcg_strategy_forge_ucis_sdk_walkthrough_v1",
            "schema_version": 1,
            "status": "failed",
            "error_code": "ucis_sdk_walkthrough_failed",
            "claims": {"engine_authority": False, "production_authority": False},
        }
    assert_public_report(report)
    return report


def run_suite(package_path: Path, suite_path: Path) -> dict[str, object]:
    if not suite_path.is_file() or suite_path.is_symlink():
        raise ValueError("scenario_suite_invalid")
    suite_path = suite_path.resolve()
    suite_root = suite_path.parent
    suite = load_json(suite_path)
    if (
        type(suite) is not dict
        or suite.get("document_type") != SUITE_DOCUMENT_TYPE
        or suite.get("schema_version") != 1
        or type(suite.get("cases")) is not list
        or not 1 <= len(suite["cases"]) <= 1000
    ):
        raise ValueError("scenario_suite_invalid")
    results: list[dict[str, object]] = []
    case_ids: set[str] = set()
    for case in suite["cases"]:
        if type(case) is not dict or set(case) != {"id", "path", "expect"} or type(case["expect"]) is not dict:
            raise ValueError("scenario_suite_invalid")
        case_id = case["id"]
        relative = case["path"]
        expected = case["expect"]
        if (
            type(case_id) is not str
            or not case_id.strip()
            or case_id in case_ids
            or type(relative) is not str
            or not relative
            or "\\" in relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or set(expected) - {"status", "error_code", "selected_indexes", "matched_rule_id", "selected_source"}
            or expected.get("status") not in {"passed", "error"}
        ):
            raise ValueError("scenario_suite_invalid")
        case_ids.add(case_id)
        scenario_path = (suite_root / relative).resolve()
        try:
            scenario_path.relative_to(suite_root)
        except ValueError as error:
            raise ValueError("scenario_suite_invalid") from error
        if not scenario_path.is_file() or scenario_path.is_symlink():
            raise ValueError("scenario_suite_invalid")
        try:
            scenario_document = load_json(scenario_path)
            simulation = (
                simulate_competitive_public_frame(package_path, scenario_path)
                if is_competitive_scenario(scenario_document)
                else simulate_public_window(package_path, scenario_path)
            )
            assert_public_report(simulation)
            observed = {
                "status": simulation["status"],
                "error_code": simulation.get("error_code", ""),
                "selected_indexes": simulation["decision"]["selected_indexes"],
                "matched_rule_ids": [row["rule_id"] for row in simulation["adapter"]["matched_rules"]],
                "selected_source": simulation["adjudication"]["selected_source"],
                "claims": simulation["claims"],
            }
        except DeveloperToolError as error:
            observed = {"status": "error", "error_code": error.code}
        accepted = observed.get("status") == expected.get("status")
        for key in ("error_code", "selected_indexes", "selected_source"):
            if key in expected and observed.get(key) != expected.get(key):
                accepted = False
        if "matched_rule_id" in expected and expected["matched_rule_id"] not in observed.get("matched_rule_ids", []):
            accepted = False
        claims = observed.get("claims")
        if isinstance(claims, dict) and (
            claims.get("engine_execution") is not False
            or claims.get("production_authority") is not False
            or claims.get("classic_fallback_used") is not False
        ):
            accepted = False
        results.append({"id": case["id"], "accepted": accepted, "expected": expected, "observed": observed})
    return {
        "document_type": "ptcg_strategy_forge_scenario_report_v1",
        "schema_version": 1,
        "status": "passed" if all(row["accepted"] for row in results) else "failed",
        "package_sha256": _sha(package_path),
        "case_count": len(results),
        "passed_count": sum(bool(row["accepted"]) for row in results),
        "cases": results,
    }


def _checked_artifact_target(output: Path) -> Path:
    output_input = Path(output)
    if output_input.exists() or output_input.is_symlink():
        raise ValueError("workspace_check_output_exists")
    try:
        parent = output_input.parent.resolve(strict=True)
    except OSError as error:
        raise ValueError("workspace_check_output_parent_missing") from error
    if not parent.is_dir():
        raise ValueError("workspace_check_output_parent_invalid")
    return parent / output_input.name


def _publish_checked_artifact(source: Path, output: Path) -> Path:
    target = _checked_artifact_target(output)
    parent = target.parent
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".ptcg-strategy-forge-check-",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as file:
            file.write(source.read_bytes())
            temporary = Path(file.name)
        os.replace(temporary, target)
    except Exception:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        raise
    return target.resolve()


def check_workspace(workspace: Path, *, output: Path | None = None) -> dict[str, object]:
    workspace_input = Path(workspace)
    if workspace_input.is_symlink():
        raise ValueError("workspace_check_invalid")
    try:
        workspace_root = workspace_input.resolve(strict=True)
    except OSError as error:
        raise ValueError("workspace_check_invalid") from error
    package_source = workspace_root / "package"
    scenario_suite = workspace_root / "scenario-suite.json"
    if not workspace_root.is_dir() or not package_source.is_dir() or not scenario_suite.is_file():
        raise ValueError("workspace_check_invalid")
    if output is not None:
        _checked_artifact_target(output)
    try:
        ucis_sdk = UcisDeveloperSdk.load(ROOT)
        ucis_catalog = ucis_sdk.capability_catalog()
        ucis_closure = dict(ucis_catalog["closure"])
        ucis_legacy = dict(ucis_catalog["legacy_closure"])
        ucis_coverage = dict(ucis_catalog["coverage_metrics"])
        ucis_qualification = _ucis_qualification(ROOT)
        ucis_accepted = all(
            ucis_closure.get(key) == 0
            for key in (
                "unregistered",
                "legacy_author_visible",
                "custom_prompt_builder",
                "silent_fallback",
            )
        ) and all(
            ucis_legacy.get(key) == 0
            for key in (
                "legacy_author_visible",
                "legacy_write_entrypoints",
                "dual_authority",
                "custom_prompt_builder",
            )
        ) and all(
            row.get("numerator") == row.get("denominator")
            for row in ucis_coverage.values()
        ) and bool(ucis_qualification["accepted"])
    except (OSError, UnicodeError, ValueError, UcisSdkError) as error:
        raise ValueError("workspace_ucis_contract_invalid") from error

    manifest_path = package_source / "strategy_package.json"
    package_manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    policy = package_manifest.get("policy", {})
    model_required = (
        package_manifest.get("document_type") == "strategy_package_v2"
        and isinstance(policy, dict)
        and policy.get("policy_mode") == "rules_with_model"
    )
    model_report: dict[str, object] = {
        "required": model_required,
        "status": "not_applicable",
        "cpu_only": True,
        "remote_inference": False,
    }
    if model_required:
        try:
            model_report = {
                "required": True,
                **model_conformance(package_source / "model/actor.ort"),
            }
        except OrtActorError as error:
            model_report = {
                "required": True,
                "status": "failed",
                "error_code": error.code,
                "cpu_only": True,
                "remote_inference": False,
            }

    with tempfile.TemporaryDirectory(prefix="ptcg-strategy-forge-check-") as temp_name:
        temp_root = Path(temp_name)
        package_a = temp_root / "workspace-a.ptcgai"
        package_b = temp_root / "workspace-b.ptcgai"
        build_a = build_development_package(package_source, package_a)
        build_b = build_development_package(package_source, package_b)
        deterministic = package_a.read_bytes() == package_b.read_bytes()
        validation = validate_development_package(package_a)
        scenarios = run_suite(package_a, scenario_suite)
        accepted = bool(
            deterministic
            and build_a["archive_sha256"] == build_b["archive_sha256"]
            and validation.get("status") == "valid"
            and scenarios.get("status") == "passed"
            and ucis_accepted
            and (not model_required or model_report.get("status") == "passed")
        )
        artifact_path: Path | None = None
        if accepted and output is not None:
            artifact_path = _publish_checked_artifact(package_a, output)
        report = {
            "document_type": "ptcg_strategy_forge_workspace_check_v1",
            "schema_version": 1,
            "status": "passed" if accepted else "failed",
            "build": {
                "package_id": build_a["package_id"],
                "package_version": build_a["package_version"],
                "archive_sha256": build_a["archive_sha256"],
                "archive_bytes": build_a["archive_bytes"],
                "second_archive_sha256": build_b["archive_sha256"],
                "deterministic": deterministic,
            },
            "validation": validation,
            "scenarios": scenarios,
            "model": model_report,
            "ucis": {
                "accepted": ucis_accepted,
                "ucis_generation": ucis_catalog["ucis_generation"],
                "contract_generation": ucis_catalog["contract_generation"],
                "registry_sha256": ucis_catalog["registry_sha256"],
                "catalog_scope_sha256": ucis_catalog["catalog_scope_sha256"],
                "coverage_ledger_sha256": ucis_catalog["coverage_ledger_sha256"],
                "primitive_count": len(ucis_catalog["primitives"]),
                "catalog_closure": ucis_closure,
                "legacy_closure": ucis_legacy,
                "coverage_metrics": ucis_coverage,
                "unsupported_capabilities": list(
                    ucis_catalog["unsupported_capabilities"]
                ),
                "qualification": ucis_qualification,
            },
            "artifact": {
                "written": artifact_path is not None,
                "path": str(artifact_path) if artifact_path is not None else "",
            },
            "claims": {
                "development_only": True,
                "production_ready": False,
                "engine_authority": False,
                "cabt_engine_parity": False,
            },
        }
    assert_public_report(report)
    return report


def run_demo(output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError("demo_output_exists")
    output.mkdir(parents=True)
    demo_root = ROOT / "demo/marnie-forge"
    source = demo_root / "package"
    suite = demo_root / "scenario-suite.json"
    baseline_source = output / "baseline-source"
    shutil.copytree(source, baseline_source)
    shutil.copy2(demo_root / "optimization/baseline_adapter.json", baseline_source / "policy/adapter.json")
    baseline_package = output / "baseline.ptcgai"
    build_development_package(baseline_source, baseline_package)
    positive_scenario = demo_root / "scenarios/01-positive.json"
    baseline_simulation = simulate_public_window(baseline_package, positive_scenario)
    baseline_red = baseline_simulation.get("status") == "failed" and baseline_simulation.get("error_code") == "simulation_expectation_failed"

    final_a = output / "forge-demo-a.ptcgai"
    final_b = output / "forge-demo-b.ptcgai"
    build_a = build_development_package(source, final_a)
    build_b = build_development_package(source, final_b)
    deterministic = final_a.read_bytes() == final_b.read_bytes()
    validation = validate_development_package(final_a)
    scenarios = run_suite(final_a, suite)
    sdk_walkthrough = run_ucis_sdk_walkthrough()
    accepted = bool(
        baseline_red
        and deterministic
        and validation.get("status") == "valid"
        and scenarios.get("status") == "passed"
        and sdk_walkthrough.get("status") == "passed"
    )
    report = {
        "document_type": "ptcg_strategy_forge_demo_report_v1",
        "schema_version": 1,
        "status": "passed" if accepted else "failed",
        "optimization": {
            "baseline_red": baseline_red,
            "baseline_selected_indexes": baseline_simulation.get("decision", {}).get("selected_indexes", []),
            "final_scenario_passed": scenarios.get("passed_count", 0),
            "final_scenario_total": scenarios.get("case_count", 0),
        },
        "build": {
            "package_id": build_a["package_id"],
            "package_version": build_a["package_version"],
            "archive_sha256": build_a["archive_sha256"],
            "archive_bytes": build_a["archive_bytes"],
            "second_archive_sha256": build_b["archive_sha256"],
            "deterministic": deterministic,
        },
        "validation": validation,
        "scenarios": scenarios,
        "ucis_sdk": sdk_walkthrough,
        "claims": {
            "development_only": True,
            "production_ready": False,
            "engine_authority": False,
            "cabt_engine_parity": False,
        },
    }
    write_json(output / "demo-report.json", report)
    return report


def _configure_model_workspace(workspace: Path) -> dict[str, object]:
    package_root = workspace / "package"
    manifest_path = package_root / "strategy_package.json"
    manifest = load_json(manifest_path)
    manifest["document_type"] = "strategy_package_v2"
    manifest["schema_version"] = 2
    manifest["compatibility"]["minimum_game_api"] = "ptcgdap-author-host-v2"
    capabilities = list(manifest["compatibility"].get("required_capabilities", []))
    if "learned_policy_head_v1" not in capabilities:
        capabilities.append("learned_policy_head_v1")
    manifest["compatibility"]["required_capabilities"] = capabilities
    manifest["policy"] = {
        **manifest["policy"],
        "weights_path": None,
        "policy_mode": "rules_with_model",
        "model_manifest_path": "model/model_manifest.json",
        "model_artifact_path": "model/actor.ort",
    }
    training_root = workspace / "model-source"
    package_model_root = package_root / "model"
    legacy_weights = package_root / "policy/weights.bin"
    if legacy_weights.exists():
        legacy_weights.unlink()
    training_root.mkdir()
    package_model_root.mkdir()
    onnx_path = training_root / "actor.onnx"
    ort_path = package_model_root / "actor.ort"
    source_report = write_linear_actor_onnx(onnx_path, [1] + [0] * 15)
    import_report = import_onnx_to_ort(onnx_path, ort_path)
    model_manifest = build_model_manifest(
        ort_path.read_bytes(),
        model_id=f"{manifest['package_id']}.actor",
        cabt_contract_sha256=CABT_CONTRACT_SHA256,
        card_catalog_sha256=CARD_CATALOG_SHA256,
        training_method="other",
        source_run_id="forge-model-template",
    )
    manifest_path.write_bytes(canonical_bytes(manifest))
    (package_model_root / "model_manifest.json").write_bytes(canonical_bytes(model_manifest))
    return {
        "policy_mode": "model",
        "package_document_type": "strategy_package_v2",
        "model_source": str(onnx_path.resolve()),
        "model_artifact": str(ort_path.resolve()),
        "model_artifact_sha256": import_report["artifact_sha256"],
        "operators": source_report["operators"],
        "training_required_for_quality": True,
    }


def _configure_rules_workspace(workspace: Path) -> dict[str, object]:
    package_root = workspace / "package"
    manifest_path = package_root / "strategy_package.json"
    manifest = load_json(manifest_path)
    manifest["document_type"] = "strategy_package_v2"
    manifest["schema_version"] = 2
    manifest["compatibility"]["minimum_game_api"] = "ptcgdap-author-host-v2"
    manifest["compatibility"]["required_capabilities"] = [
        capability
        for capability in manifest["compatibility"].get("required_capabilities", [])
        if capability != "learned_policy_head_v1"
    ]
    manifest["policy"] = {
        **manifest["policy"],
        "weights_path": None,
        "policy_mode": "rules_only",
        "model_manifest_path": None,
        "model_artifact_path": None,
    }
    legacy_weights = package_root / "policy/weights.bin"
    if legacy_weights.exists():
        legacy_weights.unlink()
    manifest_path.write_bytes(canonical_bytes(manifest))
    return {
        "policy_mode": "rules",
        "package_document_type": "strategy_package_v2",
        "model_artifact": None,
    }


def _model_import(source: Path, output: Path, manifest: Path, model_id: str) -> dict[str, object]:
    if manifest.exists() or manifest.is_symlink():
        raise OrtActorError("model_output_exists")
    report = import_onnx_to_ort(source, output)
    document = build_model_manifest(
        Path(output).read_bytes(),
        model_id=model_id,
        cabt_contract_sha256=CABT_CONTRACT_SHA256,
        card_catalog_sha256=CARD_CATALOG_SHA256,
    )
    manifest.write_bytes(canonical_bytes(document))
    return {**report, "model_manifest": str(manifest.resolve())}


def _model_tensorize(context_path: Path, output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise OrtActorError("model_output_exists")
    context = load_json(context_path)
    tensors = PublicActorTensorizer.tensorize(context)
    document = {
        "document_type": "ptcgai_public_actor_tensors_v1",
        "schema_version": 1,
        "profile_id": tensors.profile_id,
        "frame_i32": [list(tensors.frame_i32)],
        "frame_presence_i32": [list(tensors.frame_presence_i32)],
        "option_i32": [[list(row) for row in tensors.option_i32]],
        "option_presence_i32": [[list(row) for row in tensors.option_presence_i32]],
        "option_mask_i32": [list(tensors.option_mask_i32)],
        "row_to_current_index": list(tensors.row_to_current_index),
        "semantic_keys": list(tensors.semantic_keys),
        "public_only": True,
    }
    payload = canonical_bytes(document)
    output.write_bytes(payload)
    return {
        "document_type": "ptcgai_model_tensorize_report_v1",
        "status": "written",
        "output": str(output.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "option_count": len(tensors.row_to_current_index),
        "public_only": True,
    }
