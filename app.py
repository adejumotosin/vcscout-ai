from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from vcscout.service import get_ranked_startups  # noqa: E402

st.set_page_config(page_title="VCScout AI", page_icon="◈", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; max-width: 1500px;}
      [data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: 14px; border-radius: 14px;}
      .vc-kicker {font-size:.82rem; letter-spacing:.13em; text-transform:uppercase; opacity:.65;}
      .vc-title {font-size:2.55rem; font-weight:750; line-height:1.05; margin:.2rem 0 .5rem 0;}
      .vc-subtitle {font-size:1rem; opacity:.72; max-width:800px;}
      .score-note {font-size:.82rem; opacity:.65;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="vc-kicker">Alternative-data venture sourcing</div>', unsafe_allow_html=True)
st.markdown('<div class="vc-title">VCScout AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="vc-subtitle">Discover unusually fast-moving engineering teams before the fundraising narrative becomes obvious. The current score ranks observable GitHub momentum; it is not a funding probability.</div>',
    unsafe_allow_html=True,
)

try:
    ranked, meta = get_ranked_startups()
except Exception as exc:
    st.error(f"Could not load the live signal feed: {exc}")
    st.stop()

with st.sidebar:
    st.header("Scout filters")
    sector_options = ["All"] + sorted(ranked["sector"].dropna().unique().tolist())
    geography_options = ["All"] + sorted(ranked["geography"].dropna().unique().tolist())
    stage_options = ["All"] + sorted(ranked["stage"].dropna().unique().tolist())
    sector = st.selectbox("Sector", sector_options)
    geography = st.selectbox("Geography", geography_options)
    stage = st.selectbox("Stage", stage_options)
    min_score = st.slider("Minimum VC Scout Score", 0, 100, 50)
    only_positive_velocity = st.toggle("Positive commit acceleration only", value=False)
    st.divider()
    st.caption(f"Source period: {meta.get('period', 'Unknown')}")
    st.caption(f"Source updated: {meta.get('last_updated', 'Unknown')}")
    if st.button("Refresh live data"):
        get_ranked_startups(force_refresh=True)
        st.rerun()

filtered = ranked[ranked["vc_scout_score"] >= min_score].copy()
if sector != "All":
    filtered = filtered[filtered["sector"] == sector]
if geography != "All":
    filtered = filtered[filtered["geography"] == geography]
if stage != "All":
    filtered = filtered[filtered["stage"] == stage]
if only_positive_velocity:
    filtered = filtered[filtered["commit_velocity_change"] > 0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tracked organisations", int(meta.get("total_startups") or len(ranked)))
c2.metric("Visible after filters", len(filtered))
c3.metric("Breakout signals", int((filtered["momentum_flag"] == "Breakout").sum()))
c4.metric("Median scout score", f"{filtered['vc_scout_score'].median():.1f}" if not filtered.empty else "—")

st.subheader("Deal-flow leaderboard")
leader = filtered.head(50).copy()
leader["Rank"] = range(1, len(leader) + 1)
show_cols = [
    "Rank", "name", "vc_scout_score", "momentum_flag", "sector", "stage", "geography",
    "commit_velocity_14d", "commit_velocity_change", "contributor_growth", "new_repos_30d",
    "signal_type", "top_driver",
]
st.dataframe(
    leader[show_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "name": "Startup / org",
        "vc_scout_score": st.column_config.ProgressColumn("VC Scout Score", min_value=0, max_value=100, format="%.1f"),
        "commit_velocity_14d": "Commits / 14d",
        "commit_velocity_change": "Commit Δ %",
        "contributor_growth": "Contributor Δ %",
        "new_repos_30d": "New repos / 30d",
    },
)

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Momentum map")
    if not filtered.empty:
        fig = px.scatter(
            filtered.head(150),
            x="commit_velocity_change",
            y="contributor_growth",
            size="commit_velocity_14d",
            hover_name="name",
            hover_data=["sector", "stage", "vc_scout_score", "signal_type"],
            labels={
                "commit_velocity_change": "14-day commit velocity change (%)",
                "contributor_growth": "Contributor growth (%)",
                "commit_velocity_14d": "Commit velocity",
            },
        )
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Sector heat")
    if not filtered.empty:
        sector_stats = (
            filtered.groupby("sector", as_index=False)
            .agg(
                avg_score=("vc_scout_score", "mean"),
                startups=("name", "nunique"),
                avg_velocity_change=("commit_velocity_change", "mean"),
            )
            .sort_values("avg_score", ascending=False)
        )
        fig2 = px.bar(
            sector_stats.head(12),
            x="avg_score",
            y="sector",
            orientation="h",
            hover_data=["startups", "avg_velocity_change"],
            labels={"avg_score": "Average VC Scout Score", "sector": ""},
        )
        fig2.update_layout(height=520, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig2, use_container_width=True)

st.subheader("Startup deep dive")
if filtered.empty:
    st.info("No startups match the current filters.")
else:
    selected_name = st.selectbox("Select an organisation", filtered["name"].tolist())
    row = filtered[filtered["name"] == selected_name].iloc[0]

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("VC Scout Score", f"{row.vc_scout_score:.1f}/100")
    d2.metric("14d commit velocity", f"{row.commit_velocity_14d:.0f}", f"{row.commit_velocity_change:+.0f}%")
    d3.metric("Contributors", f"{row.contributors:.0f}", f"{row.contributor_growth:+.0f}%")
    d4.metric("New repos / 30d", f"{row.new_repos_30d:.0f}")

    st.markdown(f"**{row['name']}** · {row['sector']} · {row['stage']} · {row['geography']}")
    if row["description"]:
        st.write(row["description"])
    st.write(f"**Signal:** {row['signal_type']}  |  **Top score driver:** {row['top_driver']}  |  **Momentum:** {row['momentum_flag']}")
    if row["risk_flag"] != "None":
        st.warning(row["risk_flag"])
    links = []
    if row.get("github_url"):
        links.append(f"[GitHub]({row['github_url']})")
    if row.get("website_url"):
        links.append(f"[Website]({row['website_url']})")
    if row.get("profile_url"):
        links.append(f"[Source profile]({row['profile_url']})")
    if links:
        st.markdown(" · ".join(links))

st.divider()
st.markdown(
    """
    <div class="score-note">
    VC Scout Score is a transparent sourcing heuristic based on commit acceleration, contributor growth, absolute engineering velocity, repository expansion, team depth and signal type. It should be used to prioritize diligence, not as investment advice or a claim that a financing event will occur.
    </div>
    """,
    unsafe_allow_html=True,
)
