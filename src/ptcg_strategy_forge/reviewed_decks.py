from __future__ import annotations

import copy
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
    646600: {
        "slug": "marnies-gift-box",
        "deck_name": "玛丽的礼盒",
        "strategy_name": "玛丽的礼盒",
        "summary": "波导的勇者为宁波第五名构筑研发的雪妖女、愿增猿与玛俐的长毛巨魔 ex 公共伤害规划策略。",
        "competitive_v2": True,
        "competitive_builder": "marnies_gift_box",
        "rules": [
            {"rule_id": "opening.budew-lock", "goal_stage": "deploy"},
            {"rule_id": "opening.impidimp-engine", "goal_stage": "deploy"},
            {"rule_id": "grimmsnarl.punk-up", "goal_stage": "fund"},
            {"rule_id": "punk-up.target-current-debt", "goal_stage": "fund"},
            {"rule_id": "munkidori.adrena-brain", "goal_stage": "execute"},
            {"rule_id": "damage.best-transfer-target", "goal_stage": "execute"},
            {"rule_id": "attack.shadow-bullet", "goal_stage": "execute"},
            {"rule_id": "damage.shadow-bullet-bench-target", "goal_stage": "execute"},
            {"rule_id": "handoff.ready-grimmsnarl", "goal_stage": "ready"},
            {"rule_id": "handoff.single-prize-bridge", "goal_stage": "recover"},
            {"rule_id": "devolution.public-lethal", "goal_stage": "execute"},
        ],
        "agenda": "以 2+2+2 的厄诡椪 ex 奖赏路线为首选；双雪妖女在能力密集场面提供回合间铺伤，愿增猿把己方指示物转为精确击倒债务，长毛巨魔 ex 用 180+后排30 连续完成两奖转换。",
        "routes": "最快路线是含羞苞有效封锁争取窗口，或捣蛋小妖→诈唬魔/神奇糖果→长毛巨魔；稳健路线同时建立双雪妖女、带恶能量愿增猿和一只仅差至多一能量的备用长毛巨魔。",
        "ledger": "庞克泵感只取得当前与备用长毛巨魔的真实双恶债务，最多再为可经能量转移启动的愿增猿准备一张；手贴优先愿增猿，低牌库禁止无收益抽滤。",
        "checkpoints": "每次检索、抽牌、硬币结果、能力使用、伤害移动、对手行动、治疗、进化/退化、奖赏变化及当前选项提交后都重新观察、重新计算并按稳定公共实体序号重绑定。",
        "interactions": "愿增猿按来源→精确数量→目标三阶段执行；暗影子弹后排30优先下一只两奖、下一次雪妖女检查或退化致死目标；老大和反击捕捉器只在本回合存在真实攻击窗口时消费。",
        "unsupported": "策略不读取牌库顺序、对手手牌或引擎对象；已登记的叶伊布 ex 后排治疗会按公开能量与攻击费用计入响应风险，其他未登记治疗/防护、隐藏信息和未来随机抽牌仍由 Base 确定性回退。",
    },
    800018880: {
        "slug": "ethans-typhlosion",
        "deck_name": "18.0 阿响的火暴兽",
        "strategy_name": "18.0 阿响的火暴兽 Competitive IR v2 策略",
        "summary": "围绕阿响的火岩鼠检索、阿响的冒险弃牌伤害、大比鸟 ex 信息引擎和双火暴兽连续攻击构建的公开当前窗口策略。",
        "competitive_v2": True,
        "competitive_builder": "ethans_typhlosion",
        "rules": [
            {"rule_id": "main.arven-development", "goal_stage": "acquire"},
            {"rule_id": "main.evolve-quilava", "goal_stage": "deploy"},
            {"rule_id": "main.evolve-typhlosion", "goal_stage": "deploy"},
            {"rule_id": "main.evolve-pidgeot", "goal_stage": "deploy"},
            {"rule_id": "quilava.journey-bond", "goal_stage": "acquire"},
            {"rule_id": "pidgeot.quick-search", "goal_stage": "acquire"},
            {"rule_id": "search.adventure.typhlosion-first", "goal_stage": "acquire"},
            {"rule_id": "search.adventure.fire-energy", "goal_stage": "fund"},
            {"rule_id": "attack.partner-blast-ko", "goal_stage": "execute"},
            {"rule_id": "handoff.ready-typhlosion", "goal_stage": "ready"},
            {"rule_id": "main.stop-low-deck-information", "goal_stage": "maintain"},
        ],
        "agenda": "以单奖火暴兽的连续攻击压缩奖赏交换。弃牌区阿响的冒险从 0 到 4 张时，搭档爆破的公开伤害阶梯为 40/100/160/220/280；最快路线在 2 张冒险时用一火达到 160，稳健路线同时维持第二只火暴兽与大比鸟 ex。",
        "routes": "开局优先形成火球鼠与波波两个不同进化根；派帕取得友好宝芬与进化 TM，或用神奇糖果直接完成当前最紧迫的火暴兽/大比鸟线。每次火岩鼠旅途牵绊、大比鸟音速搜索和阿响的冒险检索后都进入新的信息纪元。",
        "ledger": "主攻火暴兽的搭档爆破只需一火，第二火只在爆热炮 160 确实补足当前击倒或维持连续攻击时投入。阿响的冒险既是检索资源也是弃牌伤害资源；至少保留一条后续火球鼠→火岩鼠→火暴兽链和一个备战位。",
        "checkpoints": "每次检索、抽牌、能力、支援者结算、进化、手贴、奖赏变化及当前选项提交后都重新观察；只保留目标角色、公开弃牌区冒险数量和下一攻击手债务，不保存旧索引或旧分数。",
        "interactions": "友好宝芬精确铺两个不同根；进化 TM 在 fresh window 中分别绑定火岩鼠与比比鸟；旅途牵绊只取阿响的冒险；冒险最多取三张时按当前缺口选择火暴兽/火岩鼠线与基本火能量；老大/反击捕捉器仅在前场真实可攻时消费。",
        "unsupported": "当前 data-only 包不推测牌库顺序、奖赏内容或对手手牌。搭档爆破的真实动态伤害必须由 Godot 当前攻击 option 的公开 projected damage/KO 证明；若 Host 未投影该效果，策略保持 Base 回退并登记为 Host/能力注册 Block。",
    },
    800052301: {
        "slug": "ogerpon-crustle-v523a",
        "deck_name": "18.0 厄诡椪岩殿居蟹 v5.23a 迁移",
        "strategy_name": "18.0 厄诡椪岩殿居蟹 v5.23a Competitive IR v2 策略",
        "summary": "把 Kaggle v5.23a 厄诡椪/岩殿居蟹冠军线迁移为纯数据、公开当前窗口的 Godot Competitive IR v2 策略。",
        "competitive_v2": True,
        "rules": [
            {"rule_id": "ogerpon.teal-dance", "goal_stage": "fund"},
            {"rule_id": "crustle.evolve-funded", "goal_stage": "deploy"},
            {"rule_id": "crustle.attack", "goal_stage": "execute"},
            {"rule_id": "ogerpon.attack", "goal_stage": "execute"},
            {"rule_id": "handoff.articuno-certified-bridge", "goal_stage": "recover"},
        ],
        "agenda": "厄诡椪既是抽牌/充能引擎也是双奖主攻；岩殿居蟹把真实的宝可梦 ex 伤害路线转成单奖墙与 120 点取奖窗口；火箭队的急冻鸟只在公开奖赏时钟和退出路径都成立时作桥。",
        "routes": "优先建立至少两只厄诡椪和一条石居蟹线。每个攻击回合先结算仍安全的碧草之舞并重观察，再完成当前攻击与下一攻击手的精确三能量账本。支援者按公开阶段和场面债务分工：前中期没有就绪攻击手且仍有能量债务时用奇树重启；对手进入三奖以内且我方仍有至少三奖时用奇树压缩其后续资源；裁判只保留在前六回合、对手仍有至少四奖且我方攻击时钟落后的干扰线。",
        "ledger": "厄诡椪通常以三草为攻击完成线；岩殿居蟹以三草等价支付 GCC。已满足费用的单位不再无证据过投；好伤药按治疗→弃能→重新补能的完整 transaction 评估。",
        "checkpoints": "碧草之舞抽牌、捕虫套装/太晶珠/捕获香氛/能量输送检索、硬币分支、好伤药弃能、能量转移、奖赏与出战窗口后全部重观察。",
        "interactions": "检索绑定当前缺口而不是旧索引；捕虫套装精确选择最多两张有效草系资源；捕获香氛按本次正反面暴露的合法候选重新绑定；出战同时比较奖赏价值、能量债务和攻击就绪度。",
        "unsupported": "当前公开帧没有通用的对手 mechanic/特性影响标签，监视塔的“无色特性确有影响”证明和岩殿居蟹对实际 ex 招式来源的完整证书不能由包猜测；这些窗口保持 Base 回退并登记为观察限制，而不是读取隐藏信息。",
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
    # Strategic Trace v2 limits one macro proposal to 64 semantic macro IDs,
    # while Competitive Policy v2 intentionally permits up to 512 score rules.
    # For larger adapters the IR records the policy layer as one macro proposal;
    # the complete, executable rule inventory remains sealed in adapter.json.
    rule_ids = [str(rule["rule_id"]) for rule in rules]
    macro_ids = rule_ids if len(rule_ids) <= 64 else ["competitive.score-rules"]
    return {
        "entry_node_id": "n00",
        "graph_id": package_id,
        "nodes": [
            {"config": {"frontier": "current_window"}, "next_node_ids": ["n10"], "node_id": "n00", "operator": "legality_guard", "owner": "base"},
            {"config": {"mandatory_precedence": True, "terminal_precedence": True}, "next_node_ids": ["n20"], "node_id": "n10", "operator": "mandatory_terminal_guard", "owner": "base"},
            {"config": {"macro_ids": macro_ids}, "next_node_ids": ["n30"], "node_id": "n20", "operator": "macro_proposal", "owner": "adapter"},
            {"config": {"same_tier_only": True}, "next_node_ids": ["n40"], "node_id": "n30", "operator": "hard_tier_filter", "owner": "base"},
            {"config": {"enabled": True}, "next_node_ids": ["n50"], "node_id": "n40", "operator": "base_veto", "owner": "base"},
            {"config": {"strategy": "same_window_first_min"}, "next_node_ids": ["n60"], "node_id": "n50", "operator": "deterministic_fallback", "owner": "base"},
            {"config": {}, "next_node_ids": [], "node_id": "n60", "operator": "emit_decision", "owner": "base"},
        ],
        "profile_id": "ptcgdap-restricted-base-graph-ir-p4-wp2-v1",
        "required_capabilities": ["public_context", "current_window", "deterministic_fallback", "strategic_trace_v2"],
        "schema_version": 1,
    }


def _v2_condition(
    fact: str,
    op: str,
    value: object,
    *,
    card_uid: str | None = None,
) -> dict[str, object]:
    return {"fact": fact, "op": op, "value": value, "card_uid": card_uid}


def _v2_rule(
    rule_id: str,
    goal_id: str,
    stage: str,
    channel: str,
    score: int,
    *conditions: dict[str, object],
    score_terms: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "goal_id": goal_id,
        "goal_stage": stage,
        "channel": channel,
        "horizon": 0,
        "confidence_milli": 1000,
        "base_score": score,
        "when": list(conditions),
        "score_terms": list(score_terms or []),
    }


def _ogerpon_competitive_adapter(package_id: str, adapter_version: int = 6) -> dict[str, object]:
    """Compile the portable, public portion of the frozen Kaggle v5.23a plan."""

    ogerpon = "CSV8C_028"
    dwebble = "CSV10C_009"
    crustle = "CSV10C_010"
    articuno = "CSV10C_052"
    grass = "CSVE1C_GRA"
    bug_set = "CSV8C_182"
    energy_switch = "CSVH1aC_008"
    energy_search = "CSVH1C_035"
    hammer = "CSV1C_108"
    pokegear = "CSV2C_113"
    tera_orb = "CSV9C_181"
    hyper_potion = "CSV10C_189"
    aroma = "CS6aC_120"
    cape = "CSV7C_187"
    boss = "CSVH1aC_023"
    judge = "CSV10C_206"
    iono = "CSV3C_123"
    lively = "CSV9C_206"
    watchtower = "CSV10C_219"
    teal_dance_deck_reserve = 4

    def c(fact: str, op: str, value: object, card_uid: str | None = None) -> dict[str, object]:
        return _v2_condition(fact, op, value, card_uid=card_uid)

    goals = [
        {
            "goal_id": "ogerpon-prize-route",
            "stage": "execute",
            "priority": 900,
            "requirements": [{
                "card_uid": ogerpon,
                "ready_target_count": 1,
                "energy_required": 3,
                "energy_requirements": [{"energy_uid": grass, "count": 3}],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "ogerpon-engine",
            "stage": "fund",
            "priority": 850,
            "requirements": [{
                "card_uid": ogerpon,
                "ready_target_count": 2,
                "energy_required": 1,
                "energy_requirements": [{"energy_uid": grass, "count": 1}],
                "attack_index": None,
                "ability_index": 0,
            }],
        },
        {
            "goal_id": "crustle-wall-route",
            "stage": "ready",
            "priority": 800,
            "requirements": [{
                "card_uid": crustle,
                "ready_target_count": 1,
                "energy_required": 3,
                "energy_requirements": [{"energy_uid": grass, "count": 3}],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "dwebble-backup-line",
            "stage": "deploy",
            "priority": 700,
            "requirements": [{
                "card_uid": dwebble,
                "ready_target_count": 1,
                "energy_required": 1,
                "energy_requirements": [{"energy_uid": grass, "count": 1}],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "articuno-bridge",
            "stage": "recover",
            "priority": 300,
            "requirements": [{
                "card_uid": articuno,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": None,
                "ability_index": 0,
            }],
        },
    ]
    count_rules = [
        {
            "rule_id": "bug-catching-set.exact-two",
            "priority": 0,
            "goal_id": "ogerpon-engine",
            "mode": "fixed",
            "fixed_count": 2,
            "fact": None,
            "divisor": None,
            "when": [c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", bug_set)],
        },
        {
            "rule_id": "teal-dance.exact-one",
            "priority": 1,
            "goal_id": "ogerpon-engine",
            "mode": "fixed",
            "fixed_count": 1,
            "fact": None,
            "divisor": None,
            "when": [c("prompt_kind", "eq", "assignment_source"), c("window.source_uid", "eq", ogerpon)],
        },
        {
            "rule_id": "energy-switch.exact-one",
            "priority": 2,
            "goal_id": "crustle-wall-route",
            "mode": "fixed",
            "fixed_count": 1,
            "fact": None,
            "divisor": None,
            "when": [c("window.source_uid", "eq", energy_switch)],
        },
        {
            "rule_id": "hyper-potion.exact-one",
            "priority": 3,
            "goal_id": "ogerpon-prize-route",
            "mode": "fixed",
            "fixed_count": 1,
            "fact": None,
            "divisor": None,
            "when": [c("window.source_uid", "eq", hyper_potion)],
        },
        {
            "rule_id": "single-search",
            "priority": 20,
            "goal_id": "ogerpon-engine",
            "mode": "fixed",
            "fixed_count": 1,
            "fact": None,
            "divisor": None,
            "when": [c("prompt_kind", "eq", "search")],
        },
        {
            "rule_id": "single-effect-target",
            "priority": 21,
            "goal_id": "ogerpon-prize-route",
            "mode": "fixed",
            "fixed_count": 1,
            "fact": None,
            "divisor": None,
            "when": [c("prompt_kind", "eq", "effect_target")],
        },
    ]
    rules: list[dict[str, object]] = []

    # Setup and board exposure discipline.
    rules.extend([
        _v2_rule("setup.active-dwebble", "dwebble-backup-line", "deploy", "macro", 18000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", dwebble)),
        _v2_rule("setup.active-ogerpon", "ogerpon-engine", "deploy", "macro", 15000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", ogerpon)),
        _v2_rule("setup.active-articuno", "articuno-bridge", "recover", "future", 4000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", articuno)),
        _v2_rule("setup.bench-first-ogerpon", "ogerpon-engine", "deploy", "macro", 18000,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", ogerpon),
                 c("self.board.count_uid", "lt", 2, ogerpon)),
        _v2_rule("setup.bench-dwebble", "dwebble-backup-line", "deploy", "future", 16500,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", dwebble),
                 c("self.board.count_uid", "eq", 0, dwebble)),
        _v2_rule("setup.defer-articuno", "articuno-bridge", "recover", "uncertainty", -9000,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", articuno),
                 c("self.board.count_uid", "eq", 0, dwebble)),
    ])

    # Zero-resource acquisition precedes any nonterminal attack or wait.
    for uid, name, score in (
        (tera_orb, "tera-orb", 21000),
        (bug_set, "bug-catching-set", 20500),
        (aroma, "capturing-aroma", 19500),
        (energy_search, "energy-search", 15000),
        (pokegear, "pokegear", 12000),
    ):
        rules.append(_v2_rule(
            f"main.acquire.{name}", "ogerpon-engine", "acquire", "macro", score,
            c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
            c("option.card_uid", "eq", uid), c("self.deck_count", "gt", 2),
        ))
    rules.extend([
        _v2_rule("main.bench-first-ogerpon", "ogerpon-engine", "deploy", "macro", 22000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", ogerpon), c("self.board.count_uid", "lt", 2, ogerpon)),
        _v2_rule("main.bench-first-dwebble", "dwebble-backup-line", "deploy", "macro", 21500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", dwebble), c("self.board.count_uid", "eq", 0, dwebble)),
        _v2_rule("main.bench-second-dwebble", "crustle-wall-route", "maintain", "future", 9500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", dwebble), c("self.board.count_uid", "eq", 1, dwebble),
                 c("self.bench_space", "gte", 2)),
        _v2_rule("main.bench-articuno-only-with-core", "articuno-bridge", "recover", "future", 3500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", articuno), c("self.board.count_uid", "gte", 2, ogerpon),
                 c("self.board.count_uid", "gte", 1, dwebble), c("self.bench_space", "gte", 2)),
    ])

    # Information checkpoint: Teal Dance is intentionally ahead of ordinary attacks.
    rules.extend([
        _v2_rule("ogerpon.teal-dance", "ogerpon-engine", "fund", "future", 32000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
                 c("option.source_uid", "eq", ogerpon), c("option.ability_index", "eq", 0),
                 c("self.deck_count", "gt", teal_dance_deck_reserve)),
        _v2_rule("teal-dance.select-grass", "ogerpon-engine", "fund", "interaction", 26000,
                 c("prompt_kind", "eq", "assignment_source"), c("window.source_uid", "eq", ogerpon),
                 c("option.card_uid", "eq", grass)),
        _v2_rule("teal-dance.bind-largest-public-debt", "ogerpon-engine", "fund", "interaction", 12000,
                 c("prompt_kind", "eq", "assignment_target"), c("window.source_uid", "eq", ogerpon),
                 c("option.target_uid", "eq", ogerpon),
                 score_terms=[{"fact": "option.target_energy_debt", "coefficient": 1200, "minimum": 0, "maximum": 3}]),
    ])

    # Exact three-Energy ledgers and the evolve-before-funding gust-trap guard.
    rules.extend([
        _v2_rule("attach.active-dwebble-ascension", "dwebble-backup-line", "fund", "macro", 23000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", grass), c("option.target_uid", "eq", dwebble),
                 c("option.target_is_active", "eq", True), c("option.target_attack_ready", "eq", False)),
        _v2_rule("attach.crustle-exact-debt", "crustle-wall-route", "fund", "macro", 20000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", grass), c("option.target_uid", "eq", crustle),
                 c("option.target_energy_debt", "gt", 0),
                 score_terms=[{"fact": "option.target_energy_debt", "coefficient": 900, "minimum": 0, "maximum": 3}]),
        _v2_rule("attach.ogerpon-exact-debt", "ogerpon-prize-route", "fund", "macro", 18500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", grass), c("option.target_uid", "eq", ogerpon),
                 c("option.target_energy_debt", "gt", 0),
                 score_terms=[{"fact": "option.target_energy_debt", "coefficient": 700, "minimum": 0, "maximum": 3}]),
        _v2_rule("attach.no-overfund-ready", "ogerpon-engine", "maintain", "uncertainty", -24000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.target_attack_ready", "eq", True)),
        _v2_rule("crustle.evolve-funded", "crustle-wall-route", "deploy", "future", 22000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", crustle), c("option.target_uid", "eq", dwebble),
                 c("option.target_attached_energy_count", "gte", 2)),
        _v2_rule("crustle.block-underfunded-bench-evolution", "crustle-wall-route", "maintain", "uncertainty", -26000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", crustle), c("option.target_uid", "eq", dwebble),
                 c("option.target_is_active", "eq", False), c("option.target_attached_energy_count", "lt", 2)),
    ])

    # Search and branch-local bindings; every result invalidates the old option indexes.
    rules.extend([
        _v2_rule("search.tera-orb-ogerpon", "ogerpon-engine", "acquire", "interaction", 30000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", tera_orb),
                 c("option.card_uid", "eq", ogerpon)),
        _v2_rule("search.bug-set-first-ogerpon", "ogerpon-engine", "acquire", "interaction", 26000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", bug_set),
                 c("option.card_uid", "eq", ogerpon), c("self.board.count_uid", "lt", 2, ogerpon)),
        _v2_rule("search.bug-set-dwebble", "dwebble-backup-line", "acquire", "interaction", 25000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", bug_set),
                 c("option.card_uid", "eq", dwebble), c("self.board.count_uid", "eq", 0, dwebble)),
        _v2_rule("search.bug-set-crustle", "crustle-wall-route", "acquire", "interaction", 23500,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", bug_set),
                 c("option.card_uid", "eq", crustle), c("self.board.count_uid", "gte", 1, dwebble)),
        _v2_rule("search.bug-set-grass", "ogerpon-engine", "fund", "interaction", 16000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", bug_set),
                 c("option.card_uid", "eq", grass)),
        _v2_rule("search.energy-search-grass", "ogerpon-engine", "fund", "interaction", 26000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", energy_search),
                 c("option.card_uid", "eq", grass)),
        _v2_rule("search.aroma-evolution-branch", "crustle-wall-route", "acquire", "interaction", 28000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", aroma),
                 c("option.card_uid", "eq", crustle)),
        _v2_rule("search.aroma-basic-dwebble", "dwebble-backup-line", "acquire", "interaction", 27000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", aroma),
                 c("option.card_uid", "eq", dwebble), c("self.board.count_uid", "eq", 0, dwebble)),
        _v2_rule("search.aroma-basic-ogerpon", "ogerpon-engine", "acquire", "interaction", 24000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", aroma),
                 c("option.card_uid", "eq", ogerpon)),
        _v2_rule("search.pokegear-boss-terminal-clock", "ogerpon-prize-route", "execute", "interaction", 18000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pokegear),
                 c("option.card_uid", "eq", boss), c("self.prizes_remaining", "lte", 2)),
        _v2_rule("search.pokegear-iono", "ogerpon-engine", "recover", "interaction", 12000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pokegear),
                 c("option.card_uid", "eq", iono)),
        _v2_rule("search.pokegear-judge", "ogerpon-engine", "recover", "interaction", 10500,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pokegear),
                 c("option.card_uid", "eq", judge)),
    ])

    # Healing is a heal/discard/refill transaction, never a blind Item score.
    rules.extend([
        _v2_rule("main.hyper-potion-damaged-active", "ogerpon-prize-route", "recover", "macro", 17000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", hyper_potion), c("self.active.remaining_hp", "lte", 120),
                 c("self.active.remaining_hp", "gt", 0), c("self.board.energy_count_uid", "gte", 1, grass)),
        _v2_rule("hyper-potion.target-ogerpon", "ogerpon-prize-route", "recover", "interaction", 21000,
                 c("window.source_uid", "eq", hyper_potion), c("option.target_uid", "eq", ogerpon),
                 c("option.target_remaining_hp", "lte", 150), c("option.target_attached_energy_count", "gte", 1)),
        _v2_rule("hyper-potion.target-crustle", "crustle-wall-route", "recover", "interaction", 20000,
                 c("window.source_uid", "eq", hyper_potion), c("option.target_uid", "eq", crustle),
                 c("option.target_remaining_hp", "lte", 90), c("option.target_attached_energy_count", "gte", 1)),
        _v2_rule("hyper-potion.discard-from-overfunded", "ogerpon-prize-route", "recover", "interaction", 19000,
                 c("window.source_uid", "eq", hyper_potion), c("option.card_uid", "eq", grass),
                 c("option.target_attached_energy_count", "gt", 3)),
        _v2_rule("main.energy-switch-for-crustle-debt", "crustle-wall-route", "fund", "macro", 14500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", energy_switch),
                 c("goal.energy_debt_uid", "gt", 0, crustle),
                 c("self.board.count_uid", "gte", 1, ogerpon),
                 c("self.board.energy_count_uid", "gte", 5, grass)),
        _v2_rule("main.block-energy-switch-before-ready-donor", "crustle-wall-route", "maintain", "uncertainty", -15500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", energy_switch),
                 c("goal.energy_debt_uid", "gt", 0, crustle),
                 c("self.board.energy_count_uid", "lt", 5, grass)),
        _v2_rule("energy-switch.source-overfunded-ogerpon", "crustle-wall-route", "fund", "interaction", 26000,
                 c("prompt_kind", "eq", "assignment_source"),
                 c("window.source_uid", "eq", energy_switch), c("option.card_uid", "eq", grass),
                 c("option.target_uid", "eq", ogerpon), c("option.target_attack_ready", "eq", True),
                 c("option.target_attached_energy_count", "gt", 3)),
        _v2_rule("energy-switch.protect-underfunded-crustle-source", "crustle-wall-route", "maintain", "uncertainty", -30000,
                 c("prompt_kind", "eq", "assignment_source"),
                 c("window.source_uid", "eq", energy_switch), c("option.target_uid", "eq", crustle),
                 c("option.target_energy_debt", "gt", 0)),
        _v2_rule("energy-switch.target-crustle", "crustle-wall-route", "fund", "interaction", 22000,
                 c("prompt_kind", "eq", "assignment_target"),
                 c("window.source_uid", "eq", energy_switch), c("option.target_uid", "eq", crustle),
                 c("option.target_energy_debt", "gt", 0)),
    ])

    # Item-spend order, hand disruption, stadiums and prize conversion.
    rules.extend([
        _v2_rule("main.crushing-hammer-tempo", "crustle-wall-route", "maintain", "future", 7000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", hammer), c("opponent.active.prize_value", "gte", 1)),
        _v2_rule("main.hero-cape-crustle-line", "crustle-wall-route", "maintain", "future", 8500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", cape),
                 c("self.board.count_uid", "gte", 1, crustle)),
        _v2_rule("tool.hero-cape-crustle", "crustle-wall-route", "maintain", "interaction", 18000,
                 c("option.target_uid", "eq", crustle), c("window.source_uid", "eq", cape)),
        _v2_rule("tool.hero-cape-ogerpon", "ogerpon-prize-route", "maintain", "interaction", 15000,
                 c("option.target_uid", "eq", ogerpon), c("window.source_uid", "eq", cape)),
        _v2_rule("main.boss-prize-window", "ogerpon-prize-route", "execute", "tactical", 12500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", boss),
                 c("self.prizes_remaining", "lte", 2), c("opponent.bench_count", "gte", 1),
                 c("goal.ready_count", "gte", 1)),
        _v2_rule("main.iono-self-brick-reset", "ogerpon-engine", "recover", "macro", 24000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", iono),
                 c("goal.ready_count", "eq", 0), c("goal.energy_debt", "gt", 0),
                 c("turn.supporter_available", "eq", True), c("self.deck_count", "gt", 6)),
        _v2_rule("main.iono-late-prize-lock", "ogerpon-engine", "recover", "macro", 23000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", iono),
                 c("self.prizes_remaining", "gte", 3), c("opponent.prizes_remaining", "lte", 3),
                 c("turn.supporter_available", "eq", True), c("self.deck_count", "gt", 6)),
        _v2_rule("main.judge-early-prize-disruption", "ogerpon-engine", "recover", "macro", 14500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", judge),
                 c("turn_number", "lte", 6), c("opponent.prizes_remaining", "gte", 4),
                 c("threat.tempo_margin", "lte", -1),
                 c("turn.supporter_available", "eq", True), c("self.deck_count", "gt", 6),
                 c("window.option_count_card_uid", "eq", 0, tera_orb),
                 c("window.option_count_card_uid", "eq", 0, bug_set),
                 c("window.option_count_card_uid", "eq", 0, pokegear)),
        _v2_rule("main.avoid-judge-late-game", "ogerpon-engine", "recover", "uncertainty", -24000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", judge),
                 c("opponent.prizes_remaining", "lte", 3)),
        _v2_rule("main.avoid-iono-low-deck", "ogerpon-engine", "recover", "uncertainty", -30000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", iono),
                 c("self.deck_count", "lte", 6)),
        _v2_rule("main.lively-stadium-hp-clock", "ogerpon-engine", "maintain", "future", 4500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", lively),
                 c("self.board.count_uid", "gte", 2, ogerpon)),
        _v2_rule("main.watchtower-no-unproved-target", "crustle-wall-route", "maintain", "uncertainty", -15000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", watchtower)),
    ])

    # Attack and handoff. Articuno has no attack route in this all-Grass list.
    rules.extend([
        _v2_rule("dwebble.ascension", "dwebble-backup-line", "execute", "tactical", 17000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", dwebble), c("option.attack_index", "eq", 0)),
        _v2_rule("crustle.attack", "crustle-wall-route", "execute", "tactical", 20000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", crustle), c("option.attack_index", "eq", 0),
                 c("option.projected_damage", "gt", 0)),
        _v2_rule("ogerpon.attack", "ogerpon-prize-route", "execute", "tactical", 19000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", ogerpon), c("option.attack_index", "eq", 0),
                 c("option.projected_damage", "gt", 0)),
        _v2_rule("attack.final-prize-ko", "ogerpon-prize-route", "execute", "tactical", 60000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.projected_knockout", "eq", True), c("self.prizes_remaining", "lte", 2)),
        _v2_rule("handoff.ready-crustle-vs-two-prize", "crustle-wall-route", "ready", "tactical", 26000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", crustle),
                 c("option.target_attack_ready", "eq", True), c("opponent.active.prize_value", "gte", 2)),
        _v2_rule("handoff.ready-ogerpon", "ogerpon-prize-route", "ready", "tactical", 24000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", ogerpon),
                 c("option.target_attack_ready", "eq", True)),
        _v2_rule("handoff.near-ready-crustle", "crustle-wall-route", "ready", "future", 17000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", crustle),
                 c("option.target_energy_debt", "eq", 1)),
        _v2_rule("handoff.articuno-certified-bridge", "articuno-bridge", "recover", "future", 13000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", articuno),
                 c("option.target_prize_value", "eq", 1), c("opponent.prizes_remaining", "eq", 2),
                 c("goal.ready_count", "eq", 1), c("window.option_count_target_uid", "eq", 0, crustle),
                 c("window.option_count_target_uid", "eq", 0, ogerpon)),
        _v2_rule("handoff.avoid-unready-two-prize", "ogerpon-engine", "recover", "uncertainty", -22000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_prize_value", "gte", 2),
                 c("option.target_attack_ready", "eq", False), c("opponent.prizes_remaining", "eq", 2)),
        _v2_rule("articuno.no-grass-attack-route", "articuno-bridge", "recover", "uncertainty", -30000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", articuno)),
    ])

    turn_routes = [{
        "route_id": "ogerpon-crustle-continuity-turn",
        "priority": 1000,
        "goal_id": "ogerpon-prize-route",
        "owner_goal_id": "ogerpon-prize-route",
        "bridge_goal_id": "articuno-bridge",
        "pivot_goal_id": "crustle-wall-route",
        "when": [c("self.board.count_uid", "gte", 1, ogerpon)],
        "steps": [
            {
                "step_id": "take-final-prize-ko",
                "prompt_kinds": ["main"],
                "goal_id": "ogerpon-prize-route",
                "when": [c("self.prizes_remaining", "lte", 2)],
                "option_when": [c("option.kind", "eq", "attack"), c("option.projected_knockout", "eq", True)],
                "score_bonus": 240000,
                "selection_count": 1,
                "terminal": True,
                "checkpoint": False,
            },
            {
                "step_id": "teal-dance-before-attack",
                "prompt_kinds": ["main"],
                "goal_id": "ogerpon-engine",
                "when": [c("self.deck_count", "gt", teal_dance_deck_reserve)],
                "option_when": [c("option.kind", "eq", "use_ability"), c("option.source_uid", "eq", ogerpon), c("option.ability_index", "eq", 0)],
                "score_bonus": 180000,
                "selection_count": 1,
                "terminal": False,
                "checkpoint": True,
            },
            {
                "step_id": "fund-current-route",
                "prompt_kinds": ["main"],
                "goal_id": "ogerpon-prize-route",
                "when": [c("goal.energy_debt", "gt", 0), c("turn.manual_attachment_available", "eq", True)],
                "option_when": [c("goal.option.funds_target", "eq", True)],
                "score_bonus": 150000,
                "selection_count": 1,
                "terminal": False,
                "checkpoint": False,
            },
            {
                "step_id": "send-ready-crustle-pivot",
                "prompt_kinds": ["send_out"],
                "goal_id": "crustle-wall-route",
                "when": [c("goal.complete", "eq", True)],
                "option_when": [c("goal.option.pivots_ready_target", "eq", True)],
                "score_bonus": 165000,
                "selection_count": 1,
                "terminal": False,
                "checkpoint": False,
            },
            {
                "step_id": "execute-declared-ogerpon-attack",
                "prompt_kinds": ["main"],
                "goal_id": "ogerpon-prize-route",
                "when": [c("goal.complete", "eq", True)],
                "option_when": [c("goal.option.executes_requirement", "eq", True), c("option.projected_damage", "gt", 0)],
                "score_bonus": 140000,
                "selection_count": 1,
                "terminal": True,
                "checkpoint": False,
            },
        ],
    }]
    return {
        "schema_version": 2,
        "adapter_id": package_id,
        "adapter_version": adapter_version,
        "goals": goals,
        "count_rules": count_rules,
        "rules": rules,
        "turn_routes": turn_routes,
        "route_candidates": [],
        "interaction_recipes": [],
        "turn_bonus_contracts": [],
    }


def _marnie_gift_box_competitive_adapter(
    package_id: str, adapter_version: int = 15
) -> dict[str, object]:
    """Compile the public, current-window portion of the locked 646600 plan."""

    impidimp = "CSV10C_146"
    morgrem = "CSV10C_147"
    grimmsnarl = "CSV10C_148"
    munkidori = "CSV8C_094"
    snorunt = "CSV9.5C_043"
    froslass = "CSV7C_059"
    budew = "CSV9.5C_004"
    shaymin = "CSV10C_007"
    dark = "CSVE1C_DAR"
    arven = "CSV1C_123"
    iono = "CSV3C_123"
    research = "CSV1C_121"
    boss = "CSVH1aC_023"
    counter_catcher = "CSV6C_114"
    energy_switch = "CSVH1aC_008"
    night_stretcher = "CSV8C_183"
    tm_evolution = "CSV5C_119"
    ultra_ball = "CSV1C_112"
    artazon = "CSV2C_127"
    rare_candy = "CSVH1C_045"
    spikemuth = "CSV10C_216"
    tm_devolution = "CSV5C_120"
    defiance_band = "CSV1C_117"
    rescue_board = "CSV7C_185"
    energy_search = "CSVH1C_035"
    secret_box = "CSV8C_176"
    poffin = "CSV7C_177"

    def c(fact: str, op: str, value: object, card_uid: str | None = None) -> dict[str, object]:
        return _v2_condition(fact, op, value, card_uid=card_uid)

    goals = [
        {
            "goal_id": "grimmsnarl-prize-route", "stage": "execute", "priority": 1000,
            "requirements": [{
                "card_uid": grimmsnarl, "ready_target_count": 1, "energy_required": 2,
                "energy_requirements": [{"energy_uid": dark, "count": 2}],
                "attack_index": 0, "ability_index": None,
            }],
        },
        {
            "goal_id": "backup-grimmsnarl", "stage": "ready", "priority": 950,
            "requirements": [{
                "card_uid": grimmsnarl, "ready_target_count": 2, "energy_required": 2,
                "energy_requirements": [{"energy_uid": dark, "count": 2}],
                "attack_index": 0, "ability_index": None,
            }],
        },
        {
            "goal_id": "munkidori-transfer", "stage": "execute", "priority": 900,
            "requirements": [{
                "card_uid": munkidori, "ready_target_count": 1, "energy_required": 1,
                "energy_requirements": [{"energy_uid": dark, "count": 1}],
                "attack_index": None, "ability_index": 0,
            }],
        },
        {
            "goal_id": "double-froslass-engine", "stage": "maintain", "priority": 850,
            "requirements": [{
                "card_uid": froslass, "ready_target_count": 2, "energy_required": 0,
                "energy_requirements": [], "attack_index": None, "ability_index": None,
            }],
        },
        {
            "goal_id": "budew-tempo", "stage": "execute", "priority": 400,
            "requirements": [{
                "card_uid": budew, "ready_target_count": 1, "energy_required": 0,
                "energy_requirements": [], "attack_index": 0, "ability_index": None,
            }],
        },
        {
            "goal_id": "single-prize-bridge", "stage": "recover", "priority": 300,
            "requirements": [{
                "card_uid": munkidori, "ready_target_count": 1, "energy_required": 1,
                "energy_requirements": [{"energy_uid": dark, "count": 1}],
                "attack_index": None, "ability_index": 0,
            }],
        },
        {
            "goal_id": "devolution-finish", "stage": "execute", "priority": 800,
            "requirements": [{
                "card_uid": grimmsnarl, "ready_target_count": 1, "energy_required": 2,
                "energy_requirements": [{"energy_uid": dark, "count": 2}],
                "attack_index": 0, "ability_index": None,
            }],
        },
    ]
    count_rules = [
        {
            "rule_id": "punk-up.exact-public-debt", "priority": 0,
            "goal_id": "backup-grimmsnarl", "mode": "goal_energy_debt",
            "fixed_count": None, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "assignment_source"),
                     c("window.source_uid", "eq", grimmsnarl)],
        },
        {
            "rule_id": "poffin.exact-two", "priority": 10,
            "goal_id": "backup-grimmsnarl", "mode": "fixed",
            "fixed_count": 2, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin)],
        },
        {
            "rule_id": "single-search", "priority": 20,
            "goal_id": "grimmsnarl-prize-route", "mode": "fixed",
            "fixed_count": 1, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search")],
        },
        {
            "rule_id": "single-assignment", "priority": 21,
            "goal_id": "backup-grimmsnarl", "mode": "fixed",
            "fixed_count": 1, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "assignment_source")],
        },
        {
            "rule_id": "single-target", "priority": 22,
            "goal_id": "grimmsnarl-prize-route", "mode": "fixed",
            "fixed_count": 1, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "assignment_target")],
        },
    ]
    rules: list[dict[str, object]] = [
        # Opening flip: Budew only while it can still buy an actual setup window.
        _v2_rule("opening.budew-lock", "budew-tempo", "deploy", "tactical", 22000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", budew),
                 c("opponent.bench_count", "eq", 0)),
        _v2_rule("opening.impidimp-engine", "backup-grimmsnarl", "deploy", "future", 21000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", impidimp),
                 c("opponent.bench_count", "gt", 0)),
        _v2_rule("opening.impidimp-safe-default", "backup-grimmsnarl", "deploy", "future", 18000,
                 c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", impidimp)),
        _v2_rule("opening.bench-impidimp", "backup-grimmsnarl", "deploy", "macro", 19000,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", impidimp),
                 c("self.board.count_uid", "lt", 2, impidimp)),
        _v2_rule("opening.bench-snorunt", "double-froslass-engine", "deploy", "future", 17500,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", snorunt),
                 c("self.board.count_uid", "lt", 2, snorunt)),
        _v2_rule("opening.protect-bench-space", "grimmsnarl-prize-route", "maintain", "uncertainty", -18000,
                 c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", shaymin),
                 c("self.bench_open", "eq", False)),

        # Engine deployment and acquisition.
        _v2_rule("main.poffin", "backup-grimmsnarl", "acquire", "macro", 24500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", poffin), c("self.deck_count", "gt", 5)),
        _v2_rule("search.poffin-impidimp-first", "backup-grimmsnarl", "acquire", "interaction", 33000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin),
                 c("option.card_uid", "eq", impidimp), c("self.board.count_uid", "eq", 0, impidimp)),
        _v2_rule("search.poffin-snorunt-engine", "double-froslass-engine", "acquire", "interaction", 28000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin),
                 c("option.card_uid", "eq", snorunt)),
        _v2_rule("search.poffin-snorunt-after-line", "double-froslass-engine", "acquire", "interaction", 33500,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin),
                 c("option.card_uid", "eq", snorunt), c("self.board.count_uid", "gte", 1, impidimp)),
        _v2_rule("search.spikemuth-grimmsnarl-from-morgrem", "backup-grimmsnarl", "acquire", "interaction", 35000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", spikemuth),
                 c("option.card_uid", "eq", grimmsnarl), c("self.board.count_uid", "gte", 1, morgrem)),
        _v2_rule("search.spikemuth-grimmsnarl-with-rare-candy", "backup-grimmsnarl", "acquire", "interaction", 37000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", spikemuth),
                 c("option.card_uid", "eq", grimmsnarl), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.hand.count_uid", "gt", 0, rare_candy)),
        _v2_rule("search.spikemuth-morgrem-from-impidimp", "backup-grimmsnarl", "acquire", "interaction", 34000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", spikemuth),
                 c("option.card_uid", "eq", morgrem), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.board.count_uid", "eq", 0, morgrem)),
        _v2_rule("search.ultra-ball-grimmsnarl-from-morgrem", "backup-grimmsnarl", "acquire", "interaction", 35000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", ultra_ball),
                 c("option.card_uid", "eq", grimmsnarl), c("self.board.count_uid", "gte", 1, morgrem)),
        _v2_rule("search.ultra-ball-grimmsnarl-with-rare-candy", "backup-grimmsnarl", "acquire", "interaction", 37000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", ultra_ball),
                 c("option.card_uid", "eq", grimmsnarl), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.hand.count_uid", "gt", 0, rare_candy)),
        _v2_rule("search.ultra-ball-morgrem-from-impidimp", "backup-grimmsnarl", "acquire", "interaction", 34000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", ultra_ball),
                 c("option.card_uid", "eq", morgrem), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.board.count_uid", "eq", 0, morgrem)),
        # Arven is the deck's four-copy development supporter.  Its item and
        # tool searches arrive as separate fresh UCIS windows, so each leg is
        # rebound from the current public board instead of precommitting a pair.
        _v2_rule("main.arven-development", "backup-grimmsnarl", "acquire", "macro", 22500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
                 c("option.card_uid", "eq", arven), c("self.deck_count", "gt", 8),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("search.arven-poffin-core", "backup-grimmsnarl", "acquire", "interaction", 39000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", poffin), c("self.bench_open", "eq", True),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("search.arven-rare-candy-grimmsnarl", "backup-grimmsnarl", "acquire", "interaction", 38500,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", rare_candy), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.hand.count_uid", "gt", 0, grimmsnarl)),
        _v2_rule("search.arven-ultra-ball-core", "backup-grimmsnarl", "acquire", "interaction", 27000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", ultra_ball), c("goal.deployed_count", "lt", 2)),
        _v2_rule("search.arven-energy-search-munkidori", "munkidori-transfer", "fund", "interaction", 30000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", energy_search), c("self.board.count_uid", "gte", 1, munkidori),
                 c("self.board.energy_count_uid", "eq", 0, dark), c("goal.energy_debt", "gt", 0)),
        _v2_rule("search.arven-tm-evolution-core", "backup-grimmsnarl", "acquire", "interaction", 39000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", tm_evolution), c("self.bench.count_uid", "gt", 0, impidimp),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("search.arven-tm-evolution-snorunt", "double-froslass-engine", "acquire", "interaction", 38000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", tm_evolution), c("self.bench.count_uid", "gt", 0, snorunt),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("search.arven-rescue-board-budew", "budew-tempo", "maintain", "interaction", 36000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", rescue_board), c("self.active.count_uid", "gt", 0, budew)),
        _v2_rule("search.arven-tm-devolution-finish", "devolution-finish", "execute", "interaction", 37000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                 c("option.card_uid", "eq", tm_devolution), c("damage.best_remaining_debt", "lte", 30),
                 c("opponent.bench_count", "gte", 1)),

        # Artazon places a non-Rule-Box Basic directly onto the Bench.  Build
        # the four-role core in order: first Impidimp, first Snorunt, one
        # powered Munkidori, then redundancy if space remains.
        _v2_rule("main.artazon-development", "backup-grimmsnarl", "acquire", "future", 23500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_stadium"),
                 c("option.card_uid", "eq", artazon), c("self.deck_count", "gt", 8),
                 c("self.bench_open", "eq", True), c("goal.deployed_count", "lt", 2)),
        _v2_rule("main.artazon-use", "backup-grimmsnarl", "deploy", "macro", 27000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_stadium_effect"),
                 c("option.source_uid", "eq", artazon), c("self.deck_count", "gt", 5),
                 c("self.bench_open", "eq", True), c("goal.deployed_count", "lt", 2)),
        _v2_rule("main.defer-artazon-bench-full", "backup-grimmsnarl", "maintain", "uncertainty", -32000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", artazon),
                 c("self.bench_open", "eq", False)),
        _v2_rule("search.artazon-impidimp-first", "backup-grimmsnarl", "deploy", "interaction", 40000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", artazon),
                 c("option.card_uid", "eq", impidimp), c("self.board.count_uid", "eq", 0, impidimp)),
        _v2_rule("search.artazon-snorunt-engine", "double-froslass-engine", "deploy", "interaction", 39000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", artazon),
                 c("option.card_uid", "eq", snorunt), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.board.count_uid", "eq", 0, snorunt)),
        _v2_rule("search.artazon-munkidori-engine", "munkidori-transfer", "deploy", "interaction", 38000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", artazon),
                 c("option.card_uid", "eq", munkidori), c("self.board.count_uid", "gte", 1, impidimp),
                 c("self.board.count_uid", "gte", 1, snorunt), c("self.board.count_uid", "eq", 0, munkidori)),
        _v2_rule("search.artazon-snorunt-second", "double-froslass-engine", "deploy", "interaction", 36000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", artazon),
                 c("option.card_uid", "eq", snorunt), c("self.board.count_uid", "eq", 1, snorunt)),
        _v2_rule("search.artazon-impidimp-backup", "backup-grimmsnarl", "deploy", "interaction", 35000,
                 c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", artazon),
                 c("option.card_uid", "eq", impidimp), c("self.board.count_uid", "eq", 1, impidimp),
                 c("self.board.count_uid", "gte", 1, snorunt)),
        _v2_rule("main.ultra-ball", "backup-grimmsnarl", "acquire", "macro", 20500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", ultra_ball),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("main.energy-search", "munkidori-transfer", "fund", "macro", 17000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", energy_search),
                 c("goal.energy_debt", "gt", 0)),
        _v2_rule("main.secret-box", "backup-grimmsnarl", "acquire", "macro", 13500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", secret_box),
                 c("self.hand_count", "gte", 4), c("self.deck_count", "gt", 8)),
        _v2_rule("main.bench-impidimp", "backup-grimmsnarl", "deploy", "macro", 23000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", impidimp), c("self.board.count_uid", "lt", 2, impidimp)),
        _v2_rule("main.bench-snorunt", "double-froslass-engine", "deploy", "future", 20500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", snorunt), c("self.board.count_uid", "lt", 2, snorunt),
                 c("self.bench_open", "eq", True)),
        _v2_rule("main.bench-munkidori", "munkidori-transfer", "deploy", "future", 20000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
                 c("option.card_uid", "eq", munkidori), c("self.board.count_uid", "eq", 0, munkidori)),
        _v2_rule("main.evolve-morgrem", "backup-grimmsnarl", "deploy", "macro", 25000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", morgrem), c("option.target_uid", "eq", impidimp)),
        _v2_rule("main.evolve-grimmsnarl", "backup-grimmsnarl", "deploy", "macro", 29000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", grimmsnarl)),
        _v2_rule("main.rare-candy-grimmsnarl", "backup-grimmsnarl", "deploy", "macro", 24000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", rare_candy),
                 c("self.board.count_uid", "gte", 1, impidimp)),
        _v2_rule("main.evolve-froslass-first", "double-froslass-engine", "deploy", "future", 23500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", froslass), c("self.board.count_uid", "lt", 1, froslass)),
        _v2_rule("main.evolve-froslass-second-vs-wide-board", "double-froslass-engine", "deploy", "future", 21000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
                 c("option.card_uid", "eq", froslass), c("self.board.count_uid", "eq", 1, froslass),
                 c("opponent.bench_count", "gte", 2), c("self.bench_open", "eq", True)),

        # Exact public energy debt and typed re-binding.
        _v2_rule("grimmsnarl.punk-up", "backup-grimmsnarl", "fund", "future", 32000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
                 c("option.source_uid", "eq", grimmsnarl), c("option.ability_index", "eq", 0),
                 c("goal.energy_debt", "gt", 0)),
        _v2_rule("punk-up.select-dark", "backup-grimmsnarl", "fund", "interaction", 30000,
                 c("prompt_kind", "eq", "assignment_source"),
                 c("window.source_uid", "eq", grimmsnarl),
                 c("option.card_uid", "eq", dark)),
        _v2_rule("punk-up.target-active-debt", "grimmsnarl-prize-route", "fund", "interaction", 33000,
                 c("prompt_kind", "eq", "assignment_target"), c("window.source_uid", "eq", grimmsnarl),
                 c("option.target_uid", "eq", grimmsnarl), c("option.target_energy_debt", "gt", 0),
                 c("option.target_is_active", "eq", True)),
        _v2_rule("punk-up.target-current-debt", "grimmsnarl-prize-route", "fund", "interaction", 29000,
                 c("prompt_kind", "eq", "assignment_target"), c("window.source_uid", "eq", grimmsnarl),
                 c("option.target_uid", "eq", grimmsnarl), c("option.target_energy_debt", "gt", 0),
                 score_terms=[{"fact": "option.target_energy_debt", "coefficient": 1200, "minimum": 0, "maximum": 2}]),
        _v2_rule("attach.active-grimmsnarl-after-denial", "grimmsnarl-prize-route", "fund", "tactical", 40000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", grimmsnarl),
                 c("option.target_is_active", "eq", True), c("option.target_energy_debt", "gt", 0)),
        _v2_rule("attach.munkidori-first", "munkidori-transfer", "fund", "macro", 31500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", munkidori),
                 c("option.target_attached_energy_count", "eq", 0)),
        _v2_rule("attach.tm-evolution-active-snorunt", "double-froslass-engine", "fund", "macro", 30000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", snorunt),
                 c("option.target_is_active", "eq", True),
                 c("option.target_attached_energy_count", "eq", 0),
                 c("self.hand.count_uid", "gt", 0, tm_evolution)),
        _v2_rule("attach.tm-evolution-active-impidimp", "backup-grimmsnarl", "fund", "macro", 29500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", impidimp),
                 c("option.target_is_active", "eq", True),
                 c("option.target_attached_energy_count", "eq", 0),
                 c("self.hand.count_uid", "gt", 0, tm_evolution)),
        _v2_rule("attach.morgrem-line-debt", "backup-grimmsnarl", "fund", "future", 24500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", morgrem),
                 c("option.target_attached_energy_count", "lt", 2)),
        _v2_rule("attach.impidimp-line-debt", "backup-grimmsnarl", "fund", "future", 24000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", impidimp),
                 c("option.target_attached_energy_count", "lt", 2)),
        _v2_rule("attach.grimmsnarl-debt", "backup-grimmsnarl", "fund", "future", 19000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.card_uid", "eq", dark), c("option.target_uid", "eq", grimmsnarl),
                 c("option.target_energy_debt", "gt", 0)),
        _v2_rule("attach.no-overfund-ready", "backup-grimmsnarl", "maintain", "uncertainty", -30000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                 c("option.target_attack_ready", "eq", True)),
        _v2_rule("main.energy-switch-backup", "backup-grimmsnarl", "fund", "future", 12000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", energy_switch),
                 c("goal.energy_debt", "gt", 0), c("self.board.energy_count_uid", "gte", 3, dark)),
        _v2_rule("energy-switch.protect-munkidori", "munkidori-transfer", "maintain", "uncertainty", -32000,
                 c("prompt_kind", "eq", "assignment_source"), c("window.source_uid", "eq", energy_switch),
                 c("option.target_uid", "eq", munkidori), c("option.target_attached_energy_count", "lte", 1)),

        # Damage counter engine, 180/210 routes and split target.
        _v2_rule("munkidori.adrena-brain", "munkidori-transfer", "execute", "tactical", 33000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
                 c("option.source_uid", "eq", munkidori), c("damage.best_transfer_count", "gt", 0)),
        _v2_rule("munkidori.source-protect-two-prize", "munkidori-transfer", "execute", "interaction", 33000,
                 c("prompt_kind", "eq", "effect_target"), c("window.source_uid", "eq", munkidori),
                 c("option.target_prize_value", "eq", 2),
                 score_terms=[{"fact": "option.target_remaining_hp", "coefficient": -20,
                               "minimum": 1, "maximum": 400}]),
        _v2_rule("munkidori.count-full-public-transfer", "munkidori-transfer", "execute", "interaction", 32000,
                 c("select.context", "eq", "remove_damage_counter_count"),
                 c("option.option_number", "gte", 1),
                 score_terms=[{"fact": "option.option_number", "coefficient": 1000,
                               "minimum": 1, "maximum": 3}]),
        _v2_rule("munkidori.target-concentrated-public-ko", "munkidori-transfer", "execute", "interaction", 46000,
                 c("select.context", "eq", "damage_counter"),
                 c("transaction.id", "eq", "munkidori-concentrated-ko"),
                 c("transaction.option.matches_target", "eq", True),
                 score_terms=[{"fact": "damage.option.remaining_debt", "coefficient": -30,
                               "minimum": 0, "maximum": 400},
                              {"fact": "damage.option.overkill", "coefficient": -20,
                               "minimum": 0, "maximum": 300}]),
        _v2_rule("munkidori.avoid-healed-bench-debt", "munkidori-transfer", "execute", "uncertainty", -50000,
                 c("select.context", "eq", "damage_counter"),
                 c("damage.option.response_risk", "gte", 100),
                 c("damage.option.remaining_debt", "gt", 0)),
        _v2_rule("damage.best-transfer-target", "munkidori-transfer", "execute", "interaction", 30000,
                 c("prompt_kind", "eq", "damage_target"),
                 score_terms=[{"fact": "damage.option.remaining_debt", "coefficient": -50, "minimum": 0, "maximum": 400},
                              {"fact": "damage.option.prize_yield", "coefficient": 5000, "minimum": 1, "maximum": 3},
                              {"fact": "damage.option.overkill", "coefficient": -20, "minimum": 0, "maximum": 300}]),
        _v2_rule("attack.shadow-bullet", "grimmsnarl-prize-route", "execute", "tactical", 31000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", grimmsnarl), c("option.attack_index", "eq", 0),
                 c("damage.option.projected_damage", "gt", 0),
                 c("damage.option.prize_yield", "gte", 1),
                 score_terms=[{"fact": "damage.option.attack_windows_to_ko", "coefficient": -5000, "minimum": 1, "maximum": 3},
                              {"fact": "damage.option.overkill", "coefficient": -15, "minimum": 0, "maximum": 300}]),
        _v2_rule("attack.reject-zero-active-damage", "grimmsnarl-prize-route", "execute", "uncertainty", -60000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", grimmsnarl),
                 c("damage.option.projected_damage", "eq", 0)),
        _v2_rule("attack.defiance-210-two-prize", "grimmsnarl-prize-route", "execute", "tactical", 52000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
                 c("option.source_uid", "eq", grimmsnarl), c("self.prizes_remaining", "gt", 3),
                 c("damage.option.projected_damage", "eq", 210), c("damage.option.prize_yield", "eq", 2),
                 c("damage.option.attack_windows_to_ko", "eq", 1)),
        _v2_rule("damage.shadow-bullet-bench-target", "grimmsnarl-prize-route", "execute", "interaction", 28000,
                 c("prompt_kind", "eq", "attack_target"), c("option.target_prize_value", "eq", 2),
                 score_terms=[{"fact": "damage.option.attack_windows_to_ko", "coefficient": -4000, "minimum": 1, "maximum": 3},
                              {"fact": "damage.option.remaining_debt", "coefficient": -30, "minimum": 0, "maximum": 400}]),
        _v2_rule("main.tm-devolution-public-finish", "devolution-finish", "execute", "tactical", 27000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", tm_devolution),
                 c("damage.best_remaining_debt", "lte", 30), c("opponent.bench_count", "gte", 1)),
        _v2_rule("main.defiance-band-grimmsnarl", "grimmsnarl-prize-route", "maintain", "future", 33500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_tool"),
                 c("option.card_uid", "eq", defiance_band), c("option.target_uid", "eq", grimmsnarl),
                 c("self.prizes_remaining", "gt", 3)),
        _v2_rule("main.reject-defiance-band-non-attacker", "grimmsnarl-prize-route", "maintain", "uncertainty", -40000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_tool"),
                 c("option.card_uid", "eq", defiance_band), c("option.target_uid", "ne", grimmsnarl)),

        # Prize-clock scheduling and low-resource protection.
        _v2_rule("main.counter-catcher-window", "grimmsnarl-prize-route", "execute", "tactical", 23500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", counter_catcher),
                 c("self.prizes_remaining", "gt", 3), c("goal.active_ready_count", "gte", 1),
                 c("opponent.bench_count", "gte", 1)),
        _v2_rule("main.counter-catcher-exact-two-prize", "grimmsnarl-prize-route", "execute", "tactical", 68000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", counter_catcher),
                 c("goal.active_ready_count", "gte", 1),
                 c("damage.best_gust_attack_windows_to_ko", "eq", 1),
                 c("damage.best_gust_prize_yield", "eq", 2)),
        _v2_rule("main.boss-only-with-attacker", "grimmsnarl-prize-route", "execute", "tactical", 21500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", boss),
                 c("goal.active_ready_count", "gte", 1), c("opponent.bench_count", "gte", 1)),
        _v2_rule("main.boss-exact-two-prize", "grimmsnarl-prize-route", "execute", "tactical", 65000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", boss),
                 c("goal.active_ready_count", "gte", 1),
                 c("damage.best_gust_attack_windows_to_ko", "eq", 1),
                 c("damage.best_gust_prize_yield", "eq", 2)),
        _v2_rule("main.defer-counter-catcher-without-active-attacker", "grimmsnarl-prize-route",
                 "maintain", "uncertainty", -40000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", counter_catcher),
                 c("goal.active_ready_count", "eq", 0)),
        _v2_rule("main.defer-boss-without-active-attacker", "grimmsnarl-prize-route",
                 "maintain", "uncertainty", -40000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", boss),
                 c("goal.active_ready_count", "eq", 0)),
        _v2_rule("gust.target-two-prize", "grimmsnarl-prize-route", "execute", "interaction", 34000,
                 c("prompt_kind", "eq", "effect_target"),
                 c("window.source_uid", "eq", boss),
                 c("option.target_prize_value", "eq", 2),
                 score_terms=[{"fact": "damage.option.attack_windows_to_ko", "coefficient": -4000,
                               "minimum": 1, "maximum": 3},
                              {"fact": "damage.option.remaining_debt", "coefficient": -20,
                               "minimum": 0, "maximum": 400}]),
        _v2_rule("gust.target-exact-two-prize", "grimmsnarl-prize-route", "execute", "interaction", 62000,
                 c("prompt_kind", "eq", "effect_target"),
                 c("transaction.id", "eq", "gust-exact-two-prize-ko"),
                 c("transaction.option.matches_target", "eq", True),
                 c("option.target_prize_value", "eq", 2)),
        _v2_rule("gust.avoid-single-prize-wall", "grimmsnarl-prize-route", "execute", "uncertainty", -28000,
                 c("prompt_kind", "eq", "effect_target"),
                 c("window.source_uid", "eq", boss),
                 c("option.target_prize_value", "eq", 1)),
        _v2_rule("gust.target-two-prize-counter-catcher", "grimmsnarl-prize-route", "execute", "interaction", 34000,
                 c("prompt_kind", "eq", "effect_target"),
                 c("window.source_uid", "eq", counter_catcher),
                 c("option.target_prize_value", "eq", 2),
                 score_terms=[{"fact": "damage.option.attack_windows_to_ko", "coefficient": -4000,
                               "minimum": 1, "maximum": 3},
                              {"fact": "damage.option.remaining_debt", "coefficient": -20,
                               "minimum": 0, "maximum": 400}]),
        _v2_rule("gust.avoid-single-prize-wall-counter-catcher", "grimmsnarl-prize-route", "execute", "uncertainty", -28000,
                 c("prompt_kind", "eq", "effect_target"),
                 c("window.source_uid", "eq", counter_catcher),
                 c("option.target_prize_value", "eq", 1)),
        _v2_rule("handoff.ready-grimmsnarl", "grimmsnarl-prize-route", "ready", "tactical", 36000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", grimmsnarl),
                 c("option.target_attack_ready", "eq", True)),
        _v2_rule("handoff.near-ready-grimmsnarl", "backup-grimmsnarl", "ready", "future", 22000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", grimmsnarl),
                 c("option.target_energy_debt", "eq", 1), c("opponent.prizes_remaining", "gt", 2)),
        _v2_rule("handoff.single-prize-bridge", "single-prize-bridge", "recover", "future", 28000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", munkidori),
                 c("option.target_prize_value", "eq", 1), c("opponent.prizes_remaining", "eq", 2)),
        _v2_rule("handoff.avoid-unready-two-prize-terminal", "single-prize-bridge", "recover", "uncertainty", -36000,
                 c("prompt_kind", "eq", "send_out"), c("option.target_prize_value", "eq", 2),
                 c("option.target_attack_ready", "eq", False), c("opponent.prizes_remaining", "eq", 2)),
        _v2_rule("main.night-stretcher-continuity", "backup-grimmsnarl", "recover", "future", 14500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", night_stretcher),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("main.tm-evolution", "backup-grimmsnarl", "deploy", "future", 18500,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_tool"),
                 c("option.card_uid", "eq", tm_evolution),
                 c("option.target_is_active", "eq", True),
                 c("option.target_attached_energy_count", "gte", 1),
                 c("goal.deployed_count", "lt", 2)),
        _v2_rule("attack.tm-evolution-develop", "backup-grimmsnarl", "deploy", "macro", 55000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "granted_attack"),
                 c("option.source_uid", "eq", tm_evolution), c("option.attack_index", "eq", 0),
                 c("self.bench.count_uid", "gt", 0, impidimp)),
        _v2_rule("attack.tm-evolution-develop-snorunt", "double-froslass-engine", "deploy", "macro", 55000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "granted_attack"),
                 c("option.source_uid", "eq", tm_evolution), c("option.attack_index", "eq", 0),
                 c("self.bench.count_uid", "gt", 0, snorunt)),
        _v2_rule("main.defer-tm-evolution-without-energy", "backup-grimmsnarl", "maintain", "uncertainty", -30000,
                 c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_tool"),
                 c("option.card_uid", "eq", tm_evolution),
                 c("option.target_attached_energy_count", "eq", 0)),
        _v2_rule("main.spikemuth-continuity", "backup-grimmsnarl", "maintain", "future", 6000,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", spikemuth),
                 c("goal.ready_count", "eq", 0)),
        _v2_rule("main.iono-development", "backup-grimmsnarl", "recover", "macro", 12500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", iono),
                 c("goal.ready_count", "eq", 0), c("self.deck_count", "gt", 8)),
        _v2_rule("main.research-development", "backup-grimmsnarl", "recover", "macro", 10500,
                 c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", research),
                 c("goal.ready_count", "eq", 0), c("self.deck_count", "gt", 10)),
        _v2_rule("main.stop-low-deck-filter", "backup-grimmsnarl", "maintain", "uncertainty", -40000,
                 c("prompt_kind", "eq", "main"), c("self.deck_count", "lte", 5),
                 c("option.card_uid", "eq", research)),
    ]

    damage_plans = [{
        "plan_id": "marnie-public-two-window-prize-map",
        "goal_id": "grimmsnarl-prize-route",
        "priority": 1000,
        "horizon_attack_windows": 2,
        "capability_ids": [
            "attack.fixed_split.v1",
            "attack.bench_heal.v1",
            "between_turn.ability_counter.v1",
            "ability.move_damage_counters.v1",
            "tool.conditional_active_damage_bonus.v1",
            "attack.mass_devolution.v1",
        ],
        "target_roles": ["opponent.active", "opponent.bench"],
        "objective_order": [
            "attack_windows", "prize_yield", "remaining_debt", "overkill", "response_risk",
        ],
    }]
    semantic_transactions = [
        {
            "transaction_id": "gust-exact-two-prize-ko", "goal_id": "grimmsnarl-prize-route",
            "priority": 40, "max_own_turns": 1, "target_role": "opponent.pokemon",
            "start_when": [c("transaction.candidate.is_gust_best", "eq", True),
                           c("damage.best_gust_attack_windows_to_ko", "eq", 1),
                           c("damage.best_gust_prize_yield", "eq", 2),
                           c("damage.current_attack_damage", "gt", 0)],
            "continue_when": [c("transaction.remaining_damage_debt", "gt", 0)],
            "success_when": [c("transaction.remaining_damage_debt", "eq", 0)],
            "abort_when": [c("opponent.prizes_remaining", "eq", 0)],
            "step_prompt_kinds": ["main", "effect_target", "attack_target", "send_out"],
        },
        {
            "transaction_id": "devolution-finish", "goal_id": "devolution-finish",
            "priority": 30, "max_own_turns": 1, "target_role": "opponent.pokemon",
            "start_when": [c("self.hand.count_uid", "gt", 0, tm_devolution),
                           c("damage.best_remaining_debt", "lte", 30),
                           c("transaction.candidate.is_damage_best", "eq", True)],
            "continue_when": [],
            "success_when": [c("transaction.remaining_damage_debt", "eq", 0)],
            "abort_when": [c("opponent.prizes_remaining", "eq", 0)],
            "step_prompt_kinds": ["main", "damage_target", "send_out"],
        },
        {
            "transaction_id": "munkidori-concentrated-ko", "goal_id": "munkidori-transfer",
            "priority": 25, "max_own_turns": 1, "target_role": "opponent.pokemon",
            "start_when": [c("transaction.candidate.is_transfer_best", "eq", True),
                           c("damage.available_mover_count", "gt", 0),
                           c("damage.best_transfer_attack_windows_to_ko", "eq", 1)],
            "continue_when": [c("transaction.remaining_damage_debt", "gt", 0)],
            "success_when": [c("transaction.remaining_damage_debt", "eq", 0)],
            "abort_when": [c("opponent.prizes_remaining", "eq", 0)],
            "step_prompt_kinds": ["main", "effect_target", "damage_target", "send_out"],
        },
        {
            "transaction_id": "backup-grimmsnarl-ready", "goal_id": "backup-grimmsnarl",
            "priority": 20, "max_own_turns": 2, "target_role": "self.pokemon",
            "start_when": [c("transaction.candidate.card_uid", "eq", grimmsnarl),
                           c("transaction.candidate.remaining_energy_debt", "gt", 0)],
            "continue_when": [c("transaction.remaining_energy_debt", "gt", 0)],
            "success_when": [c("transaction.remaining_energy_debt", "eq", 0)],
            "abort_when": [c("opponent.prizes_remaining", "eq", 0)],
            "step_prompt_kinds": ["main", "search", "assignment_source", "assignment_target", "send_out"],
        },
        {
            "transaction_id": "ogerpon-two-prize-conversion", "goal_id": "grimmsnarl-prize-route",
            "priority": 10, "max_own_turns": 2, "target_role": "opponent.pokemon",
            "start_when": [c("damage.best_prize_yield", "eq", 2),
                           c("transaction.candidate.is_damage_best", "eq", True)],
            "continue_when": [c("transaction.remaining_damage_debt", "gt", 0)],
            "success_when": [c("transaction.remaining_damage_debt", "eq", 0)],
            "abort_when": [c("opponent.prizes_remaining", "eq", 0)],
            "step_prompt_kinds": ["main", "damage_target", "send_out"],
        },
    ]
    return {
        "schema_version": 2,
        "adapter_id": package_id,
        "adapter_version": adapter_version,
        "goals": goals,
        "count_rules": count_rules,
        "rules": rules,
        "turn_routes": [],
        "route_candidates": [],
        "interaction_recipes": [],
        "turn_bonus_contracts": [],
        "damage_plans": damage_plans,
        "semantic_transactions": semantic_transactions,
    }


def _competitive_slot(
    serial: int,
    uid: str,
    *,
    remaining_hp: int,
    prize_value: int,
    energy_count: int,
    minimum_attack_energy_count: int,
) -> dict[str, object]:
    return {
        "serial": serial,
        "local_card_uid": uid,
        "remaining_hp": remaining_hp,
        "prize_value": prize_value,
        "attached_energy_count": energy_count,
        "attached_energy_uids": ["CSVE1C_GRA"] * energy_count,
        "minimum_attack_energy_count": minimum_attack_energy_count,
        "attack_ready": energy_count >= minimum_attack_energy_count,
        "energy_debt": max(0, minimum_attack_energy_count - energy_count),
    }


def _competitive_option(index: int, kind: str, **values: object) -> dict[str, object]:
    option: dict[str, object] = {
        "index": index,
        "kind": kind,
        "card_uid": None,
        "card_serial": None,
        "source_uid": None,
        "source_serial": None,
        "source_entity_serial": None,
        "target_uid": None,
        "target_serial": None,
        "target_entity_serial": None,
        "target_remaining_hp": None,
        "target_prize_value": None,
        "target_attached_energy_count": None,
        "target_attached_energy_uids": None,
        "target_minimum_attack_energy_count": None,
        "target_attack_ready": None,
        "target_energy_debt": None,
        "projected_damage": None,
        "projected_knockout": False,
        "requires_interaction": False,
        "attack_index": None,
        "option_number": None,
        "ability_index": None,
        "energy_type_raw": None,
        "energy_count": None,
        "special_condition_type": None,
        "pending_assignment_count": 0,
        "tags": [],
        "option_type_raw": 3,
        "option_player_index": 0,
    }
    option.update(values)
    if "option_type_raw" not in values:
        option["option_type_raw"] = {
            "use_ability": 12,
            "attack": 13,
            "end_turn": 14,
        }.get(kind, 3)
    if option["option_type_raw"] == 3 and option.get("card_uid") is None:
        if option.get("target_uid") is not None:
            option["card_uid"] = option["target_uid"]
            option["card_serial"] = option.get("target_serial")
        elif option.get("source_uid") is not None:
            option["card_uid"] = option["source_uid"]
            option["card_serial"] = option.get("source_serial")
    if option.get("card_uid") is not None and option.get("card_serial") is None:
        option["card_serial"] = 10_000 + index
    if option.get("source_uid") is not None and option.get("source_serial") is None:
        option["source_serial"] = 20_000 + index
    if option.get("target_uid") is not None and option.get("target_serial") is None:
        option["target_serial"] = 30_000 + index
    return option


def _ogerpon_scenario_frame(prompt_kind: str = "main") -> dict[str, object]:
    ogerpon = _competitive_slot(10, "CSV8C_028", remaining_hp=210, prize_value=2, energy_count=3, minimum_attack_energy_count=3)
    backup = _competitive_slot(11, "CSV8C_028", remaining_hp=210, prize_value=2, energy_count=1, minimum_attack_energy_count=3)
    dwebble = _competitive_slot(12, "CSV10C_009", remaining_hp=70, prize_value=1, energy_count=0, minimum_attack_energy_count=1)
    return {
        "schema_version": 2,
        "profile_id": "ptcgdap-competitive-public-frame-v2",
        "sequence": 1,
        "seat": 0,
        "prompt_kind": prompt_kind,
        "source": {"public_observation_hash": "A" * 64, "window_id": "B" * 64},
        "public_state": {
            "turn_number": 4,
            "phase": "MAIN",
            "self": {
                "hand": [],
                "active": [ogerpon],
                "bench": [backup, dwebble],
                "discard": [],
                "deck_count": 30,
                "prizes_remaining": 4,
                "turn": {"supporter_available": True, "manual_attachment_available": True, "retreat_available": True},
                "bench_capacity": 5,
            },
            "opponent": {
                "hand_count": 5,
                "active": [_competitive_slot(20, "CSV10C_052", remaining_hp=120, prize_value=1, energy_count=0, minimum_attack_energy_count=3)],
                "bench": [],
                "discard": [],
                "deck_count": 28,
                "prizes_remaining": 4,
            },
        },
        "select_semantics": {"min_count": 1, "max_count": 1, "select_type_raw": 0, "select_context_raw": 0},
        "options": [],
    }


def _marnie_slot(
    entity_serial: int,
    card_serial: int,
    uid: str,
    *,
    remaining_hp: int,
    max_hp: int,
    prize_value: int,
    energy_count: int = 0,
    minimum_attack_energy_count: int = 0,
    damage_counters: int = 0,
    tool_uid: str | None = None,
) -> dict[str, object]:
    return {
        "serial": card_serial,
        "entity_serial": entity_serial,
        "local_card_uid": uid,
        "remaining_hp": remaining_hp,
        "max_hp": max_hp,
        "damage_counters": damage_counters,
        "prize_value": prize_value,
        "attached_energy_count": energy_count,
        "attached_energy_uids": ["CSVE1C_DAR"] * energy_count,
        "attached_tool_uid": tool_uid,
        "pokemon_stack_uids": [uid],
        "minimum_attack_energy_count": minimum_attack_energy_count,
        "attack_ready": energy_count >= minimum_attack_energy_count,
        "energy_debt": max(0, minimum_attack_energy_count - energy_count),
    }


def _marnie_scenario_frame(prompt_kind: str = "main") -> dict[str, object]:
    active = _marnie_slot(
        100, 101, "CSV10C_148", remaining_hp=260, max_hp=320, prize_value=2,
        energy_count=2, minimum_attack_energy_count=2, damage_counters=60,
    )
    bench = [
        _marnie_slot(110, 111, "CSV7C_059", remaining_hp=90, max_hp=90, prize_value=1),
        _marnie_slot(120, 121, "CSV7C_059", remaining_hp=90, max_hp=90, prize_value=1),
        _marnie_slot(130, 131, "CSV8C_094", remaining_hp=90, max_hp=110, prize_value=1,
                     energy_count=1, minimum_attack_energy_count=1, damage_counters=20),
        _marnie_slot(140, 141, "CSV10C_148", remaining_hp=320, max_hp=320, prize_value=2,
                     energy_count=1, minimum_attack_energy_count=2),
    ]
    opponent_active = _marnie_slot(
        900, 901, "CSV8C_028", remaining_hp=210, max_hp=210, prize_value=2,
        energy_count=3, minimum_attack_energy_count=3,
    )
    opponent_bench = [
        _marnie_slot(
            910, 911, "CSV8C_028", remaining_hp=210, max_hp=210, prize_value=2,
            energy_count=1, minimum_attack_energy_count=3,
        )
    ]
    return {
        "schema_version": 2,
        "profile_id": "ptcgdap-competitive-public-frame-v2",
        "sequence": 1,
        "seat": 0,
        "prompt_kind": prompt_kind,
        "source": {"public_observation_hash": "A" * 64, "window_id": "B" * 64},
        "public_state": {
            "turn_number": 8,
            "phase": "MAIN",
            "self": {
                "hand": [], "active": [active], "bench": bench, "discard": [],
                "deck_count": 24, "prizes_remaining": 4,
                "turn": {"supporter_available": True, "manual_attachment_available": True,
                         "retreat_available": True},
                "bench_capacity": 5,
            },
            "opponent": {
                "hand_count": 5, "active": [opponent_active], "bench": opponent_bench,
                "discard": [], "deck_count": 23, "prizes_remaining": 4,
            },
        },
        "select_semantics": {
            "min_count": 1, "max_count": 1, "select_type_raw": 0,
            "select_context_raw": 0,
        },
        "options": [],
    }


def _generate_marnie_gift_box_scenarios(workspace: Path) -> dict[str, object]:
    scenario_root = workspace / "scenarios"
    cases: list[dict[str, object]] = []

    def add(
        scenario_id: str,
        frame: dict[str, object],
        expected: list[int],
        *,
        matched_rule_id: str = "",
        selected_source: str | None = None,
        mandatory: list[int] | None = None,
        terminal: list[int] | None = None,
        tiers: list[dict[str, object]] | None = None,
        vetoed: list[int] | None = None,
    ) -> None:
        sequence = len(cases) + 1
        frame["sequence"] = sequence
        frame["source"]["window_id"] = f"{sequence:064X}"
        path = f"{sequence:02d}-{scenario_id}.json"
        write_json(scenario_root / path, {
            "document_type": "ptcg_strategy_forge_competitive_scenario_v2",
            "schema_version": 2,
            "scenario_id": scenario_id,
            "frame": frame,
            "base_authority": {
                "mandatory_indexes": list(mandatory or []),
                "terminal_indexes": list(terminal or []),
                "base_hard_tiers": list(
                    tiers or [{"index": index, "tier": [0]} for index in range(len(frame["options"]))]
                ),
                "base_vetoed_indexes": list(vetoed or []),
            },
            "expected_selected_indexes": expected,
        })
        expect: dict[str, object] = {
            "status": "passed", "selected_indexes": expected,
            "selected_source": selected_source or (
                "terminal" if terminal else "mandatory" if mandatory else "adapter_proposal"
            ),
        }
        if matched_rule_id:
            expect["matched_rule_id"] = matched_rule_id
        cases.append({"id": scenario_id, "path": f"scenarios/{path}", "expect": expect})

    def setup_frame(opponent_bench_count: int) -> dict[str, object]:
        frame = _marnie_scenario_frame("setup_active")
        frame["public_state"]["self"]["active"] = []
        frame["public_state"]["self"]["bench"] = []
        frame["public_state"]["opponent"]["bench"] = (
            frame["public_state"]["opponent"]["bench"][:opponent_bench_count]
        )
        frame["options"] = [
            _competitive_option(0, "setup_active", card_uid="CSV9.5C_004"),
            _competitive_option(1, "setup_active", card_uid="CSV10C_146"),
        ]
        return frame

    add("opening-budew-lock", setup_frame(0), [0], matched_rule_id="opening.budew-lock")
    add("opening-impidimp-engine", setup_frame(1), [1], matched_rule_id="opening.impidimp-engine")
    opening_reordered = setup_frame(0)
    opening_reordered["options"].reverse()
    for index, option in enumerate(opening_reordered["options"]): option["index"] = index
    add("opening-budew-semantic-reorder", opening_reordered, [1], matched_rule_id="opening.budew-lock")

    evolve = _marnie_scenario_frame()
    evolve["options"] = [
        _competitive_option(0, "evolve", card_uid="CSV7C_059", target_uid="CSV9.5C_043"),
        _competitive_option(1, "end_turn"),
    ]
    evolve["public_state"]["self"]["bench"] = [
        _marnie_slot(150, 151, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1),
    ]
    add("single-froslass-threshold", evolve, [0], matched_rule_id="main.evolve-froslass-first")
    second = copy.deepcopy(evolve)
    second["public_state"]["self"]["bench"].append(
        _marnie_slot(110, 111, "CSV7C_059", remaining_hp=90, max_hp=90, prize_value=1)
    )
    second["public_state"]["opponent"]["bench"].append(
        _marnie_slot(920, 921, "CSV8C_028", remaining_hp=210, max_hp=210, prize_value=2)
    )
    add("double-froslass-wide-board", second, [0], matched_rule_id="main.evolve-froslass-second-vs-wide-board")
    narrow = copy.deepcopy(second)
    narrow["public_state"]["opponent"]["bench"] = []
    add("double-froslass-narrow-board-deferred", narrow, [1], selected_source="deterministic_fallback")

    def punk_frame(active_energy: int, backup_energy: int, option_count: int = 5) -> dict[str, object]:
        frame = _marnie_scenario_frame("assignment_source")
        frame["select_semantics"].update({"min_count": 0, "max_count": 5, "select_type_raw": 1,
                                          "select_context_raw": 22})
        frame["public_state"]["self"]["active"][0].update({
            "attached_energy_count": active_energy, "attached_energy_uids": ["CSVE1C_DAR"] * active_energy,
            "energy_debt": max(0, 2 - active_energy), "attack_ready": active_energy >= 2,
        })
        frame["public_state"]["self"]["bench"][-1].update({
            "attached_energy_count": backup_energy, "attached_energy_uids": ["CSVE1C_DAR"] * backup_energy,
            "energy_debt": max(0, 2 - backup_energy), "attack_ready": backup_energy >= 2,
        })
        frame["options"] = [
            _competitive_option(i, "assignment_source", card_uid="CSVE1C_DAR",
                                source_uid="CSV10C_148")
            for i in range(option_count)
        ]
        return frame

    add("punk-up-exact-zero", punk_frame(2, 2), [], matched_rule_id="punk-up.select-dark")
    add("punk-up-exact-one", punk_frame(2, 1), [0], matched_rule_id="punk-up.select-dark")
    add("punk-up-exact-two", punk_frame(2, 0), [0, 1], matched_rule_id="punk-up.select-dark")
    add("punk-up-exact-three", punk_frame(1, 0), [0, 1, 2], matched_rule_id="punk-up.select-dark")
    add("punk-up-exact-four", punk_frame(0, 0), [0, 1, 2, 3], matched_rule_id="punk-up.select-dark")
    punk_reordered = punk_frame(1, 0)
    punk_reordered["options"] = [
        _competitive_option(0, "assignment_source", card_uid="CSV3C_123",
                            source_uid="CSV10C_148"),
        *[
            _competitive_option(i + 1, "assignment_source", card_uid="CSVE1C_DAR",
                                source_uid="CSV10C_148")
            for i in range(4)
        ],
    ]
    add("punk-up-exact-three-reordered", punk_reordered, [1, 2, 3], matched_rule_id="punk-up.select-dark")

    assign = _marnie_scenario_frame("assignment_target")
    assign["select_semantics"].update({"select_type_raw": 1, "select_context_raw": 22})
    assign["options"] = [
        _competitive_option(0, "assignment_target", source_uid="CSV10C_148", target_uid="CSV10C_148",
                            target_serial=101, target_entity_serial=100, target_energy_debt=0,
                            target_attack_ready=True),
        _competitive_option(1, "assignment_target", source_uid="CSV10C_148", target_uid="CSV10C_148",
                            target_serial=141, target_entity_serial=140, target_energy_debt=1,
                            target_attack_ready=False),
    ]
    add("punk-up-cross-target-allocation", assign, [1], matched_rule_id="punk-up.target-current-debt")
    assign_flip = copy.deepcopy(assign)
    assign_flip["options"][0]["target_energy_debt"] = 1
    assign_flip["options"][0]["target_attack_ready"] = False
    assign_flip["options"][1]["target_energy_debt"] = 2
    add("punk-up-current-attacker-first", assign_flip, [0], matched_rule_id="punk-up.target-active-debt")

    def manual_attach_frame(munkidori_energy: int) -> dict[str, object]:
        frame = _marnie_scenario_frame()
        frame["public_state"]["self"]["bench"][2].update({
            "attached_energy_count": munkidori_energy,
            "attached_energy_uids": ["CSVE1C_DAR"] * munkidori_energy,
            "energy_debt": max(0, 1 - munkidori_energy),
            "attack_ready": munkidori_energy >= 1,
        })
        frame["public_state"]["self"]["bench"][3] = _marnie_slot(
            140, 141, "CSV10C_147", remaining_hp=100, max_hp=100, prize_value=1,
            energy_count=0, minimum_attack_energy_count=2,
        )
        frame["options"] = [
            _competitive_option(
                0, "attach_energy", card_uid="CSVE1C_DAR", target_uid="CSV8C_094",
                target_entity_serial=130, target_attached_energy_count=munkidori_energy,
                target_energy_debt=max(0, 1 - munkidori_energy),
                target_attack_ready=munkidori_energy >= 1,
            ),
            _competitive_option(
                1, "attach_energy", card_uid="CSVE1C_DAR", target_uid="CSV10C_147",
                target_entity_serial=140, target_attached_energy_count=0,
                target_energy_debt=2, target_attack_ready=False,
            ),
        ]
        return frame

    attach_zero = manual_attach_frame(0)
    add("manual-attach-munkidori-zero-energy", attach_zero, [0], matched_rule_id="attach.munkidori-first")
    attach_one = manual_attach_frame(1)
    add("manual-attach-munkidori-one-energy-flips-to-line", attach_one, [1],
        matched_rule_id="attach.morgrem-line-debt")
    attach_one_reordered = manual_attach_frame(1)
    attach_one_reordered["options"].reverse()
    for index, option in enumerate(attach_one_reordered["options"]): option["index"] = index
    add("manual-attach-munkidori-one-energy-semantic-reorder", attach_one_reordered, [0],
        matched_rule_id="attach.morgrem-line-debt")

    def denied_active_frame(active_energy: int, reordered: bool = False) -> dict[str, object]:
        frame = _marnie_scenario_frame()
        active = frame["public_state"]["self"]["active"][0]
        active.update({
            "attached_energy_count": active_energy,
            "attached_energy_uids": ["CSVE1C_DAR"] * active_energy,
            "energy_debt": max(0, 2 - active_energy),
            "attack_ready": active_energy >= 2,
        })
        frame["public_state"]["self"]["bench"][2].update({
            "attached_energy_count": 0, "attached_energy_uids": [],
            "energy_debt": 1, "attack_ready": False,
        })
        frame["options"] = [
            _competitive_option(
                0, "attach_energy", card_uid="CSVE1C_DAR", target_uid="CSV8C_094",
                target_entity_serial=130, target_attached_energy_count=0,
                target_energy_debt=1, target_attack_ready=False,
            ),
            _competitive_option(
                1, "attach_energy", card_uid="CSVE1C_DAR", target_uid="CSV10C_148",
                target_entity_serial=100, target_attached_energy_count=active_energy,
                target_energy_debt=max(0, 2 - active_energy),
                target_attack_ready=active_energy >= 2,
            ),
        ]
        if reordered:
            frame["options"].reverse()
            for index, option in enumerate(frame["options"]): option["index"] = index
        return frame

    add("manual-attach-repairs-denied-active-grimmsnarl", denied_active_frame(1), [1],
        matched_rule_id="attach.active-grimmsnarl-after-denial")
    add("manual-attach-repairs-denied-active-grimmsnarl-reordered",
        denied_active_frame(1, reordered=True), [0],
        matched_rule_id="attach.active-grimmsnarl-after-denial")
    add("manual-attach-ready-active-flips-to-munkidori", denied_active_frame(2), [0],
        matched_rule_id="attach.munkidori-first")

    def tm_evolution_frame(active_energy: int) -> dict[str, object]:
        frame = _marnie_scenario_frame()
        frame["public_state"]["self"]["active"] = [
            _marnie_slot(
                200, 201, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1,
                energy_count=active_energy, minimum_attack_energy_count=1,
            )
        ]
        frame["public_state"]["self"]["bench"] = [
            _marnie_slot(210, 211, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1)
        ]
        frame["public_state"]["self"]["hand"] = [
            {"serial": 50, "local_card_uid": "CSV5C_119"},
            {"serial": 51, "local_card_uid": "CSVE1C_DAR"},
        ]
        frame["options"] = [
            _competitive_option(
                0, "attach_energy", card_uid="CSVE1C_DAR", target_uid="CSV9.5C_043",
                target_entity_serial=200,
                target_attached_energy_count=active_energy,
                target_energy_debt=max(0, 1 - active_energy),
                target_attack_ready=active_energy >= 1,
            ),
            _competitive_option(
                1, "attach_tool", card_uid="CSV5C_119", target_uid="CSV9.5C_043",
                target_entity_serial=200,
                target_attached_energy_count=active_energy,
                target_energy_debt=max(0, 1 - active_energy),
                target_attack_ready=active_energy >= 1,
            ),
            _competitive_option(
                2, "attach_tool", card_uid="CSV5C_119", target_uid="CSV9.5C_043",
                target_entity_serial=210,
                target_attached_energy_count=0, target_energy_debt=1,
                target_attack_ready=False,
            ),
            _competitive_option(3, "end_turn"),
        ]
        return frame

    tm_energy_first = tm_evolution_frame(0)
    add("tm-evolution-active-energy-first", tm_energy_first, [0],
        matched_rule_id="attach.tm-evolution-active-snorunt")
    tm_after_energy = tm_evolution_frame(1)
    add("tm-evolution-active-after-energy", tm_after_energy, [1], matched_rule_id="main.tm-evolution")
    tm_after_energy_reordered = tm_evolution_frame(1)
    tm_after_energy_reordered["options"] = [
        tm_after_energy_reordered["options"][1], tm_after_energy_reordered["options"][2],
        tm_after_energy_reordered["options"][0], tm_after_energy_reordered["options"][3],
    ]
    for index, option in enumerate(tm_after_energy_reordered["options"]): option["index"] = index
    add("tm-evolution-active-after-energy-semantic-reorder", tm_after_energy_reordered, [0],
        matched_rule_id="main.tm-evolution")
    tm_defer = tm_evolution_frame(0)
    tm_defer["options"] = [tm_defer["options"][1], tm_defer["options"][3]]
    for index, option in enumerate(tm_defer["options"]): option["index"] = index
    add("tm-evolution-defer-without-energy", tm_defer, [1],
        matched_rule_id="main.defer-tm-evolution-without-energy", selected_source="deterministic_fallback")

    tm_execute = _marnie_scenario_frame()
    tm_execute["public_state"]["self"]["active"] = [
        _marnie_slot(
            200, 201, "CSV8C_094", remaining_hp=110, max_hp=110, prize_value=1,
            energy_count=1, minimum_attack_energy_count=1, tool_uid="CSV5C_119",
        )
    ]
    tm_execute["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1),
        _marnie_slot(220, 221, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1),
    ]
    tm_execute["options"] = [
        _competitive_option(
            0, "granted_attack", source_uid="CSV5C_119", attack_index=0,
            requires_interaction=True,
        ),
        _competitive_option(1, "end_turn"),
    ]
    add("tm-evolution-executes-granted-attack", tm_execute, [0],
        matched_rule_id="attack.tm-evolution-develop")
    tm_execute_reordered = copy.deepcopy(tm_execute)
    tm_execute_reordered["options"].reverse()
    for index, option in enumerate(tm_execute_reordered["options"]):
        option["index"] = index
    add("tm-evolution-executes-granted-attack-reordered", tm_execute_reordered, [1],
        matched_rule_id="attack.tm-evolution-develop")
    tm_wrong_source = copy.deepcopy(tm_execute)
    tm_wrong_source["options"][0]["source_uid"] = "CSV5C_120"
    add("tm-evolution-wrong-source-fails-closed", tm_wrong_source, [1],
        selected_source="deterministic_fallback")
    add("tm-evolution-terminal-protection", copy.deepcopy(tm_execute), [1], terminal=[1],
        matched_rule_id="attack.tm-evolution-develop", selected_source="terminal")
    add("tm-evolution-veto-protection", copy.deepcopy(tm_execute), [1], vetoed=[0],
        matched_rule_id="attack.tm-evolution-develop", selected_source="deterministic_fallback")
    tm_no_bench = copy.deepcopy(tm_execute)
    tm_no_bench["public_state"]["self"]["active"] = [
        _marnie_slot(
            200, 201, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1,
            energy_count=1, minimum_attack_energy_count=1, tool_uid="CSV5C_119",
        )
    ]
    tm_no_bench["public_state"]["self"]["bench"] = []
    add("tm-evolution-active-only-fails-closed", tm_no_bench, [1],
        selected_source="deterministic_fallback")
    tm_impidimp_bench = copy.deepcopy(tm_no_bench)
    tm_impidimp_bench["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1)
    ]
    add("tm-evolution-bench-impidimp-flips-to-attack", tm_impidimp_bench, [0],
        matched_rule_id="attack.tm-evolution-develop")
    tm_snorunt_bench = copy.deepcopy(tm_no_bench)
    tm_snorunt_bench["public_state"]["self"]["bench"] = [
        _marnie_slot(220, 221, "CSV9.5C_043", remaining_hp=60, max_hp=60, prize_value=1)
    ]
    add("tm-evolution-bench-snorunt-flips-to-attack", tm_snorunt_bench, [0],
        matched_rule_id="attack.tm-evolution-develop-snorunt")

    def poffin_frame(*, impidimp_deployed: bool, reordered: bool = False) -> dict[str, object]:
        frame = _marnie_scenario_frame("search")
        frame["select_semantics"].update({
            "min_count": 0, "max_count": 2, "select_type_raw": 1, "select_context_raw": 7,
        })
        if impidimp_deployed:
            frame["public_state"]["self"]["bench"][3] = _marnie_slot(
                140, 141, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1,
            )
        options = [
            _competitive_option(0, "search", card_uid="CSV9.5C_043", source_uid="CSV7C_177"),
            _competitive_option(1, "search", card_uid="CSV10C_146", source_uid="CSV7C_177"),
            _competitive_option(2, "search", card_uid="CSV10C_146", source_uid="CSV7C_177"),
            _competitive_option(3, "search", card_uid="CSV9.5C_004", source_uid="CSV7C_177"),
            _competitive_option(4, "search", card_uid="CSV9.5C_043", source_uid="CSV7C_177"),
        ]
        if reordered:
            options = [options[2], options[4], options[3], options[0], options[1]]
            for index, option in enumerate(options): option["index"] = index
        frame["options"] = options
        return frame

    add("poffin-exact-two-impidimp-line", poffin_frame(impidimp_deployed=False), [1, 2],
        matched_rule_id="search.poffin-impidimp-first")
    add("poffin-exact-two-impidimp-line-reordered",
        poffin_frame(impidimp_deployed=False, reordered=True), [0, 4],
        matched_rule_id="search.poffin-impidimp-first")
    add("poffin-second-line-flips-to-snorunt", poffin_frame(impidimp_deployed=True), [0, 4],
        matched_rule_id="search.poffin-snorunt-after-line")
    add("poffin-second-line-flips-to-snorunt-reordered",
        poffin_frame(impidimp_deployed=True, reordered=True), [1, 3],
        matched_rule_id="search.poffin-snorunt-after-line")

    def evolution_search_frame(source_uid: str, board_uid: str) -> dict[str, object]:
        frame = _marnie_scenario_frame("search")
        frame["select_semantics"].update({"min_count": 0, "max_count": 1})
        hp = 100 if board_uid == "CSV10C_147" else 70 if board_uid == "CSV10C_146" else 60
        frame["public_state"]["self"]["active"] = [
            _marnie_slot(200, 201, board_uid, remaining_hp=hp, max_hp=hp, prize_value=1)
        ]
        frame["public_state"]["self"]["bench"] = []
        frame["options"] = [
            _competitive_option(0, "search", card_uid="CSV10C_146", source_uid=source_uid),
            _competitive_option(1, "search", card_uid="CSV10C_147", source_uid=source_uid),
            _competitive_option(2, "search", card_uid="CSV10C_148", source_uid=source_uid),
            _competitive_option(3, "search", card_uid="CSV7C_059", source_uid=source_uid),
            _competitive_option(4, "search", card_uid="CSV8C_094", source_uid=source_uid),
        ]
        return frame

    spikemuth_grimmsnarl = evolution_search_frame("CSV10C_216", "CSV10C_147")
    add("spikemuth-completes-grimmsnarl-line", spikemuth_grimmsnarl, [2],
        matched_rule_id="search.spikemuth-grimmsnarl-from-morgrem")
    spikemuth_reordered = evolution_search_frame("CSV10C_216", "CSV10C_147")
    spikemuth_reordered["options"] = [
        spikemuth_reordered["options"][2], spikemuth_reordered["options"][4],
        spikemuth_reordered["options"][0], spikemuth_reordered["options"][3],
        spikemuth_reordered["options"][1],
    ]
    for index, option in enumerate(spikemuth_reordered["options"]): option["index"] = index
    add("spikemuth-completes-grimmsnarl-line-reordered", spikemuth_reordered, [0],
        matched_rule_id="search.spikemuth-grimmsnarl-from-morgrem")
    spikemuth_morgrem = evolution_search_frame("CSV10C_216", "CSV10C_146")
    add("spikemuth-completes-morgrem-line", spikemuth_morgrem, [1],
        matched_rule_id="search.spikemuth-morgrem-from-impidimp")
    spikemuth_candy = evolution_search_frame("CSV10C_216", "CSV10C_146")
    spikemuth_candy["public_state"]["self"]["hand"] = [
        {"local_card_uid": "CSVH1C_045", "serial": 301},
    ]
    add("spikemuth-candy-skips-morgrem", spikemuth_candy, [2],
        matched_rule_id="search.spikemuth-grimmsnarl-with-rare-candy")
    spikemuth_candy_reordered = copy.deepcopy(spikemuth_candy)
    spikemuth_candy_reordered["options"] = [
        spikemuth_candy_reordered["options"][2], spikemuth_candy_reordered["options"][4],
        spikemuth_candy_reordered["options"][1], spikemuth_candy_reordered["options"][0],
        spikemuth_candy_reordered["options"][3],
    ]
    for index, option in enumerate(spikemuth_candy_reordered["options"]): option["index"] = index
    add("spikemuth-candy-skips-morgrem-reordered", spikemuth_candy_reordered, [0],
        matched_rule_id="search.spikemuth-grimmsnarl-with-rare-candy")
    ultra_candy = evolution_search_frame("CSV1C_112", "CSV10C_146")
    ultra_candy["public_state"]["self"]["hand"] = [
        {"local_card_uid": "CSVH1C_045", "serial": 302},
    ]
    add("ultra-ball-candy-skips-morgrem", ultra_candy, [2],
        matched_rule_id="search.ultra-ball-grimmsnarl-with-rare-candy")
    ultra_candy_reordered = copy.deepcopy(ultra_candy)
    ultra_candy_reordered["options"] = [
        ultra_candy_reordered["options"][4], ultra_candy_reordered["options"][2],
        ultra_candy_reordered["options"][0], ultra_candy_reordered["options"][3],
        ultra_candy_reordered["options"][1],
    ]
    for index, option in enumerate(ultra_candy_reordered["options"]): option["index"] = index
    add("ultra-ball-candy-skips-morgrem-reordered", ultra_candy_reordered, [1],
        matched_rule_id="search.ultra-ball-grimmsnarl-with-rare-candy")
    def arven_search_frame(kind: str, reordered: bool = False) -> dict[str, object]:
        frame = _marnie_scenario_frame("search")
        frame["select_semantics"].update({
            "min_count": 0, "max_count": 1, "select_type_raw": 1, "select_context_raw": 7,
        })
        frame["public_state"]["self"]["active"] = [
            _marnie_slot(200, 201, "CSV9.5C_004", remaining_hp=30, max_hp=30, prize_value=1)
        ]
        frame["public_state"]["self"]["bench"] = [
            _marnie_slot(210, 211, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1)
        ]
        if kind == "item":
            options = [
                _competitive_option(0, "search", card_uid="CSV8C_183", source_uid="CSV1C_123"),
                _competitive_option(1, "search", card_uid="CSV7C_177", source_uid="CSV1C_123"),
                _competitive_option(2, "search", card_uid="CSVH1C_045", source_uid="CSV1C_123"),
                _competitive_option(3, "search", card_uid="CSV1C_112", source_uid="CSV1C_123"),
            ]
        else:
            options = [
                _competitive_option(0, "search", card_uid="CSV1C_117", source_uid="CSV1C_123"),
                _competitive_option(1, "search", card_uid="CSV7C_185", source_uid="CSV1C_123"),
                _competitive_option(2, "search", card_uid="CSV5C_119", source_uid="CSV1C_123"),
                _competitive_option(3, "search", card_uid="CSV5C_120", source_uid="CSV1C_123"),
            ]
        if reordered:
            options = [options[2], options[0], options[3], options[1]]
            for index, option in enumerate(options):
                option["index"] = index
        frame["options"] = options
        return frame

    add("arven-finds-poffin-core", arven_search_frame("item"), [1],
        matched_rule_id="search.arven-poffin-core")
    add("arven-finds-poffin-core-reordered", arven_search_frame("item", reordered=True), [3],
        matched_rule_id="search.arven-poffin-core")
    add("arven-finds-tm-evolution-core", arven_search_frame("tool"), [2],
        matched_rule_id="search.arven-tm-evolution-core")
    add("arven-finds-tm-evolution-core-reordered", arven_search_frame("tool", reordered=True), [0],
        matched_rule_id="search.arven-tm-evolution-core")

    arven_no_evolution_target = arven_search_frame("tool")
    arven_no_evolution_target["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV7C_059", remaining_hp=90, max_hp=90, prize_value=1)
    ]
    add("arven-without-evolution-target-finds-rescue-board", arven_no_evolution_target, [1],
        matched_rule_id="search.arven-rescue-board-budew")
    arven_no_evolution_target_reordered = copy.deepcopy(arven_no_evolution_target)
    arven_no_evolution_target_reordered["options"] = [
        arven_no_evolution_target_reordered["options"][2],
        arven_no_evolution_target_reordered["options"][0],
        arven_no_evolution_target_reordered["options"][3],
        arven_no_evolution_target_reordered["options"][1],
    ]
    for index, option in enumerate(arven_no_evolution_target_reordered["options"]):
        option["index"] = index
    add("arven-without-evolution-target-finds-rescue-board-reordered",
        arven_no_evolution_target_reordered, [3],
        matched_rule_id="search.arven-rescue-board-budew")

    artazon_main = _marnie_scenario_frame()
    artazon_main["public_state"]["self"]["active"] = [
        _marnie_slot(200, 201, "CSV9.5C_004", remaining_hp=30, max_hp=30, prize_value=1)
    ]
    artazon_main["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV7C_059", remaining_hp=90, max_hp=90, prize_value=1)
    ]
    artazon_main["options"] = [
        _competitive_option(0, "use_stadium_effect", card_uid="CSV2C_127", source_uid="CSV2C_127"),
        _competitive_option(1, "play_trainer", card_uid="CSV1C_123"),
        _competitive_option(2, "end_turn"),
    ]
    add("artazon-use-before-supporter", artazon_main, [0], matched_rule_id="main.artazon-use")

    def artazon_search_frame(reordered: bool = False) -> dict[str, object]:
        frame = _marnie_scenario_frame("search")
        frame["select_semantics"].update({
            "min_count": 0, "max_count": 1, "select_type_raw": 1, "select_context_raw": 7,
        })
        frame["public_state"]["self"]["active"] = [
            _marnie_slot(200, 201, "CSV9.5C_004", remaining_hp=30, max_hp=30, prize_value=1)
        ]
        frame["public_state"]["self"]["bench"] = []
        options = [
            _competitive_option(0, "search", card_uid="CSV9.5C_043", source_uid="CSV2C_127"),
            _competitive_option(1, "search", card_uid="CSV9.5C_004", source_uid="CSV2C_127"),
            _competitive_option(2, "search", card_uid="CSV10C_146", source_uid="CSV2C_127"),
            _competitive_option(3, "search", card_uid="CSV8C_094", source_uid="CSV2C_127"),
        ]
        if reordered:
            options = [options[3], options[2], options[0], options[1]]
            for index, option in enumerate(options):
                option["index"] = index
        frame["options"] = options
        return frame

    add("artazon-deploys-impidimp", artazon_search_frame(), [2],
        matched_rule_id="search.artazon-impidimp-first")
    add("artazon-deploys-impidimp-reordered", artazon_search_frame(reordered=True), [1],
        matched_rule_id="search.artazon-impidimp-first")

    artazon_after_impidimp = artazon_search_frame()
    artazon_after_impidimp["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1)
    ]
    add("artazon-after-impidimp-deploys-snorunt", artazon_after_impidimp, [0],
        matched_rule_id="search.artazon-snorunt-engine")

    artazon_after_core = artazon_search_frame()
    artazon_after_core["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV10C_146", remaining_hp=70, max_hp=70, prize_value=1),
        _marnie_slot(220, 221, "CSV9.5C_043", remaining_hp=50, max_hp=50, prize_value=1),
    ]
    add("artazon-after-core-deploys-munkidori", artazon_after_core, [3],
        matched_rule_id="search.artazon-munkidori-engine")

    artazon_mandatory = copy.deepcopy(artazon_main)
    add("artazon-yields-to-mandatory-option", artazon_mandatory, [1], mandatory=[1])

    artazon_full = _marnie_scenario_frame()
    artazon_full["public_state"]["self"]["bench"].append(
        _marnie_slot(150, 151, "CSV10C_007", remaining_hp=70, max_hp=70, prize_value=1)
    )
    artazon_full["options"] = [
        _competitive_option(0, "play_stadium", card_uid="CSV2C_127"),
        _competitive_option(1, "end_turn"),
    ]
    add("artazon-bench-full-deferred", artazon_full, [1],
        matched_rule_id="main.defer-artazon-bench-full",
        selected_source="deterministic_fallback")

    band_target = _marnie_scenario_frame()
    band_target["options"] = [
        _competitive_option(0, "attach_tool", card_uid="CSV1C_117", target_uid="CSV9.5C_043",
                            target_entity_serial=150),
        _competitive_option(1, "attach_tool", card_uid="CSV1C_117", target_uid="CSV10C_148",
                            target_entity_serial=100, target_attack_ready=True),
        _competitive_option(2, "end_turn"),
    ]
    add("defiance-band-binds-ready-grimmsnarl", band_target, [1],
        matched_rule_id="main.defiance-band-grimmsnarl")
    band_reordered = copy.deepcopy(band_target)
    band_reordered["options"] = [band_reordered["options"][1], band_reordered["options"][2],
                                  band_reordered["options"][0]]
    for index, option in enumerate(band_reordered["options"]): option["index"] = index
    add("defiance-band-binds-ready-grimmsnarl-reordered", band_reordered, [0],
        matched_rule_id="main.defiance-band-grimmsnarl")

    gust = _marnie_scenario_frame("effect_target")
    gust["options"] = [
        _competitive_option(0, "effect_target", source_uid="CSVH1aC_023", target_uid="CSV10C_010",
                            target_entity_serial=930, target_remaining_hp=140, target_prize_value=1),
        _competitive_option(1, "effect_target", source_uid="CSVH1aC_023", target_uid="CSV8C_028",
                            target_entity_serial=910, target_remaining_hp=180, target_prize_value=2),
    ]
    add("boss-targets-two-prize", gust, [1], matched_rule_id="gust.target-two-prize")
    gust_reordered = copy.deepcopy(gust)
    gust_reordered["options"].reverse()
    for index, option in enumerate(gust_reordered["options"]): option["index"] = index
    add("boss-targets-two-prize-reordered", gust_reordered, [0], matched_rule_id="gust.target-two-prize")

    boss_without_active_attacker = _marnie_scenario_frame()
    boss_without_active_attacker["public_state"]["self"]["active"] = [
        _marnie_slot(200, 201, "CSV8C_094", remaining_hp=110, max_hp=110, prize_value=1,
                     energy_count=1, minimum_attack_energy_count=1)
    ]
    boss_without_active_attacker["public_state"]["self"]["bench"] = [
        _marnie_slot(210, 211, "CSV10C_148", remaining_hp=320, max_hp=320, prize_value=2,
                     energy_count=2, minimum_attack_energy_count=2)
    ]
    boss_without_active_attacker["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSVH1aC_023"),
        _competitive_option(1, "end_turn"),
    ]
    add("boss-with-ready-bench-only-is-deferred", boss_without_active_attacker, [1],
        matched_rule_id="main.defer-boss-without-active-attacker",
        selected_source="deterministic_fallback")
    boss_without_active_attacker_reordered = copy.deepcopy(boss_without_active_attacker)
    boss_without_active_attacker_reordered["options"].reverse()
    for index, option in enumerate(boss_without_active_attacker_reordered["options"]):
        option["index"] = index
    add("boss-with-ready-bench-only-is-deferred-reordered",
        boss_without_active_attacker_reordered, [0],
        matched_rule_id="main.defer-boss-without-active-attacker",
        selected_source="deterministic_fallback")

    munk_source = _marnie_scenario_frame("effect_target")
    munk_source["options"] = [
        _competitive_option(0, "effect_target", source_uid="CSV8C_094", target_uid="CSV7C_059",
                            target_entity_serial=110, target_remaining_hp=30, target_prize_value=1),
        _competitive_option(1, "effect_target", source_uid="CSV8C_094", target_uid="CSV10C_148",
                            target_entity_serial=100, target_remaining_hp=80, target_prize_value=2),
    ]
    add("munkidori-source-protects-two-prize", munk_source, [1],
        matched_rule_id="munkidori.source-protect-two-prize")
    munk_source_reordered = copy.deepcopy(munk_source)
    munk_source_reordered["options"].reverse()
    for index, option in enumerate(munk_source_reordered["options"]): option["index"] = index
    add("munkidori-source-protects-two-prize-reordered", munk_source_reordered, [0],
        matched_rule_id="munkidori.source-protect-two-prize")

    munk_count = _marnie_scenario_frame("effect_target")
    munk_count["select_semantics"].update({
        "min_count": 1, "max_count": 1, "select_type_raw": 8, "select_context_raw": 40,
    })
    munk_count["options"] = [
        _competitive_option(0, "effect_target", option_type_raw=0, option_number=1),
        _competitive_option(1, "effect_target", option_type_raw=0, option_number=3),
        _competitive_option(2, "effect_target", option_type_raw=0, option_number=2),
    ]
    add("munkidori-count-moves-full-public-amount", munk_count, [1],
        matched_rule_id="munkidori.count-full-public-transfer")
    munk_count_reordered = copy.deepcopy(munk_count)
    munk_count_reordered["options"] = [munk_count_reordered["options"][2],
                                        munk_count_reordered["options"][0],
                                        munk_count_reordered["options"][1]]
    for index, option in enumerate(munk_count_reordered["options"]): option["index"] = index
    add("munkidori-count-moves-full-public-amount-reordered", munk_count_reordered, [2],
        matched_rule_id="munkidori.count-full-public-transfer")

    munk_target = _marnie_scenario_frame("effect_target")
    munk_target["select_semantics"].update({"select_type_raw": 1, "select_context_raw": 13})
    munk_target["public_state"]["self"]["bench"][2].update({"damage_counters": 20})
    munk_target["public_state"]["self"]["bench"][3] = _marnie_slot(
        140, 141, "CSV8C_094", remaining_hp=80, max_hp=110, prize_value=1,
        energy_count=1, minimum_attack_energy_count=1, damage_counters=30,
    )
    munk_target["public_state"]["self"]["bench"].append(_marnie_slot(
        150, 151, "CSV8C_094", remaining_hp=80, max_hp=110, prize_value=1,
        energy_count=1, minimum_attack_energy_count=1, damage_counters=30,
    ))
    munk_target["public_state"]["opponent"]["active"] = [_marnie_slot(
        900, 901, "CSV9.5C_006", remaining_hp=260, max_hp=270, prize_value=2,
        energy_count=3, minimum_attack_energy_count=3,
    )]
    munk_target["public_state"]["opponent"]["bench"] = [
        _marnie_slot(910, 911, "CSV8C_028", remaining_hp=100, max_hp=210, prize_value=2),
        _marnie_slot(920, 921, "CSV8C_028", remaining_hp=70, max_hp=210, prize_value=1),
    ]
    munk_target["options"] = [
        _competitive_option(0, "effect_target", source_uid="CSV8C_094", target_uid="CSV8C_028",
                            target_entity_serial=910, target_remaining_hp=100, target_prize_value=2),
        _competitive_option(1, "effect_target", source_uid="CSV8C_094", target_uid="CSV8C_028",
                            target_entity_serial=920, target_remaining_hp=70, target_prize_value=1),
    ]
    add("munkidori-concentrates-easy-ko-before-ready-heal", munk_target, [1],
        matched_rule_id="munkidori.target-concentrated-public-ko")
    munk_target_reordered = copy.deepcopy(munk_target)
    munk_target_reordered["options"].reverse()
    for index, option in enumerate(munk_target_reordered["options"]): option["index"] = index
    add("munkidori-concentrates-easy-ko-before-ready-heal-reordered", munk_target_reordered, [0],
        matched_rule_id="munkidori.target-concentrated-public-ko")
    munk_heal_unready = copy.deepcopy(munk_target)
    munk_heal_unready["public_state"]["opponent"]["active"][0].update({
        "attached_energy_count": 2,
        "attached_energy_uids": ["CSVE1C_DAR", "CSVE1C_DAR"],
        "attack_ready": False,
        "energy_debt": 1,
    })
    add("munkidori-unready-heal-flips-to-two-prize", munk_heal_unready, [0],
        matched_rule_id="munkidori.target-concentrated-public-ko")

    ability = _marnie_scenario_frame()
    ability["options"] = [
        _competitive_option(0, "use_ability", source_uid="CSV8C_094", source_entity_serial=130,
                            ability_index=0),
        _competitive_option(1, "attack", source_uid="CSV10C_148", source_entity_serial=100,
                            source_serial=101, attack_index=0),
    ]
    add("munkidori-before-shadow-bullet", ability, [0], matched_rule_id="munkidori.adrena-brain")

    target = _marnie_scenario_frame("damage_target")
    target["options"] = [
        _competitive_option(0, "damage_target", target_uid="CSV8C_028", target_entity_serial=900,
                            target_remaining_hp=210, target_prize_value=2),
        _competitive_option(1, "damage_target", target_uid="CSV8C_028", target_entity_serial=910,
                            target_remaining_hp=210, target_prize_value=2),
    ]
    target["public_state"]["opponent"]["active"][0]["remaining_hp"] = 20
    add("munkidori-exact-immediate-ko", target, [0], matched_rule_id="damage.best-transfer-target")
    target_reordered = copy.deepcopy(target)
    target_reordered["options"].reverse()
    for index, option in enumerate(target_reordered["options"]): option["index"] = index
    add("munkidori-target-semantic-reorder", target_reordered, [1], matched_rule_id="damage.best-transfer-target")

    attack = _marnie_scenario_frame()
    attack["options"] = [
        _competitive_option(0, "attack", source_uid="CSV10C_148", source_serial=101,
                            source_entity_serial=100, attack_index=0),
        _competitive_option(1, "end_turn"),
    ]
    add("shadow-bullet-180", attack, [0], matched_rule_id="attack.shadow-bullet")
    band = copy.deepcopy(attack)
    band["public_state"]["self"]["active"][0]["attached_tool_uid"] = "CSV1C_117"
    band["public_state"]["opponent"]["prizes_remaining"] = 2
    add("defiance-band-210-two-prize", band, [0], matched_rule_id="attack.defiance-210-two-prize")

    crustle = _marnie_scenario_frame()
    crustle["public_state"]["opponent"]["active"] = [
        _marnie_slot(
            930, 931, "CSV10C_010", remaining_hp=140, max_hp=150, prize_value=1,
            energy_count=3, minimum_attack_energy_count=3,
        )
    ]
    crustle["options"] = [
        _competitive_option(
            0, "attack", source_uid="CSV10C_148", source_serial=101,
            source_entity_serial=100, attack_index=0, projected_damage=0,
        ),
        _competitive_option(1, "play_trainer", card_uid="CSVH1aC_023"),
        _competitive_option(2, "end_turn"),
    ]
    add("crustle-zero-damage-defers-to-boss", crustle, [1],
        matched_rule_id="main.boss-only-with-attacker")
    crustle_reordered = copy.deepcopy(crustle)
    crustle_reordered["options"] = [
        crustle_reordered["options"][2], crustle_reordered["options"][0],
        crustle_reordered["options"][1],
    ]
    for index, option in enumerate(crustle_reordered["options"]):
        option["index"] = index
    add("crustle-zero-damage-defers-to-boss-reordered", crustle_reordered, [2],
        matched_rule_id="main.boss-only-with-attacker")
    crustle_stop = copy.deepcopy(crustle)
    crustle_stop["options"] = [crustle_stop["options"][0], crustle_stop["options"][2]]
    for index, option in enumerate(crustle_stop["options"]):
        option["index"] = index
    add("crustle-zero-damage-stops", crustle_stop, [1],
        matched_rule_id="attack.reject-zero-active-damage",
        selected_source="deterministic_fallback")
    crustle_positive = copy.deepcopy(crustle_stop)
    crustle_positive["options"][0]["projected_damage"] = 180
    add("crustle-positive-damage-flips-to-attack", crustle_positive, [0],
        matched_rule_id="attack.shadow-bullet")

    split = _marnie_scenario_frame("attack_target")
    split["options"] = [
        _competitive_option(0, "attack_target", target_uid="CSV8C_028", target_entity_serial=910,
                            target_remaining_hp=210, target_prize_value=2),
        _competitive_option(1, "attack_target", target_uid="CSV10C_052", target_entity_serial=920,
                            target_remaining_hp=120, target_prize_value=1),
    ]
    split["public_state"]["opponent"]["bench"].append(
        _marnie_slot(920, 921, "CSV10C_052", remaining_hp=120, max_hp=120, prize_value=1)
    )
    add("shadow-bullet-bench-30-next-two-prize", split, [0], matched_rule_id="damage.shadow-bullet-bench-target")

    exact_gust = _marnie_scenario_frame()
    exact_gust["public_state"]["opponent"]["active"] = [_marnie_slot(
        900, 901, "CSV9.5C_006", remaining_hp=260, max_hp=270, prize_value=2,
        energy_count=3, minimum_attack_energy_count=3,
    )]
    exact_gust["public_state"]["opponent"]["bench"] = [_marnie_slot(
        910, 911, "CSV8C_028", remaining_hp=210, max_hp=210, prize_value=2,
    )]
    exact_gust["public_state"]["opponent"]["prizes_remaining"] = 1
    exact_gust["public_state"]["self"]["active"][0]["attached_tool_uid"] = "CSV1C_117"
    exact_gust["options"] = [
        _competitive_option(0, "attack", source_uid="CSV10C_148", source_serial=101,
                            source_entity_serial=100, attack_index=0, projected_damage=210),
        _competitive_option(1, "play_trainer", card_uid="CSV6C_114"),
        _competitive_option(2, "play_trainer", card_uid="CSVH1aC_023"),
        _competitive_option(3, "end_turn"),
    ]
    add("turn14-counter-catcher-exact-two-prize", exact_gust, [1],
        matched_rule_id="main.counter-catcher-exact-two-prize")

    devolution = _marnie_scenario_frame()
    devolution["public_state"]["self"]["hand"] = [{"serial": 50, "local_card_uid": "CSV5C_120"}]
    devolution["public_state"]["opponent"]["active"][0]["remaining_hp"] = 20
    devolution["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV5C_120"),
        _competitive_option(1, "end_turn"),
    ]
    add("devolution-public-lethal", devolution, [0], matched_rule_id="main.tm-devolution-public-finish")

    send = _marnie_scenario_frame("send_out")
    send["options"] = [
        _competitive_option(0, "send_out", target_uid="CSV10C_148", target_entity_serial=140,
                            target_prize_value=2, target_energy_debt=0, target_attack_ready=True),
        _competitive_option(1, "send_out", target_uid="CSV8C_094", target_entity_serial=130,
                            target_prize_value=1, target_energy_debt=0, target_attack_ready=True),
    ]
    add("handoff-ready-grimmsnarl", send, [0], matched_rule_id="handoff.ready-grimmsnarl")
    bridge = copy.deepcopy(send)
    bridge["public_state"]["opponent"]["prizes_remaining"] = 2
    bridge["options"][0].update({"target_energy_debt": 2, "target_attack_ready": False})
    add("handoff-single-prize-bridge", bridge, [1], matched_rule_id="handoff.single-prize-bridge")
    near = copy.deepcopy(send)
    near["options"][0].update({"target_energy_debt": 1, "target_attack_ready": False})
    add("handoff-near-ready-before-terminal", near, [0], matched_rule_id="handoff.near-ready-grimmsnarl")

    terminal = copy.deepcopy(ability)
    add("base-terminal-protection", terminal, [1], terminal=[1], selected_source="terminal")
    mandatory = copy.deepcopy(ability)
    add("base-mandatory-protection", mandatory, [1], mandatory=[1], selected_source="mandatory")
    hard = copy.deepcopy(ability)
    hard["options"][1] = _competitive_option(1, "end_turn")
    add("base-hard-tier-protection", hard, [1], tiers=[{"index": 0, "tier": [1]}, {"index": 1, "tier": [0]}],
        selected_source="deterministic_fallback")
    veto = copy.deepcopy(ability)
    veto["options"][1] = _competitive_option(1, "end_turn")
    add("base-veto-protection", veto, [1], vetoed=[0], selected_source="deterministic_fallback")

    low_deck = _marnie_scenario_frame()
    low_deck["public_state"]["self"]["deck_count"] = 4
    low_deck["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV1C_121"),
        _competitive_option(1, "end_turn"),
    ]
    add("low-deck-stop-research", low_deck, [1], matched_rule_id="main.stop-low-deck-filter",
        selected_source="deterministic_fallback")
    low_deck_flip = copy.deepcopy(low_deck)
    low_deck_flip["public_state"]["self"]["deck_count"] = 12
    low_deck_flip["public_state"]["self"]["active"][0].update({
        "attached_energy_count": 0, "attached_energy_uids": [], "energy_debt": 2, "attack_ready": False,
    })
    add("research-development-above-reserve", low_deck_flip, [0], matched_rule_id="main.research-development")

    seat = copy.deepcopy(attack)
    seat["seat"] = 1
    add("transaction-seat-isolation", seat, [0], matched_rule_id="attack.shadow-bullet")
    healed = copy.deepcopy(target)
    healed["public_state"]["opponent"]["active"][0]["remaining_hp"] = 210
    add("transaction-target-healed-replans", healed, [0], matched_rule_id="damage.best-transfer-target")
    target_left = copy.deepcopy(attack)
    target_left["public_state"]["opponent"]["active"] = []
    target_left["options"] = [_competitive_option(0, "end_turn")]
    add("transaction-target-left-aborts", target_left, [0], selected_source="deterministic_fallback")
    deadline = copy.deepcopy(attack)
    deadline["public_state"]["turn_number"] = 11
    add("transaction-deadline-rebind", deadline, [0], matched_rule_id="attack.shadow-bullet")

    write_json(workspace / "scenario-suite.json", {
        "document_type": "ptcg_strategy_forge_scenario_suite_v1",
        "schema_version": 1,
        "cases": cases,
    })
    return {"case_count": len(cases), "suite_path": str(workspace / "scenario-suite.json")}


def _generate_ogerpon_competitive_scenarios(workspace: Path) -> dict[str, object]:
    scenario_root = workspace / "scenarios"
    cases: list[dict[str, object]] = []

    def add(
        scenario_id: str,
        frame: dict[str, object],
        expected: list[int],
        *,
        matched_rule_id: str,
        selected_source: str | None = None,
        mandatory: list[int] | None = None,
        terminal: list[int] | None = None,
        tiers: list[dict[str, object]] | None = None,
        vetoed: list[int] | None = None,
    ) -> None:
        path = f"{len(cases) + 1:02d}-{scenario_id}.json"
        write_json(scenario_root / path, {
            "document_type": "ptcg_strategy_forge_competitive_scenario_v2",
            "schema_version": 2,
            "scenario_id": scenario_id,
            "frame": frame,
            "base_authority": {
                "mandatory_indexes": list(mandatory or []),
                "terminal_indexes": list(terminal or []),
                "base_hard_tiers": list(tiers or [{"index": index, "tier": [0]} for index in range(len(frame["options"]))]),
                "base_vetoed_indexes": list(vetoed or []),
            },
            "expected_selected_indexes": expected,
        })
        cases.append({
            "id": scenario_id,
            "path": f"scenarios/{path}",
            "expect": {
                "status": "passed",
                "selected_indexes": expected,
                "matched_rule_id": matched_rule_id,
                "selected_source": selected_source or (
                    "terminal" if terminal else ("mandatory" if mandatory else "adapter_proposal")
                ),
            },
        })

    ability = _competitive_option(0, "use_ability", source_uid="CSV8C_028", source_serial=10, ability_index=0)
    attack = _competitive_option(1, "attack", source_uid="CSV8C_028", source_serial=10, attack_index=0, projected_damage=150)
    end = _competitive_option(2, "end_turn")
    positive = _ogerpon_scenario_frame()
    positive["options"] = [ability, attack, end]
    add("ogerpon-teal-dance-before-attack", positive, [0], matched_rule_id="ogerpon.teal-dance")

    reordered = _ogerpon_scenario_frame()
    reordered["source"]["window_id"] = "C" * 64
    reordered["options"] = [
        _competitive_option(0, "end_turn"),
        _competitive_option(1, "attack", source_uid="CSV8C_028", source_serial=10, attack_index=0, projected_damage=150),
        _competitive_option(2, "use_ability", source_uid="CSV8C_028", source_serial=10, ability_index=0),
    ]
    add("ogerpon-teal-dance-semantic-reorder", reordered, [2], matched_rule_id="ogerpon.teal-dance")

    low_deck = copy.deepcopy(positive)
    low_deck["source"]["window_id"] = "B" * 64
    low_deck["public_state"]["self"]["deck_count"] = 3
    add(
        "ogerpon-conserve-deck-before-attack",
        low_deck,
        [1],
        matched_rule_id="ogerpon.attack",
    )

    low_deck_reordered = copy.deepcopy(low_deck)
    low_deck_reordered["source"]["window_id"] = "D" * 64
    low_deck_reordered["options"] = [
        _competitive_option(0, "attack", source_uid="CSV8C_028", source_serial=10,
                            attack_index=0, projected_damage=150),
        _competitive_option(1, "end_turn"),
        _competitive_option(2, "use_ability", source_uid="CSV8C_028", source_serial=10,
                            ability_index=0),
    ]
    add(
        "ogerpon-conserve-deck-before-attack-reordered",
        low_deck_reordered,
        [0],
        matched_rule_id="ogerpon.attack",
    )

    safe_deck_boundary = copy.deepcopy(positive)
    safe_deck_boundary["source"]["window_id"] = "E" * 64
    safe_deck_boundary["public_state"]["self"]["deck_count"] = 5
    add(
        "ogerpon-teal-dance-above-deck-reserve",
        safe_deck_boundary,
        [0],
        matched_rule_id="ogerpon.teal-dance",
    )

    funded = _ogerpon_scenario_frame()
    funded_dwebble = _competitive_slot(12, "CSV10C_009", remaining_hp=70, prize_value=1, energy_count=2, minimum_attack_energy_count=1)
    funded["public_state"]["self"]["bench"] = [funded_dwebble]
    funded["options"] = [
        _competitive_option(0, "evolve", card_uid="CSV10C_010", target_uid="CSV10C_009", target_serial=12,
                            target_attached_energy_count=2, target_attached_energy_uids=["CSVE1C_GRA", "CSVE1C_GRA"],
                            target_minimum_attack_energy_count=1, target_attack_ready=True, target_energy_debt=0),
        _competitive_option(1, "end_turn"),
    ]
    add("crustle-funded-evolution", funded, [0], matched_rule_id="crustle.evolve-funded")

    blocked = _ogerpon_scenario_frame()
    blocked["public_state"]["self"]["bench"] = [
        _competitive_slot(12, "CSV10C_009", remaining_hp=70, prize_value=1, energy_count=0, minimum_attack_energy_count=1)
    ]
    blocked["options"] = [
        _competitive_option(0, "evolve", card_uid="CSV10C_010", target_uid="CSV10C_009", target_serial=12,
                            target_attached_energy_count=0, target_attached_energy_uids=[], target_minimum_attack_energy_count=1,
                            target_attack_ready=False, target_energy_debt=1),
        _competitive_option(1, "end_turn"),
    ]
    add(
        "crustle-underfunded-evolution-guard",
        blocked,
        [1],
        matched_rule_id="crustle.block-underfunded-bench-evolution",
        selected_source="deterministic_fallback",
    )

    search = _ogerpon_scenario_frame("search")
    search["source"]["window_id"] = "D" * 64
    search["select_semantics"].update({"min_count": 0, "max_count": 2, "select_type_raw": 1, "select_context_raw": 7})
    search["options"] = [
        _competitive_option(0, "search", card_uid="CSV8C_028"),
        _competitive_option(1, "search", card_uid="CSV10C_009"),
        _competitive_option(2, "search", card_uid="CSVE1C_GRA"),
        _competitive_option(3, "search", card_uid="CSV10C_206"),
    ]
    for option in search["options"]:
        option["source_uid"] = "CSV8C_182"
    add("bug-catching-set-exact-two", search, [2, 0], matched_rule_id="search.bug-set-grass")

    potion = _ogerpon_scenario_frame("effect_target")
    potion["source"]["window_id"] = "E" * 64
    potion["public_state"]["self"]["active"][0]["remaining_hp"] = 100
    potion["options"] = [
        _competitive_option(0, "effect_target", source_uid="CSV10C_189", target_uid="CSV8C_028", target_serial=10,
                            target_remaining_hp=100, target_prize_value=2, target_attached_energy_count=3,
                            target_attached_energy_uids=["CSVE1C_GRA"] * 3, target_minimum_attack_energy_count=3,
                            target_attack_ready=True, target_energy_debt=0),
        _competitive_option(1, "effect_target", source_uid="CSV10C_189", target_uid="CSV10C_009", target_serial=12,
                            target_remaining_hp=70, target_prize_value=1, target_attached_energy_count=0,
                            target_attached_energy_uids=[], target_minimum_attack_energy_count=1,
                            target_attack_ready=False, target_energy_debt=1),
    ]
    add("hyper-potion-damaged-target", potion, [0], matched_rule_id="hyper-potion.target-ogerpon")

    handoff = _ogerpon_scenario_frame("send_out")
    handoff["source"]["window_id"] = "F" * 64
    handoff["public_state"]["self"]["active"] = []
    handoff["public_state"]["self"]["bench"] = [
        _competitive_slot(13, "CSV10C_010", remaining_hp=150, prize_value=1, energy_count=3, minimum_attack_energy_count=3),
        _competitive_slot(11, "CSV8C_028", remaining_hp=210, prize_value=2, energy_count=3, minimum_attack_energy_count=3),
    ]
    handoff["public_state"]["opponent"]["active"][0]["prize_value"] = 2
    handoff["options"] = [
        _competitive_option(0, "send_out", target_uid="CSV10C_010", target_serial=13, target_remaining_hp=150,
                            target_prize_value=1, target_attached_energy_count=3, target_attached_energy_uids=["CSVE1C_GRA"] * 3,
                            target_minimum_attack_energy_count=3, target_attack_ready=True, target_energy_debt=0),
        _competitive_option(1, "send_out", target_uid="CSV8C_028", target_serial=11, target_remaining_hp=210,
                            target_prize_value=2, target_attached_energy_count=3, target_attached_energy_uids=["CSVE1C_GRA"] * 3,
                            target_minimum_attack_energy_count=3, target_attack_ready=True, target_energy_debt=0),
    ]
    add("handoff-ready-crustle-vs-two-prize", handoff, [0], matched_rule_id="handoff.ready-crustle-vs-two-prize")

    bridge = _ogerpon_scenario_frame("send_out")
    bridge["source"]["window_id"] = "1" * 64
    bridge["public_state"]["self"]["active"] = []
    bridge["public_state"]["self"]["bench"] = [
        _competitive_slot(14, "CSV10C_052", remaining_hp=120, prize_value=1, energy_count=0, minimum_attack_energy_count=3),
        _competitive_slot(12, "CSV10C_009", remaining_hp=70, prize_value=1, energy_count=0, minimum_attack_energy_count=1),
    ]
    bridge["public_state"]["opponent"]["prizes_remaining"] = 2
    bridge["options"] = [
        _competitive_option(0, "send_out", target_uid="CSV10C_052", target_serial=14, target_remaining_hp=120,
                            target_prize_value=1, target_attached_energy_count=0, target_attached_energy_uids=[],
                            target_minimum_attack_energy_count=3, target_attack_ready=False, target_energy_debt=3),
        _competitive_option(1, "send_out", target_uid="CSV10C_009", target_serial=12, target_remaining_hp=70,
                            target_prize_value=1, target_attached_energy_count=0, target_attached_energy_uids=[],
                            target_minimum_attack_energy_count=1, target_attack_ready=False, target_energy_debt=1),
    ]
    add("handoff-articuno-certified-bridge", bridge, [0], matched_rule_id="handoff.articuno-certified-bridge")

    terminal = _ogerpon_scenario_frame()
    terminal["source"]["window_id"] = "2" * 64
    terminal["public_state"]["self"]["prizes_remaining"] = 2
    terminal["options"] = [copy.deepcopy(ability), copy.deepcopy(attack)]
    terminal["options"][1]["projected_knockout"] = True
    add("base-terminal-precedence", terminal, [1], matched_rule_id="attack.final-prize-ko", terminal=[1])

    veto = _ogerpon_scenario_frame()
    veto["source"]["window_id"] = "3" * 64
    veto["options"] = [copy.deepcopy(ability), copy.deepcopy(attack)]
    add("base-veto-blocks-adapter", veto, [1], matched_rule_id="ogerpon.attack", vetoed=[0])

    early_ascension = _ogerpon_scenario_frame()
    early_ascension["source"]["window_id"] = "4" * 64
    early_ascension["public_state"]["turn_number"] = 3
    early_ascension["public_state"]["self"]["active"] = [
        _competitive_slot(10, "CSV10C_009", remaining_hp=70, prize_value=1, energy_count=1,
                          minimum_attack_energy_count=1)
    ]
    early_ascension["public_state"]["self"]["bench"] = []
    early_ascension["options"] = [
        _competitive_option(0, "attack", source_uid="CSV10C_009", source_serial=10,
                            attack_index=0, projected_damage=0, requires_interaction=True),
        _competitive_option(1, "end_turn"),
    ]
    add("early-dwebble-ascension-without-ogerpon", early_ascension, [0], matched_rule_id="dwebble.ascension")

    early_ascension_reordered = copy.deepcopy(early_ascension)
    early_ascension_reordered["source"]["window_id"] = "5" * 64
    early_ascension_reordered["options"] = [
        _competitive_option(0, "end_turn"),
        _competitive_option(1, "attack", source_uid="CSV10C_009", source_serial=10,
                            attack_index=0, projected_damage=0, requires_interaction=True),
    ]
    add(
        "early-dwebble-ascension-without-ogerpon-reordered",
        early_ascension_reordered,
        [1],
        matched_rule_id="dwebble.ascension",
    )

    unsafe_switch = _ogerpon_scenario_frame()
    unsafe_switch["source"]["window_id"] = "6" * 64
    unsafe_switch["public_state"]["self"]["active"] = [
        _competitive_slot(13, "CSV10C_010", remaining_hp=130, prize_value=1, energy_count=2,
                          minimum_attack_energy_count=3)
    ]
    unsafe_switch["public_state"]["self"]["bench"] = [
        _competitive_slot(11, "CSV8C_028", remaining_hp=210, prize_value=2, energy_count=0,
                          minimum_attack_energy_count=3)
    ]
    unsafe_switch["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSVH1aC_008", requires_interaction=True),
        _competitive_option(1, "end_turn"),
    ]
    add(
        "energy-switch-hold-before-ready-donor",
        unsafe_switch,
        [1],
        matched_rule_id="main.block-energy-switch-before-ready-donor",
        selected_source="deterministic_fallback",
    )

    safe_switch = copy.deepcopy(unsafe_switch)
    safe_switch["source"]["window_id"] = "7" * 64
    safe_switch["public_state"]["self"]["bench"] = [
        _competitive_slot(11, "CSV8C_028", remaining_hp=210, prize_value=2, energy_count=4,
                          minimum_attack_energy_count=3)
    ]
    add(
        "energy-switch-play-with-overfunded-ready-donor",
        safe_switch,
        [0],
        matched_rule_id="main.energy-switch-for-crustle-debt",
    )

    switch_source = _ogerpon_scenario_frame("assignment_source")
    switch_source["source"]["window_id"] = "8" * 64
    switch_source["public_state"]["self"]["active"] = safe_switch["public_state"]["self"]["active"]
    switch_source["public_state"]["self"]["bench"] = safe_switch["public_state"]["self"]["bench"]
    switch_source["select_semantics"].update({
        "min_count": 1, "max_count": 1, "select_type_raw": 2, "select_context_raw": 28,
    })
    switch_source["options"] = [
        _competitive_option(
            0, "assignment_source", card_uid="CSVE1C_GRA", source_uid="CSVH1aC_008", source_serial=50,
            target_uid="CSV10C_010", target_serial=13, target_remaining_hp=130, target_prize_value=1,
            target_attached_energy_count=2, target_attached_energy_uids=["CSVE1C_GRA"] * 2,
            target_minimum_attack_energy_count=3, target_attack_ready=False, target_energy_debt=1,
            option_type_raw=5,
        ),
        _competitive_option(
            1, "assignment_source", card_uid="CSVE1C_GRA", source_uid="CSVH1aC_008", source_serial=50,
            target_uid="CSV8C_028", target_serial=11, target_remaining_hp=210, target_prize_value=2,
            target_attached_energy_count=4, target_attached_energy_uids=["CSVE1C_GRA"] * 4,
            target_minimum_attack_energy_count=3, target_attack_ready=True, target_energy_debt=0,
            option_type_raw=5,
        ),
    ]
    add(
        "energy-switch-source-overfunded-ogerpon",
        switch_source,
        [1],
        matched_rule_id="energy-switch.source-overfunded-ogerpon",
    )

    switch_source_reordered = copy.deepcopy(switch_source)
    switch_source_reordered["source"]["window_id"] = "9" * 64
    switch_source_reordered["options"] = [
        copy.deepcopy(switch_source["options"][1]),
        copy.deepcopy(switch_source["options"][0]),
    ]
    for index, option in enumerate(switch_source_reordered["options"]):
        option["index"] = index
    add(
        "energy-switch-source-overfunded-ogerpon-reordered",
        switch_source_reordered,
        [0],
        matched_rule_id="energy-switch.source-overfunded-ogerpon",
    )

    switch_target = _ogerpon_scenario_frame("assignment_target")
    switch_target["source"]["window_id"] = "A" * 64
    switch_target["public_state"]["self"]["active"] = safe_switch["public_state"]["self"]["active"]
    switch_target["public_state"]["self"]["bench"] = safe_switch["public_state"]["self"]["bench"]
    switch_target["select_semantics"].update({
        "min_count": 1, "max_count": 1, "select_type_raw": 1, "select_context_raw": 22,
    })
    switch_target["options"] = [
        _competitive_option(
            0, "assignment_target", card_uid="CSV8C_028", source_uid="CSVH1aC_008", source_serial=50,
            target_uid="CSV8C_028", target_serial=11, target_remaining_hp=210, target_prize_value=2,
            target_attached_energy_count=3, target_attached_energy_uids=["CSVE1C_GRA"] * 3,
            target_minimum_attack_energy_count=3, target_attack_ready=True, target_energy_debt=0,
        ),
        _competitive_option(
            1, "assignment_target", card_uid="CSV10C_010", source_uid="CSVH1aC_008", source_serial=50,
            target_uid="CSV10C_010", target_serial=13, target_remaining_hp=130, target_prize_value=1,
            target_attached_energy_count=2, target_attached_energy_uids=["CSVE1C_GRA"] * 2,
            target_minimum_attack_energy_count=3, target_attack_ready=False, target_energy_debt=1,
        ),
    ]
    add(
        "energy-switch-target-crustle-debt",
        switch_target,
        [1],
        matched_rule_id="energy-switch.target-crustle",
    )

    switch_target_reordered = copy.deepcopy(switch_target)
    switch_target_reordered["source"]["window_id"] = "0" * 64
    switch_target_reordered["options"] = [
        copy.deepcopy(switch_target["options"][1]),
        copy.deepcopy(switch_target["options"][0]),
    ]
    for index, option in enumerate(switch_target_reordered["options"]):
        option["index"] = index
    add(
        "energy-switch-target-crustle-debt-reordered",
        switch_target_reordered,
        [0],
        matched_rule_id="energy-switch.target-crustle",
    )

    supporter_development = _ogerpon_scenario_frame()
    supporter_development["source"]["window_id"] = "2" * 64
    supporter_development["public_state"]["turn_number"] = 6
    supporter_development["public_state"]["self"]["hand"] = [
        {"serial": 30 + index, "local_card_uid": uid}
        for index, uid in enumerate([
            "CSV3C_123", "CSV10C_206", "CSV10C_010",
            "CSVE1C_GRA", "CSVE1C_GRA", "CSV7C_187",
        ])
    ]
    supporter_development["public_state"]["self"]["active"] = [
        _competitive_slot(10, "CSV8C_028", remaining_hp=210, prize_value=2,
                          energy_count=0, minimum_attack_energy_count=3)
    ]
    supporter_development["public_state"]["self"]["bench"] = [
        _competitive_slot(11, "CSV10C_009", remaining_hp=70, prize_value=1,
                          energy_count=0, minimum_attack_energy_count=1)
    ]
    supporter_development["public_state"]["self"]["prizes_remaining"] = 5
    supporter_development["public_state"]["self"]["turn"]["manual_attachment_available"] = False
    supporter_development["public_state"]["opponent"]["hand_count"] = 8
    supporter_development["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV3C_123"),
        _competitive_option(1, "play_trainer", card_uid="CSV10C_206"),
        _competitive_option(2, "evolve", card_uid="CSV10C_010", target_uid="CSV10C_009",
                            target_serial=11, target_attached_energy_count=0,
                            target_attached_energy_uids=[], target_minimum_attack_energy_count=1,
                            target_attack_ready=False, target_energy_debt=1),
        _competitive_option(3, "end_turn"),
    ]
    add(
        "supporter-development-iono-hand-six",
        supporter_development,
        [0],
        matched_rule_id="main.iono-self-brick-reset",
    )

    iono_before_low_yield_item = copy.deepcopy(supporter_development)
    iono_before_low_yield_item["source"]["window_id"] = "D" * 64
    iono_before_low_yield_item["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV3C_123"),
        _competitive_option(1, "play_trainer", card_uid="CSV9C_181", requires_interaction=True),
        _competitive_option(2, "end_turn"),
    ]
    add(
        "supporter-self-brick-iono-before-low-yield-item",
        iono_before_low_yield_item,
        [0],
        matched_rule_id="main.iono-self-brick-reset",
    )

    judge_clock = copy.deepcopy(supporter_development)
    judge_clock["source"]["window_id"] = "3" * 64
    judge_clock["public_state"]["turn_number"] = 4
    judge_clock["public_state"]["self"]["prizes_remaining"] = 6
    judge_clock["public_state"]["opponent"]["active"] = [
        _competitive_slot(20, "CSV8C_028", remaining_hp=210, prize_value=2,
                          energy_count=3, minimum_attack_energy_count=3)
    ]
    judge_clock["public_state"]["opponent"]["prizes_remaining"] = 4
    judge_clock["options"] = [
        _competitive_option(0, "end_turn"),
        _competitive_option(1, "play_trainer", card_uid="CSV10C_206"),
        copy.deepcopy(supporter_development["options"][2]),
        _competitive_option(3, "play_trainer", card_uid="CSV10C_219"),
    ]
    add(
        "supporter-judge-prize-clock",
        judge_clock,
        [1],
        matched_rule_id="main.judge-early-prize-disruption",
    )

    judge_clock_reordered = copy.deepcopy(judge_clock)
    judge_clock_reordered["source"]["window_id"] = "4" * 64
    judge_clock_reordered["options"] = [
        copy.deepcopy(judge_clock["options"][1]),
        copy.deepcopy(judge_clock["options"][0]),
        copy.deepcopy(judge_clock["options"][2]),
        copy.deepcopy(judge_clock["options"][3]),
    ]
    for index, option in enumerate(judge_clock_reordered["options"]):
        option["index"] = index
    add(
        "supporter-judge-prize-clock-reordered",
        judge_clock_reordered,
        [0],
        matched_rule_id="main.judge-early-prize-disruption",
    )

    judge_clock_safe = copy.deepcopy(judge_clock)
    judge_clock_safe["source"]["window_id"] = "5" * 64
    judge_clock_safe["public_state"]["self"]["prizes_remaining"] = 4
    add(
        "supporter-judge-no-tempo-deficit-hold",
        judge_clock_safe,
        [0],
        matched_rule_id="crustle.block-underfunded-bench-evolution",
        selected_source="deterministic_fallback",
    )

    late_iono = _ogerpon_scenario_frame()
    late_iono["source"]["window_id"] = "E" * 64
    late_iono["public_state"]["turn_number"] = 8
    late_iono["public_state"]["self"]["prizes_remaining"] = 4
    late_iono["public_state"]["opponent"]["prizes_remaining"] = 2
    late_iono["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV3C_123"),
        _competitive_option(1, "play_trainer", card_uid="CSV10C_206"),
        _competitive_option(2, "end_turn"),
    ]
    add(
        "supporter-late-iono-prize-lock",
        late_iono,
        [0],
        matched_rule_id="main.iono-late-prize-lock",
    )

    late_iono_reordered = copy.deepcopy(late_iono)
    late_iono_reordered["source"]["window_id"] = "F" * 64
    late_iono_reordered["options"] = [
        copy.deepcopy(late_iono["options"][2]),
        copy.deepcopy(late_iono["options"][1]),
        copy.deepcopy(late_iono["options"][0]),
    ]
    for index, option in enumerate(late_iono_reordered["options"]):
        option["index"] = index
    add(
        "supporter-late-iono-prize-lock-reordered",
        late_iono_reordered,
        [2],
        matched_rule_id="main.iono-late-prize-lock",
    )

    late_judge_hold = copy.deepcopy(late_iono)
    late_judge_hold["source"]["window_id"] = "7" * 64
    late_judge_hold["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV10C_206"),
        _competitive_option(1, "end_turn"),
    ]
    add(
        "supporter-late-judge-hold",
        late_judge_hold,
        [1],
        matched_rule_id="main.avoid-judge-late-game",
        selected_source="deterministic_fallback",
    )

    late_iono_low_deck = copy.deepcopy(late_iono)
    late_iono_low_deck["source"]["window_id"] = "8" * 64
    late_iono_low_deck["public_state"]["self"]["deck_count"] = 6
    late_iono_low_deck["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSV3C_123"),
        _competitive_option(1, "end_turn"),
    ]
    add(
        "supporter-late-iono-low-deck-hold",
        late_iono_low_deck,
        [1],
        matched_rule_id="main.avoid-iono-low-deck",
        selected_source="deterministic_fallback",
    )

    supporter_over_hold = copy.deepcopy(unsafe_switch)
    supporter_over_hold["source"]["window_id"] = "6" * 64
    supporter_over_hold["public_state"]["self"]["hand"] = [
        {"serial": 40 + index, "local_card_uid": uid}
        for index, uid in enumerate([
            "CSV10C_206", "CSV10C_010", "CSVE1C_GRA",
            "CSVE1C_GRA", "CSV7C_187", "CSV10C_219",
        ])
    ]
    supporter_over_hold["public_state"]["opponent"]["hand_count"] = 8
    supporter_over_hold["public_state"]["turn_number"] = 5
    supporter_over_hold["public_state"]["self"]["prizes_remaining"] = 6
    supporter_over_hold["public_state"]["opponent"]["prizes_remaining"] = 4
    supporter_over_hold["options"] = [
        _competitive_option(0, "play_trainer", card_uid="CSVH1aC_008", requires_interaction=True),
        _competitive_option(1, "play_trainer", card_uid="CSV10C_206"),
        _competitive_option(2, "end_turn"),
    ]
    add(
        "supporter-beats-energy-switch-hold",
        supporter_over_hold,
        [1],
        matched_rule_id="main.judge-early-prize-disruption",
    )

    write_json(workspace / "scenario-suite.json", {
        "document_type": "ptcg_strategy_forge_scenario_suite_v1",
        "schema_version": 1,
        "cases": cases,
    })
    return {"case_count": len(cases), "suite_path": str(workspace / "scenario-suite.json")}


def _blueprint(spec: dict[str, Any], package_id: str) -> str:
    rows = "\n".join(
        f"| {rule['rule_id']} | {rule['goal_stage']} | 当前公开窗口 predicate | option 当前语义目标 | mandatory / terminal / hard tier / veto |"
        for rule in spec["rules"]
    )
    competitive_v2 = bool(spec.get("competitive_v2", False))
    runtime_status = "Competitive IR v2 开发包" if competitive_v2 else "restricted IR v1 开发包"
    completion_status = (
        "SCENARIO COMPLETE / GODOT ENGINE PENDING" if competitive_v2 else "COMPLETE"
    )
    migration = "" if not competitive_v2 else """
## 0. Kaggle 迁移身份与保留合同

- 冻结来源：`ptcgabc_ogerpon_v523a_handoff_20260812`。
- 原 `main.py` SHA256：`d6580b1a00f7609dee68053acb67f8de3d68bea440a90774677fa25b74313207`。
- 原 `deck.csv` SHA256：`66b339a7ef8178dc0095c4369b685acb33a2d6e4fc16b452bb6fb4a5ff048b37`。
- 原模型 SHA256：`d0e72d029d7ab9fd90537622d9d2a5139b7822bd23f049dede9d594b6cc677d3`。
- Kaggle archive SHA256：`e7eea5a7e6f753b62757151f5647e85a9ed99b83f196c98c6a2ca45d01a465cc`。
- Kaggle submission `55435118`：公开 33-22（60.0%）；这是来源证据，不是 Godot 胜率声明。
- 迁移重点保护 `crustle evolve-before-funding`、三能量上限、非终局不无证据离开岩殿居蟹，以及 `Articuno` 只作带退出路径的单奖桥。

旧 Python Graph 和 `blind_turn_model.json` 不进入数据包；只把能够由公开帧证明、能在每次新窗口重绑定的语义编译进 Competitive IR v2。
"""
    if spec.get("competitive_builder") == "marnies_gift_box":
        migration = """
## 0. 构筑来源、映射与公共能力

- 唯一构筑来源：宁波赛事第 5 名，赛事 `3475`，牌组 `646600`。
- 原始响应 SHA-256：`C9E224BB3DC17730A4552B6AA57D2567B46E61AC15A43D4A112B1B741823E49F`。
- 来源 `CSV7C_057` 雪童子按名称、HP、属性、退费、进化关系与招式效果核验后映射为当前 Godot `CSV9.5C_043`；该映射不复用 `800018501`。
- 包必须声明 `public_damage_plan_v1` 与 `semantic_transaction_v1`。Host 只接受由当前卡表与标准效果实现生成的 capability ID，不接受卡名、脚本名或包自报基础伤害。
- 固定对手归档：`dev.beralee.v18.ogerpon-crustle-v523a@1.0.0`，SHA-256 `9531F683F2AB9E0138D8054D3E3813D7378F9F6E5F7F8CAF9C428C3FCAFF8D9F`。

## 0.1 伤害公式与奖赏图

- 长毛巨魔：前场 `180`，后场 `30`；奖赏落后且逆境头带生效时前场 `210`。
- 每只雪妖女在回合间只对有特性的公开目标增加 1 个伤害指示物；愿增猿每次最多移动 3 个已有公开指示物。
- 候选按攻击窗口数、奖赏、剩余债务、溢伤、响应风险、稳定公共 Pokémon 实体序号排序。
- 首选奖赏图为 `2+2+2`；无法连续攻击时比较一奖桥和未就绪双奖暴露，而不是只看当前分数。

## 0.2 跨回合事务状态机

| 事务 | 开始 | 继续 | 完成 | 立即中止 |
|---|---|---|---|---|
| `ogerpon-two-prize-conversion` | 最优公开目标值 2 奖 | 目标仍在且伤害债务 > 0 | 债务为 0/目标离场取奖 | 超时、终局、目标失效或不再占优 |
| `backup-grimmsnarl-ready` | 备用长毛巨魔仍缺 1–2 恶能量 | 重观察后能量债务仍存在 | 双恶就绪 | 超时、离场、终局或路线不合法 |
| `devolution-finish` | 手中退化 TM 且公开铺伤满足阈值 | 当前窗口仍有合法退化/目标步骤 | 退化后公开致死 | 治疗、进化栈变化、超时或目标离场 |

日志只保留事务 ID、阶段、稳定公共目标序号、剩余公开债务和己方截止回合；不保留旧索引、旧分数、合法性证明或引擎引用。
"""
    if spec.get("competitive_builder") == "ethans_typhlosion":
        migration = """
## 0. 18.0 构筑来源与语义地板

- 唯一构筑来源：Limitless 列表 `18880`，Godot 牌组 `800018880`。
- PtcgDAP 原始牌组 JSON SHA-256：`BCEA0ACBFA56F928961053725F8442E00A45BF474C131FE593C43E64FF6FF49F`。
- 精确 60 张、26 个 `godot_local_card_uid_v1` printing；核心为 4-4-3 阿响进化线、2-2-2 大比鸟线、4 张阿响的冒险与 5 张基本火能量。
- 参考的内置公开语义来自 `v18cpg_800018880_ethans_typhlosion`：先完成进化与信息引擎，确定性击倒优先，低牌库停止无收益信息动作。
- 本包不复制 GDScript 策略或引擎对象，只编译当前 Competitive v2 公共 frame 可证明的 current-window 意图。

## 0.1 对阵玛丽礼盒的首轮假设

- 以单奖火暴兽连续攻击对抗长毛巨魔/大比鸟等多奖目标，优先把 2 张冒险送入公开弃牌区形成一火 160 阈值。
- 重力山只在公开二阶目标的 HP 阈值实际改善击倒路线时使用；豪华斗篷的额外奖赏风险作为一奖桥风险处理。
- 雪妖女铺伤与愿增猿移动伤害使暴露多个未完成进化根有代价，因此每轮只保留能在下一个攻击窗口转化的备战债务。
"""
    return f"""# {spec['strategy_name']} 策略思考蓝图

> 牌组：{spec['deck_name']}
> 包身份：`{package_id}`
> 状态：{completion_status}（{runtime_status}）

{migration}

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

这部分不是“已运行”声明；不能由当前公开合同证明的分支保持 Base 回退，且不得伪造为策略已执行。

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
    competitive_builder = spec.get("competitive_builder")
    if competitive_builder == "marnies_gift_box":
        adapter = _marnie_gift_box_competitive_adapter(package_id)
    elif competitive_builder == "ethans_typhlosion":
        from .ethans_typhlosion import build_adapter

        adapter = build_adapter(package_id, str(manifest.get("package_version", "0.1.0")))
    elif bool(spec.get("competitive_v2", False)):
        adapter = _ogerpon_competitive_adapter(package_id)
    else:
        adapter = {
            "adapter_id": package_id,
            "adapter_version": 1,
            "rules": spec["rules"],
            "schema_version": 1,
        }
    write_json(package_root / "policy/adapter.json", adapter)
    if spec.get("competitive_builder") == "marnies_gift_box":
        compatibility = manifest.setdefault("compatibility", {})
        compatibility["required_capabilities"] = [
            "public_damage_plan_v1",
            "semantic_transaction_v1",
        ]
        write_json(package_root / "strategy_package.json", manifest)
    write_json(package_root / "policy/policy_ir.json", _policy_ir(package_id, list(adapter["rules"])))
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
    if competitive_builder == "marnies_gift_box":
        scenario_report = _generate_marnie_gift_box_scenarios(workspace)
    elif competitive_builder == "ethans_typhlosion":
        from .ethans_typhlosion import generate_scenarios

        scenario_report = generate_scenarios(workspace)
    elif bool(spec.get("competitive_v2", False)):
        scenario_report = _generate_ogerpon_competitive_scenarios(workspace)
    else:
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
