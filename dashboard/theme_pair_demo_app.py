"""Public-facing SignalLab demo backed by a self-contained SQLite database."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "demo_data" / "theme_pair_demo.sqlite"
THEMES = {"profit": "盈利能力", "value": "价值", "invest": "投资", "accrual": "应计项目", "quality": "质量", "finance": "融资", "intangible": "无形资产", "liquidity": "流动性"}
THEME_ORDER = tuple(THEMES)
TIMING = {"loading": 2, "candidate": .7, "evaluation": 2, "critic": 2, "freeze": 2, "preliminary": 3, "strict": 3, "backtest": 5}


@st.cache_resource
def connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def pair_key(left: str, right: str) -> str:
    return "_".join(sorted((left, right), key=THEME_ORDER.index))


def pair_bundle(key: str) -> dict:
    db = connection()
    pair = pd.read_sql_query("SELECT * FROM pairs WHERE pair_key = ?", db, params=[key]).iloc[0].to_dict()
    candidates = pd.read_sql_query("SELECT * FROM candidates WHERE pair_key = ? ORDER BY generation, candidate_id", db, params=[key])
    periods = pd.read_sql_query("SELECT * FROM periods WHERE pair_key = ? ORDER BY period_no", db, params=[key])
    return {"pair": pair, "candidates": candidates, "periods": periods}


def state() -> dict:
    if "demo_state" not in st.session_state:
        st.session_state.demo_state = {"key": None, "phase": "idle", "started": None, "generation": 0, "candidate": 0, "history": []}
    return st.session_state.demo_state


def start(key: str) -> None:
    s = state(); history = [item for item in s["history"] if item != key]
    s.update({"key": key, "phase": "loading", "started": time.time(), "generation": 0, "candidate": 0, "history": [key] + history})


def advance(s: dict) -> None:
    if s["phase"] in {"idle", "completed"}: return
    elapsed = time.time() - s["started"]
    if s["phase"] == "loading" and elapsed >= TIMING["loading"]: s.update(phase="generation", started=time.time()); return
    if s["phase"] == "generation":
        if elapsed >= TIMING["candidate"] and s["candidate"] < 5: s["candidate"] += 1; s["started"] = time.time(); return
        if s["candidate"] >= 5 and elapsed >= TIMING["candidate"]:
            s.update(phase="evaluation", started=time.time()); return
    if s["phase"] == "evaluation" and elapsed >= TIMING["evaluation"]: s.update(phase="critic", started=time.time()); return
    if s["phase"] == "critic" and elapsed >= TIMING["critic"]:
        if s["generation"] < 6: s.update(phase="generation", generation=s["generation"] + 1, candidate=0, started=time.time())
        else: s.update(phase="freeze", started=time.time())
        return
    next_phase = {"freeze": "preliminary", "preliminary": "strict", "strict": "backtest", "backtest": "completed"}
    if s["phase"] in next_phase and elapsed >= TIMING[s["phase"]]: s.update(phase=next_phase[s["phase"]], started=time.time())


def candidate_card(row: pd.Series, show_review: bool) -> None:
    label = f"{row['candidate_id']} · {row['name']} · {row['verdict']}"
    with st.expander(label, expanded=show_review):
        left, right = st.columns([1.7, 1])
        with left:
            st.caption("候选公式"); st.code(row.formula, language="text")
            st.write(row.explanation); st.caption(f"预期方向：{row.direction}")
        with right:
            st.metric("覆盖期数", int(row.coverage)); st.metric("验证年化", f"{row.annualized_return:.2%}")
            st.metric("FMB t", f"{row.fmb_t:.2f}"); st.metric("IC / Rank IC", f"{row.ic:.3f} / {row.rank_ic:.3f}")
        if show_review: st.info(row.critic_reason)


def render_sidebar(s: dict) -> None:
    st.sidebar.markdown("## 主题对研究工作台")
    st.sidebar.caption("演示数据库 · 8选2")
    selected = [item for item in THEME_ORDER if st.sidebar.checkbox(THEMES[item], key=f"demo_{item}")]
    key = pair_key(*selected) if len(selected) == 2 else None
    st.sidebar.write(" × ".join(THEMES[item] for item in selected) if selected else "尚未选择")
    if st.sidebar.button("开始研究", type="primary", disabled=key is None): start(key); st.rerun()
    if st.sidebar.button("重新选择"):
        history = s["history"]; s.clear(); s.update({"key": None, "phase": "idle", "started": None, "generation": 0, "candidate": 0, "history": history}); st.rerun()
    st.sidebar.divider(); st.sidebar.markdown("**本次会话已研究**")
    for old_key in s["history"]:
        if st.sidebar.button(pair_bundle(old_key)["pair"]["label"], key=f"demo_history_{old_key}", width="stretch"):
            s.update({"key": old_key, "phase": "completed", "generation": 6, "candidate": 5}); st.rerun()


def render_main(s: dict) -> None:
    if not s["key"]: st.info("请在左侧选择两个主题，然后点击“开始研究”。"); return
    advance(s); bundle = pair_bundle(s["key"]); candidates = bundle["candidates"]
    phase = s["phase"]
    st.progress(1.0 if phase == "completed" else .5, text="进度")
    cols = st.columns(4); cols[0].metric("当前阶段", {"loading": "环境准备中", "generation": "候选提案", "evaluation": "组合评估", "critic": "研究审查", "freeze": "候选确认", "preliminary": "初步检验", "strict": "严格检验", "backtest": "回测结果", "completed": "结果完成"}.get(phase, "处理中")); cols[1].metric("当前世代", f"第{s['generation'] + 1}代 / 7代"); cols[2].metric("当前候选", f"{s['candidate']} / 5"); cols[3].metric("主题对", bundle["pair"]["label"])
    if phase in {"generation", "evaluation", "critic"}:
        st.subheader(f"第{s['generation']}代候选提案")
        rows = candidates[candidates.generation == s["generation"]]
        visible = s["candidate"] if phase == "generation" else 5
        for index, (_, row) in enumerate(rows.iterrows()):
            if index < visible: candidate_card(row, phase == "critic")
        if phase == "generation" and s["candidate"] < 5: st.caption("候选提案正在进入研究流程。")
        if phase == "evaluation": st.info("正在进行机械校验和组合评估。")
        if phase == "critic": st.info("研究审查正在进行。")
    elif phase in {"freeze", "preliminary", "strict", "backtest", "completed"}:
        selected = candidates[candidates.candidate_id == "g004_c04"].iloc[0]
        st.subheader("最终候选已确认"); st.markdown(f"### {selected['candidate_id']} · {selected['name']}"); st.code(selected.formula, language="text"); st.write(selected.explanation)
        if phase in {"backtest", "completed"}:
            st.subheader("验证期回测结果")
            periods = bundle["periods"].copy(); periods["策略净值"] = (1 + periods.base_cost).cumprod(); periods["沪深300净值"] = (1 + periods.benchmark).cumprod()
            table = [{"成本情景": "无成本", "累计收益": f"{(1 + periods.no_cost).prod() - 1:.2%}", "年化收益": f"{(1 + periods.no_cost).prod() ** (4 / 14) - 1:.2%}", "Sharpe": f"{periods.no_cost.mean() / periods.no_cost.std() * 2:.2f}", "有效区间数": 14}, {"成本情景": "基础成本", "累计收益": f"{(1 + periods.base_cost).prod() - 1:.2%}", "年化收益": f"{(1 + periods.base_cost).prod() ** (4 / 14) - 1:.2%}", "Sharpe": f"{periods.base_cost.mean() / periods.base_cost.std() * 2:.2f}", "有效区间数": 14}, {"成本情景": "保守成本", "累计收益": f"{(1 + periods.conservative_cost).prod() - 1:.2%}", "年化收益": f"{(1 + periods.conservative_cost).prod() ** (4 / 14) - 1:.2%}", "Sharpe": f"{periods.conservative_cost.mean() / periods.conservative_cost.std() * 2:.2f}", "有效区间数": 14}]
            st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch"); st.line_chart(periods.set_index("formation_date")[["策略净值", "沪深300净值"]])
    if phase != "completed": st.caption("研究流程正在按阶段推进。")


st.set_page_config(page_title="SignalLab · 主题对研究工作台（演示）", layout="wide")
st.markdown("""<style>.block-container{max-width:1500px;padding-top:1.5rem}.demo-note{color:#0f172a;background:#f0fdfa;border-left:4px solid #0f766e;padding:.8rem 1rem;border-radius:4px}[data-testid="stMetricValue"]{white-space:normal;overflow-wrap:anywhere;font-size:1.25rem}</style>""", unsafe_allow_html=True)
st.title("SignalLab · 主题对研究工作台")
st.markdown('<div class="demo-note">演示数据库模式：用于展示主题对研究流程和页面交互，数据为预置演示数据。</div>', unsafe_allow_html=True)
s = state(); render_sidebar(s)
if hasattr(st, "fragment"):
    @st.fragment(run_every="1s")
    def main_fragment(): render_main(s)
    main_fragment()
else: render_main(s)
