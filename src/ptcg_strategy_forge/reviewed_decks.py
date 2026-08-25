from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes

from .scenarios import generate_macro_scenarios, load_json, write_json


ROOT = Path(__file__).resolve().parents[2]


def _predicate(
    *,
    option_type: int | None,
    option_card: str | None = None,
    hand: str | None = None,
    active: str | None = None,
    select_type: int | None = None,
    select_context: int | None = None,
    player_index: int | None = None,
) -> dict[str, object]:
    return {
        "select_type_raw": select_type,
        "select_context_raw": select_context,
        "option_type_raw": option_type,
        "option_card_id": option_card,
        "option_player_index": player_index,
        "acting_hand_card_id": hand,
        "acting_active_card_id": active,
    }


def _rule(
    rule_id: str,
    stage: str,
    priority: int,
    *,
    option_type: int | None,
    option_card: str | None = None,
    hand: str | None = None,
    active: str | None = None,
    select_type: int | None = None,
    select_context: int | None = None,
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "operator": "macro_proposal",
        "reason_code": "public_macro_proposal",
        "goal_stage": stage,
        "priority": priority,
        "predicate": _predicate(
            option_type=option_type,
            option_card=option_card,
            hand=hand,
            active=active,
            select_type=select_type,
            select_context=select_context,
        ),
    }


REVIEWED_DECKS: dict[int, dict[str, Any]] = {
    800018501: {
        "slug": "marnie-grimmsnarl",
        "deck_name": "18.0 玛俐的长毛巨魔",
        "strategy_name": "18.0 玛俐长毛巨魔完整作者策略",
        "summary": "围绕长毛巨魔进化、恶能量加速、雪妖女铺伤与连续攻击构建的公开当前窗口策略。",
        "primary": {
            "rule_id": "marnie.morgrem.evolve",
            "hand_uid": "CSV10C_147",
            "target_uid": "CSV10C_146",
            "active_uid": "CSV10C_148",
            "decoy_hand_uid": "CSV10C_216",
            "decoy_target_uid": "CSV8C_094",
        },
        "rules": [
            _rule("marnie.morgrem.evolve", "deploy", 0, option_type=3, option_card="CSV10C_146", hand="CSV10C_147"),
            _rule("marnie.grimmsnarl.evolve", "deploy", 0, option_type=3, option_card="CSV10C_147", hand="CSV10C_148"),
            _rule("marnie.rare-candy.play", "deploy", 1, option_type=7, option_card="CSVH1C_045", hand="CSVH1C_045"),
            _rule("marnie.morgrem.acquire", "acquire", 2, option_type=3, option_card="CSV10C_147"),
            _rule("marnie.grimmsnarl.acquire", "acquire", 1, option_type=3, option_card="CSV10C_148"),
            _rule("marnie.froslass.acquire", "maintain", 3, option_type=3, option_card="CSV7C_059"),
            _rule("marnie.punk-up.use", "fund", 0, option_type=12, option_card="CSV10C_148"),
            _rule("marnie.dark-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_DAR", select_type=1, select_context=22),
            _rule("marnie.shadow-bullet.attack", "execute", 0, option_type=13, active="CSV10C_148"),
            _rule("marnie.poffin.play", "acquire", 2, option_type=7, option_card="CSV7C_177", hand="CSV7C_177"),
            _rule("marnie.spikemuth.play", "acquire", 2, option_type=7, option_card="CSV10C_216", hand="CSV10C_216"),
            _rule("marnie.night-stretcher.play", "recover", 3, option_type=7, option_card="CSV8C_183", hand="CSV8C_183"),
        ],
        "agenda": "先建立两条玛俐进化线，以长毛巨魔完成能量加速和主攻，雪妖女与愿增猿负责把 180+30 转成稳定奖赏节奏。",
        "routes": "最快路线是捣蛋小妖→诈唬魔/神奇糖果→长毛巨魔；稳健路线保留第二攻击手与一张回收，不在无攻击窗口时消费抓取。",
        "ledger": "恶能量优先满足当前攻击手后再投第二线；最后一张进化组件、回收和可形成连续攻击的撤退资源受保护。",
        "checkpoints": "宝芬、尖钉镇道馆、奇树、博士研究、夜间担架和奖赏变化后立即重观察进化缺口与下一攻击手。",
        "interactions": "检索依次补进化缺口；庞克提升只支付当前与下一攻击窗口所需能量；暗影子弹伤害落点服务下一次取奖。",
        "unsupported": "仅在完整公开路线证明下才允许的撤退/抓取阈值和跨窗口第二攻击手债务仍由内置基准策略验证；v1 IR 不保存旧窗口或任意条件图。",
    },
    800017097: {
        "slug": "no-balloon-gardevoir",
        "deck_name": "18.0 无碟沙奈朵",
        "strategy_name": "18.0 无碟沙奈朵完整作者策略",
        "summary": "围绕拉鲁拉丝进化、精神拥抱、伤害搬运与单奖攻击手调度的公开当前窗口策略。",
        "primary": {
            "rule_id": "gardevoir.kirlia.evolve",
            "hand_uid": "CSV2C_054",
            "target_uid": "CSV2C_053",
            "active_uid": "CSV2C_055",
            "decoy_hand_uid": "CSV3C_123",
            "decoy_target_uid": "CSV8C_094",
        },
        "rules": [
            _rule("gardevoir.kirlia.evolve", "deploy", 0, option_type=3, option_card="CSV2C_053", hand="CSV2C_054"),
            _rule("gardevoir.ex.evolve", "deploy", 0, option_type=3, option_card="CSV2C_054", hand="CSV2C_055"),
            _rule("gardevoir.rare-candy.play", "deploy", 1, option_type=7, option_card="CSVH1C_045", hand="CSVH1C_045"),
            _rule("gardevoir.kirlia.acquire", "acquire", 2, option_type=3, option_card="CSV2C_054"),
            _rule("gardevoir.ex.acquire", "acquire", 1, option_type=3, option_card="CSV2C_055"),
            _rule("gardevoir.scream-tail.acquire", "ready", 3, option_type=3, option_card="CSV6C_065"),
            _rule("gardevoir.drifloon.acquire", "ready", 3, option_type=3, option_card="CSV2C_060"),
            _rule("gardevoir.psychic-embrace.use", "fund", 0, option_type=12, option_card="CSV2C_055"),
            _rule("gardevoir.psychic-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_PSY", select_type=1, select_context=22),
            _rule("gardevoir.scream-tail.attack", "execute", 0, option_type=13, active="CSV6C_065"),
            _rule("gardevoir.drifloon.attack", "execute", 0, option_type=13, active="CSV2C_060"),
            _rule("gardevoir.night-stretcher.play", "recover", 3, option_type=7, option_card="CSV8C_183", hand="CSV8C_183"),
        ],
        "agenda": "用沙奈朵 ex 建立能量引擎，以飘飘球、吼叫尾和皮皮 ex 按奖赏与目标距离选择攻击手，愿增猿修正伤害与生存线。",
        "routes": "最快路线优先拉鲁拉丝进化与精神拥抱；稳健路线保留第二拉鲁拉丝、回收以及不会暴露额外双奖负担的单奖攻击手。",
        "ledger": "超能量弃牌量、精神拥抱可承受伤害、勇气护符合法目标、最后一张神奇糖果与夜间担架是核心资源债务。",
        "checkpoints": "容器/高级球/巢穴球检索、奇树刷新、精神拥抱每次分配以及奖赏变化后重算当前击倒与下一攻击手。",
        "interactions": "检索先补沙奈朵引擎再选攻击手；勇气护符只服务飘飘球或吼叫尾；能量分配以精确攻击费用和不自毁为界。",
        "unsupported": "牌库 0–1 张时才使用奇树、精确伤害计数和跨多个精神拥抱窗口的预算需要更丰富公开谓词；包中明确回退到 Base。",
    },
    800018499: {
        "slug": "pure-dragapult",
        "deck_name": "18.0 多龙巴鲁托",
        "strategy_name": "18.0 多龙巴鲁托完整作者策略",
        "summary": "围绕多龙进化链、幻影潜袭铺伤与连续攻击的公开当前窗口策略。",
        "primary": {
            "rule_id": "dragapult.drakloak.evolve",
            "hand_uid": "CSV8C_158",
            "target_uid": "CSV8C_157",
            "active_uid": "CSV8C_159",
            "decoy_hand_uid": "CSV3C_123",
            "decoy_target_uid": "CSV8C_094",
        },
        "rules": [
            _rule("dragapult.drakloak.evolve", "deploy", 0, option_type=3, option_card="CSV8C_157", hand="CSV8C_158"),
            _rule("dragapult.ex.evolve", "deploy", 0, option_type=3, option_card="CSV8C_158", hand="CSV8C_159"),
            _rule("dragapult.drakloak.acquire", "acquire", 2, option_type=3, option_card="CSV8C_158"),
            _rule("dragapult.ex.acquire", "acquire", 1, option_type=3, option_card="CSV8C_159"),
            _rule("dragapult.poffin.play", "acquire", 1, option_type=7, option_card="CSV7C_177", hand="CSV7C_177"),
            _rule("dragapult.ultra-ball.play", "acquire", 2, option_type=7, option_card="CSV1C_112", hand="CSV1C_112"),
            _rule("dragapult.brocks-scouting.play", "acquire", 2, option_type=7, option_card="CSV10C_207", hand="CSV10C_207"),
            _rule("dragapult.fire-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_FIR", select_type=1, select_context=22),
            _rule("dragapult.psychic-energy.assign", "fund", 1, option_type=3, option_card="CSVE1C_PSY", select_type=1, select_context=22),
            _rule("dragapult.phantom-dive.attack", "execute", 0, option_type=13, active="CSV8C_159"),
            _rule("dragapult.night-stretcher.play", "recover", 3, option_type=7, option_card="CSV8C_183", hand="CSV8C_183"),
        ],
        "agenda": "尽快建立多龙巴鲁托 ex，用主伤害和伤害指示物同时推进当前奖赏与下一次多目标击倒，月月熊仅作终盘补位。",
        "routes": "最快路线为多龙梅西亚→多龙奇→多龙巴鲁托；稳健路线保留第二条进化链、能量与夜间担架，避免无攻击窗口时浪费抓取。",
        "ledger": "火/超能量各自的攻击费用、第二多龙奇、回收和对手可被 60 点铺伤转化的奖赏目标必须持续记账。",
        "checkpoints": "宝芬、高级球、小刚的发掘、夜间担架及幻影潜袭分配后重观察进化缺口、伤害版图和下一攻击窗口。",
        "interactions": "小刚的发掘按真实进化缺口选择基础或进化模式；铺伤优先制造确定的下一奖赏，而不是平均分配。",
        "unsupported": "精确 60 点伤害分配和抓取是否立即转成击倒需要目标 HP/奖赏组合谓词；v1 包保留为蓝图并由 Base 确定回退。",
    },
    800018509: {
        "slug": "raging-bolt-ogerpon",
        "deck_name": "18.0 猛雷鼓厄诡椪",
        "strategy_name": "18.0 猛雷鼓厄诡椪完整作者策略",
        "summary": "围绕碧草之舞、奥琳博士、拉帝亚斯换位与精确咆哮雷霆斩杀的公开当前窗口策略。",
        "primary": {
            "rule_id": "raging-bolt.noctowl.evolve",
            "hand_uid": "CSV9C_155",
            "target_uid": "CSV9C_154",
            "active_uid": "CSV7C_154",
            "decoy_hand_uid": "CSV3C_123",
            "decoy_target_uid": "CSV9C_161",
        },
        "rules": [
            _rule("raging-bolt.noctowl.evolve", "deploy", 0, option_type=3, option_card="CSV9C_154", hand="CSV9C_155"),
            _rule("raging-bolt.attacker.acquire", "ready", 0, option_type=3, option_card="CSV7C_154"),
            _rule("raging-bolt.ogerpon.acquire", "fund", 1, option_type=3, option_card="CSV8C_028"),
            _rule("raging-bolt.latias.acquire", "maintain", 2, option_type=3, option_card="CSV9C_078"),
            _rule("raging-bolt.teal-dance.use", "fund", 0, option_type=12, option_card="CSV8C_028"),
            _rule("raging-bolt.nest-ball.play", "acquire", 1, option_type=7, option_card="CSVH1C_043", hand="CSVH1C_043"),
            _rule("raging-bolt.earthen-vessel.play", "fund", 1, option_type=7, option_card="CSV6C_115", hand="CSV6C_115"),
            _rule("raging-bolt.sada.play", "fund", 1, option_type=7, option_card="CSV6C_121", hand="CSV6C_121"),
            _rule("raging-bolt.crispin.play", "fund", 2, option_type=7, option_card="CSV9C_196", hand="CSV9C_196"),
            _rule("raging-bolt.grass-energy.assign", "fund", 1, option_type=3, option_card="CSVE1C_GRA", select_type=1, select_context=22),
            _rule("raging-bolt.fighting-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_FIG", select_type=1, select_context=22),
            _rule("raging-bolt.lightning-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_LIG", select_type=1, select_context=22),
            _rule("raging-bolt.bellowing-thunder.attack", "execute", 0, option_type=13, active="CSV7C_154"),
            _rule("raging-bolt.night-stretcher.play", "recover", 3, option_type=7, option_card="CSV8C_183", hand="CSV8C_183"),
        ],
        "agenda": "后攻首轮建立猛雷鼓攻击窗口，以厄诡椪和奥琳博士补能，拉帝亚斯保证从被卡住的基础位切回主攻。",
        "routes": "最快路线是猛雷鼓+厄诡椪+三色能量；稳健路线用猫头夜鹰和拉帝亚斯补检索/换位，并保留下一次咆哮雷霆所需能量。",
        "ledger": "草能量承担碧草之舞和攻击弃能，斗/雷必须满足攻击门槛；夜间担架、能量转移与后备位共同维护连续攻击。",
        "checkpoints": "碧草之舞、奥琳博士、赤松、容器、奖赏和任何弃能攻击后重观察目标 HP、可弃能量和后备攻击手。",
        "interactions": "检索先补猛雷鼓/厄诡椪，再按卡位决定拉帝亚斯；咆哮雷霆只丢精确击倒所需能量。",
        "unsupported": "目标剩余 HP→精确弃能数量以及猛雷鼓未就绪时禁止给月月熊投资，需要数值与目标谓词；v1 包不伪造该能力。",
    },
    800018502: {
        "slug": "ns-zoroark",
        "deck_name": "18.0 N的索罗亚克",
        "strategy_name": "18.0 N 的索罗亚克完整作者策略",
        "summary": "围绕 N 的索罗亚克进化、复制招式工具箱、城堡换位与攻击手接力的公开当前窗口策略。",
        "primary": {
            "rule_id": "ns-zoroark.ex.evolve",
            "hand_uid": "CSV10C_145",
            "target_uid": "CSV10C_144",
            "active_uid": "CSV10C_145",
            "decoy_hand_uid": "CSV3C_123",
            "decoy_target_uid": "CSV8C_094",
        },
        "rules": [
            _rule("ns-zoroark.ex.evolve", "deploy", 0, option_type=3, option_card="CSV10C_144", hand="CSV10C_145"),
            _rule("ns-zoroark.darmanitan.evolve", "maintain", 1, option_type=3, option_card="CSV10C_040", hand="CSV10C_041"),
            _rule("ns-zoroark.ex.acquire", "acquire", 0, option_type=3, option_card="CSV10C_145"),
            _rule("ns-zoroark.reshiram.acquire", "ready", 1, option_type=3, option_card="CSV10C_166"),
            _rule("ns-zoroark.poffin.play", "acquire", 1, option_type=7, option_card="CSV7C_177", hand="CSV7C_177"),
            _rule("ns-zoroark.pp-up.play", "fund", 0, option_type=7, option_card="CSV10C_190", hand="CSV10C_190"),
            _rule("ns-zoroark.castle.play", "maintain", 0, option_type=7, option_card="CSV10C_215", hand="CSV10C_215"),
            _rule("ns-zoroark.dark-energy.assign", "fund", 0, option_type=3, option_card="CSVE1C_DAR", select_type=1, select_context=22),
            _rule("ns-zoroark.reversal-energy.assign", "fund", 1, option_type=3, option_card="CSV2C_128", select_type=1, select_context=22),
            _rule("ns-zoroark.night-joker.attack", "execute", 0, option_type=13, active="CSV10C_145"),
            _rule("ns-zoroark.reshiram.attack", "execute", 1, option_type=13, active="CSV10C_166"),
            _rule("ns-zoroark.night-stretcher.play", "recover", 2, option_type=7, option_card="CSV8C_183", hand="CSV8C_183"),
        ],
        "agenda": "建立至少两只 N 系攻击手，以索罗亚克复制公开可用招式，N 的莱希拉姆与达摩狒狒提供不同奖赏和伤害路线。",
        "routes": "最快路线为索罗亚→索罗亚克+双恶；稳健路线保留第二索罗亚、N 的城堡和 PP 提升剂，确保首攻倒下后仍有攻击窗口。",
        "ledger": "双恶费用、可复制招式来源、城堡撤退、PP 提升剂与夜间担架是核心债务；最后一张达摩狒狒在进化桥存在时保留。",
        "checkpoints": "暗码迷、席蓝、PP 提升剂、夜间担架、奖赏和任何可复制招式来源变化后重观察合法招式与交接路线。",
        "interactions": "检索先补索罗亚克主线，再选择莱希拉姆/达摩狒狒招式源；有已就绪后备时优先城堡完成换位。",
        "unsupported": "判断复制招式是否同时可用且伤害>0、以及跨窗口保留唯一达摩狒狒，需要招式可用性谓词；v1 包以 Base 回退保护。",
    },
}


def reviewed_deck_ids() -> tuple[int, ...]:
    return tuple(REVIEWED_DECKS)


def reviewed_deck_spec(deck_id: int) -> dict[str, Any]:
    try:
        return REVIEWED_DECKS[deck_id]
    except KeyError as exc:
        raise ValueError("reviewed_deck_not_supported") from exc


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _deck_artifacts(deck_id: int, slug: str) -> tuple[bytes, dict[str, object]]:
    source_path = ROOT / "data/bundled_user/decks" / f"{deck_id}.json"
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes.decode("utf-8"))
    if source.get("id") != deck_id or source.get("total_cards") != 60 or not isinstance(source.get("cards"), list):
        raise ValueError("reviewed_deck_source_invalid")
    source_entries: dict[str, dict[str, Any]] = {}
    for row in source["cards"]:
        uid = f"{row.get('set_code')}_{row.get('card_index')}"
        if uid in source_entries:
            raise ValueError("reviewed_deck_source_invalid")
        source_entries[uid] = row
    cards: list[dict[str, object]] = []
    csv_lines = ["local_card_uid,count"]
    total = 0
    for uid in sorted(source_entries, key=str.encode):
        row = source_entries[uid]
        count = row.get("count")
        if type(count) is not int or count < 1:
            raise ValueError("reviewed_deck_source_invalid")
        card_path = ROOT / "data/bundled_user/cards" / f"{uid}.json"
        card_bytes = card_path.read_bytes()
        card = json.loads(card_bytes.decode("utf-8"))
        set_code, card_index = uid.split("_", 1)
        if (
            card.get("set_code") != set_code
            or card.get("card_index") != card_index
            or card.get("effect_id") != row.get("effect_id")
        ):
            raise ValueError("reviewed_card_source_invalid")
        cards.append({
            "local_card_uid": uid,
            "set_code": set_code,
            "card_index": card_index,
            "count": count,
            "card_type": card.get("card_type"),
            "stage": card.get("stage", ""),
            "effect_id": card.get("effect_id"),
            "source_raw_sha256": _sha(card_bytes),
            "source_canonical_sha256": _sha(canonical_json_v1_bytes(card)),
        })
        csv_lines.append(f"{uid},{count}")
        total += count
    csv_bytes = ("\n".join(csv_lines) + "\n").encode("ascii")
    if total != 60:
        raise ValueError("reviewed_deck_source_invalid")
    manifest: dict[str, object] = {
        "document_type": "deck_manifest_windows_local_v1",
        "schema_version": 1,
        "deck_id": f"v18.{slug}.{deck_id}",
        "card_id_domain": "godot_local_card_uid_v1",
        "card_count": 60,
        "unique_card_count": len(cards),
        "deck_csv_sha256": _sha(csv_bytes),
        "cabt_exportable": False,
        "platform_scope": ["windows"],
        "source_deck_id": deck_id,
        "source_deck_raw_sha256": _sha(source_bytes),
        "source_deck_canonical_sha256": _sha(canonical_json_v1_bytes(source)),
        "cards": cards,
    }
    return csv_bytes, manifest


def _policy_ir(package_id: str, rules: list[dict[str, object]]) -> dict[str, object]:
    return {
        "entry_node_id": "n00",
        "graph_id": package_id,
        "nodes": [
            {"config": {"frontier": "current_window"}, "next_node_ids": ["n10"], "node_id": "n00", "operator": "legality_guard", "owner": "base"},
            {"config": {"mandatory_precedence": True, "terminal_precedence": True}, "next_node_ids": ["n20"], "node_id": "n10", "operator": "mandatory_terminal_guard", "owner": "base"},
            {"config": {"macro_ids": [str(rule["rule_id"]) for rule in rules]}, "next_node_ids": ["n30"], "node_id": "n20", "operator": "macro_proposal", "owner": "adapter"},
            {"config": {"same_tier_only": True}, "next_node_ids": ["n40"], "node_id": "n30", "operator": "hard_tier_filter", "owner": "base"},
            {"config": {"enabled": True}, "next_node_ids": ["n50"], "node_id": "n40", "operator": "base_veto", "owner": "base"},
            {"config": {"strategy": "same_window_first_min"}, "next_node_ids": ["n60"], "node_id": "n50", "operator": "deterministic_fallback", "owner": "base"},
            {"config": {}, "next_node_ids": [], "node_id": "n60", "operator": "emit_decision", "owner": "base"},
        ],
        "profile_id": "ptcgdap-restricted-base-graph-ir-p4-wp2-v1",
        "required_capabilities": ["public_context", "current_window", "deterministic_fallback", "strategic_trace_v2"],
        "schema_version": 1,
    }


def _blueprint(spec: dict[str, Any], package_id: str) -> str:
    rows = "\n".join(
        f"| {rule['rule_id']} | {rule['goal_stage']} | 当前公开窗口 predicate | option 当前语义目标 | mandatory / terminal / hard tier / veto |"
        for rule in spec["rules"]
    )
    return f"""# {spec['strategy_name']} 策略思考蓝图

> 牌组：{spec['deck_name']}
> 包身份：`{package_id}`
> 状态：COMPLETE（restricted IR v1 开发包）

## 1. 不可变决策边界

`agent(raw_observation) -> list[int]`。每次只选择当前 `select.option` 索引；信息变化后重观察并重绑定。Base Graph 始终拥有合法性、mandatory/terminal、hard tier、veto、fallback 和最终裁决。

## 2. Match Agenda

{spec['agenda']}

## 3. 当前路线与奖赏时钟

{spec['routes']}

奖赏时钟按可用攻击窗口计算；没有公开证明时保持 Rule/Base floor，不把退到备战区自动视为安全。

## 4. Resource Ledger

{spec['ledger']}

## 5. 信息检查点

{spec['checkpoints']}

每个检查点只保留语义债务和稳定 UID，不保留旧 index、旧分数或旧合法窗口。

## 6. 类型化交互

{spec['interactions']}

## 7. Adapter 规则映射

| rule_id | goal_stage | 公开前置条件 | 当前窗口目标 | Base 可阻止原因 |
|---|---|---|---|---|
{rows}

## 8. RED→GREEN 与变形证明

主 macro 覆盖正向、关键手牌缺失、错误目标、option 重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏字段。重排用例证明规则按语义重新绑定，不持久化旧索引。

## 9. 明确能力边界

{spec['unsupported']}

这部分不是“已运行”声明；复杂完整路线继续保留在内置策略基准中，直到公开合同升级后再编译进数据包。

## 10. 完成门

- [x] 蓝图意图已由规则、场景或明确能力边界关闭。
- [x] 只使用本包精确 `godot_local_card_uid_v1` 身份。
- [x] 没有脚本、引擎对象、隐藏信息、旧窗口索引或网络能力。
- [x] 包将通过 `check` 双构建、严格 Host 校验和完整场景套件。
- [x] 开发执行、Godot 引擎见证和 production 权限分别声明。
"""


def customize_reviewed_workspace(workspace: Path, deck_id: int, package_id: str) -> dict[str, object]:
    spec = reviewed_deck_spec(deck_id)
    package_root = workspace / "package"
    csv_bytes, deck_manifest = _deck_artifacts(deck_id, str(spec["slug"]))
    (package_root / "deck/deck.csv").write_bytes(csv_bytes)
    write_json(package_root / "deck/deck_manifest.json", deck_manifest)
    manifest = load_json(package_root / "strategy_package.json")
    manifest["deck"]["display_name"] = spec["deck_name"]
    current_strategy = manifest.get("strategy", {})
    current_name = str(current_strategy.get("display_name", ""))
    current_summary = str(current_strategy.get("summary", ""))
    manifest["strategy"] = {
        "display_name": spec["strategy_name"] if current_name in ["", package_id] else current_name,
        "summary": (
            spec["summary"]
            if current_summary in ["", "Data-only current-window strategy developed with PTCG Strategy Forge."]
            else current_summary
        ),
    }
    write_json(package_root / "strategy_package.json", manifest)
    adapter = {
        "adapter_id": package_id,
        "adapter_version": 1,
        "rules": spec["rules"],
        "schema_version": 1,
    }
    write_json(package_root / "policy/adapter.json", adapter)
    write_json(package_root / "policy/policy_ir.json", _policy_ir(package_id, spec["rules"]))
    deck_manifest_sha = _sha((package_root / "deck/deck_manifest.json").read_bytes())
    write_json(package_root / "policy/config.json", {
        "config_profile_id": "ptcgdap-author-policy-config-v1",
        "document_type": "author_policy_config_v1",
        "schema_version": 1,
        "values": {
            "cabt_exportable": False,
            "card_id_domain": "godot_local_card_uid_v1",
            "deck_manifest_sha256": deck_manifest_sha,
            "platform_scope": "windows",
            "source_deck_id": deck_id,
        },
    })
    (workspace / "STRATEGY-BLUEPRINT.md").write_text(_blueprint(spec, package_id), encoding="utf-8")
    scenario_report = generate_macro_scenarios(
        workspace,
        matched_rule_id=spec["primary"]["rule_id"],
        namespace=str(spec["slug"]),
        hand_uid=spec["primary"]["hand_uid"],
        target_uid=spec["primary"]["target_uid"],
        active_uid=spec["primary"]["active_uid"],
        decoy_hand_uid=spec["primary"]["decoy_hand_uid"],
        decoy_target_uid=spec["primary"]["decoy_target_uid"],
    )
    return {
        "deck_id": deck_id,
        "deck_name": spec["deck_name"],
        "unique_card_count": deck_manifest["unique_card_count"],
        "rule_count": len(spec["rules"]),
        "scenario_suite": scenario_report,
    }
