import streamlit as st
import pandas as pd

st.set_page_config(page_title="Cricket Performance Dashboard", layout="wide")

@st.cache_data
def load_csv(uploaded_file, fallback_path: str):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return pd.read_csv(fallback_path)

def to_float(s):
    return pd.to_numeric(s, errors="coerce")

def overs_to_balls(overs_series: pd.Series) -> pd.Series:
    # cricket overs like 3.3 = 3 overs + 3 balls = 21 balls
    x = overs_series.astype(str).str.strip()
    parts = x.str.split(".", n=1, expand=True)
    o = pd.to_numeric(parts[0], errors="coerce").fillna(0)
    b = pd.to_numeric(parts[1], errors="coerce").fillna(0)
    return (o * 6 + b).astype(int)

def pick_team_mask(series: pd.Series, team_query: str) -> pd.Series:
    q = (team_query or "").strip().lower()
    if not q:
        return pd.Series([True] * len(series), index=series.index)
    return series.astype(str).str.lower().str.contains(q, regex=False)

st.title("Cricket Performance Dashboard")

with st.sidebar:
    st.header("Data")
    up_bat = st.file_uploader("Upload battinginnings.csv", type=["csv"], key="bat")
    up_bowl = st.file_uploader("Upload bowlinginnings.csv", type=["csv"], key="bowl")
    st.caption("If you don’t upload, the app will try reading local files in the same folder.")
    st.divider()

bat = load_csv(up_bat, "battinginnings.csv")
bowl = load_csv(up_bowl, "bowlinginnings.csv")

# Basic cleaning
bat["runs"] = to_float(bat.get("runs"))
bat["balls"] = to_float(bat.get("balls"))
bat["fours"] = to_float(bat.get("fours"))
bat["sixes"] = to_float(bat.get("sixes"))
bat["sr"] = to_float(bat.get("sr"))

bowl["runsconceded"] = to_float(bowl.get("runsconceded"))
bowl["wickets"] = to_float(bowl.get("wickets"))
bowl["econ"] = to_float(bowl.get("econ"))
bowl["balls_bowled"] = overs_to_balls(bowl.get("overs", pd.Series(dtype=str)))

# Navigation
tab_player, tab_team = st.tabs(["Player performance", "Team match trends"])

# -------------------------
# Tab 1: Player performance
# -------------------------
with tab_player:
    st.subheader("Player-wise performance")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        tourn = st.multiselect("Tournament", sorted(set(bat["tournamentkey"]).union(set(bowl["tournamentkey"]))), default=[])
    with c2:
        match = st.multiselect("Match", sorted(set(bat["matchid"]).union(set(bowl["matchid"]))), default=[])
    with c3:
        source = st.multiselect("Source", sorted(set(bat["source"]).union(set(bowl["source"]))), default=[])
    with c4:
        player = st.selectbox("Player", ["(All)"] + sorted(set(bat["playername"]).union(set(bowl["bowlername"]))))

    bat_f = bat.copy()
    bowl_f = bowl.copy()

    if tourn:
        bat_f = bat_f[bat_f["tournamentkey"].isin(tourn)]
        bowl_f = bowl_f[bowl_f["tournamentkey"].isin(tourn)]
    if match:
        bat_f = bat_f[bat_f["matchid"].isin(match)]
        bowl_f = bowl_f[bowl_f["matchid"].isin(match)]
    if source:
        bat_f = bat_f[bat_f["source"].isin(source)]
        bowl_f = bowl_f[bowl_f["source"].isin(source)]
    if player != "(All)":
        bat_f = bat_f[bat_f["playername"] == player]
        bowl_f = bowl_f[bowl_f["bowlername"] == player]

    # Consolidated summary
    left, right = st.columns(2)

    with left:
        st.markdown("### Batting summary")
        dismissals = (bat_f["howout"].fillna("").str.lower() != "not out").sum()
        inns = len(bat_f)
        runs = bat_f["runs"].sum(skipna=True)
        balls = bat_f["balls"].sum(skipna=True)
        sr = (runs * 100 / balls) if balls else 0
        avg = (runs / dismissals) if dismissals else None

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Inns", int(inns))
        k2.metric("Runs", int(runs) if pd.notna(runs) else 0)
        k3.metric("Avg", f"{avg:.2f}" if avg is not None else "—")
        k4.metric("SR", f"{sr:.2f}" if balls else "—")
        k5.metric("4s/6s", f"{int(bat_f['fours'].sum(skipna=True))}/{int(bat_f['sixes'].sum(skipna=True))}")

        st.markdown("### Batting (match-wise / tournament-wise)")
        bat_game = bat_f.groupby(["tournamentkey", "matchid", "inningsno", "battingteam", "playername"], as_index=False).agg(
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
        )
        bat_game["sr"] = (bat_game["runs"] * 100 / bat_game["balls"]).round(2)
        st.dataframe(bat_game.sort_values(["tournamentkey", "matchid", "inningsno"]), use_container_width=True)

    with right:
        st.markdown("### Bowling summary")
        inns_b = len(bowl_f)
        overs_balls = bowl_f["balls_bowled"].sum()
        overs_equiv = overs_balls / 6 if overs_balls else 0
        runs_c = bowl_f["runsconceded"].sum(skipna=True)
        wkts = bowl_f["wickets"].sum(skipna=True)
        econ = (runs_c / overs_equiv) if overs_equiv else 0
        avg_b = (runs_c / wkts) if wkts else None
        sr_b = (overs_balls / wkts) if wkts else None

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Spells", int(inns_b))
        k2.metric("Runs", int(runs_c) if pd.notna(runs_c) else 0)
        k3.metric("Wkts", int(wkts) if pd.notna(wkts) else 0)
        k4.metric("Econ", f"{econ:.2f}" if overs_equiv else "—")
        k5.metric("Avg / SR", f"{avg_b:.2f} / {sr_b:.1f}" if (avg_b is not None and sr_b is not None) else "—")

        st.markdown("### Bowling (match-wise / tournament-wise)")
        bowl_game = bowl_f.groupby(["tournamentkey", "matchid", "inningsno", "bowlingteam", "bowlername"], as_index=False).agg(
            balls=("balls_bowled", "sum"),
            runs=("runsconceded", "sum"),
            wkts=("wickets", "sum"),
        )
        bowl_game["overs"] = (bowl_game["balls"] / 6).round(1)
        bowl_game["econ"] = (bowl_game["runs"] / (bowl_game["balls"] / 6)).replace([pd.NA, pd.NaT, float("inf")], 0).round(2)
        st.dataframe(bowl_game.sort_values(["tournamentkey", "matchid", "inningsno"]), use_container_width=True)

    # Leaderboards (all players)
    st.divider()
    st.markdown("### Leaderboards (all players in current filters)")

    lb1, lb2 = st.columns(2)

    with lb1:
        st.markdown("#### Batting leaderboard")
        bat_lb = bat_f.groupby("playername", as_index=False).agg(
            inns=("playername", "count"),
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
            dismissals=("howout", lambda s: (s.fillna("").str.lower() != "not out").sum()),
        )
        bat_lb["avg"] = (bat_lb["runs"] / bat_lb["dismissals"]).round(2)
        bat_lb.loc[bat_lb["dismissals"] == 0, "avg"] = pd.NA
        bat_lb["sr"] = (bat_lb["runs"] * 100 / bat_lb["balls"]).round(2)
        st.dataframe(bat_lb.sort_values(["runs", "sr"], ascending=[False, False]), use_container_width=True)

    with lb2:
        st.markdown("#### Bowling leaderboard")
        bowl_lb = bowl_f.groupby("bowlername", as_index=False).agg(
            spells=("bowlername", "count"),
            balls=("balls_bowled", "sum"),
            runs=("runsconceded", "sum"),
            wkts=("wickets", "sum"),
        )
        bowl_lb["overs"] = (bowl_lb["balls"] / 6).round(1)
        bowl_lb["econ"] = (bowl_lb["runs"] / (bowl_lb["balls"] / 6)).replace([pd.NA, pd.NaT, float("inf")], 0).round(2)
        bowl_lb["avg"] = (bowl_lb["runs"] / bowl_lb["wkts"]).round(2)
        bowl_lb.loc[bowl_lb["wkts"] == 0, "avg"] = pd.NA
        st.dataframe(bowl_lb.sort_values(["wkts", "econ"], ascending=[False, True]), use_container_width=True)

# -------------------------
# Tab 2: Team match trends
# -------------------------
with tab_team:
    st.subheader("Team trends by match")

    team_query = st.text_input("Team name contains (e.g., 'SUPREMOS')", value="SUPREMOS")
    tourn2 = st.multiselect("Tournament filter", sorted(set(bat["tournamentkey"]).union(set(bowl["tournamentkey"]))), default=[])

    bat_t = bat.copy()
    bowl_t = bowl.copy()
    if tourn2:
        bat_t = bat_t[bat_t["tournamentkey"].isin(tourn2)]
        bowl_t = bowl_t[bowl_t["tournamentkey"].isin(tourn2)]

    bat_team = bat_t[pick_team_mask(bat_t["battingteam"], team_query)]
    bowl_team = bowl_t[pick_team_mask(bowl_t["bowlingteam"], team_query)]

    # Batting match trend
    bm = bat_team.groupby(["tournamentkey", "matchid"], as_index=False).agg(
        runs_scored=("runs", "sum"),
        balls_faced=("balls", "sum"),
        wickets_lost=("howout", lambda s: (s.fillna("").str.lower() != "not out").sum()),
    )
    bm["run_rate"] = (bm["runs_scored"] * 6 / bm["balls_faced"]).round(2)

    # Bowling match trend
    wm = bowl_team.groupby(["tournamentkey", "matchid"], as_index=False).agg(
        runs_conceded=("runsconceded", "sum"),
        balls_bowled=("balls_bowled", "sum"),
        wickets_taken=("wickets", "sum"),
    )
    wm["overs_bowled"] = (wm["balls_bowled"] / 6)
    wm["economy"] = (wm["runs_conceded"] / wm["overs_bowled"]).round(2)

    # Merge
    mm = bm.merge(wm, on=["tournamentkey", "matchid"], how="outer")
    mm["nrr_proxy"] = ((mm["runs_scored"] * 6 / mm["balls_faced"]) - (mm["runs_conceded"] / mm["overs_bowled"])).round(2)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Batting trend (match-by-match)")
        st.line_chart(mm.sort_values(["tournamentkey", "matchid"]).set_index(["tournamentkey", "matchid"])[["runs_scored", "wickets_lost", "run_rate"]])
    with c2:
        st.markdown("### Bowling trend (match-by-match)")
        st.line_chart(mm.sort_values(["tournamentkey", "matchid"]).set_index(["tournamentkey", "matchid"])[["runs_conceded", "wickets_taken", "economy"]])

    st.markdown("### Best vs worst matches (table)")
    st.dataframe(mm.sort_values(["nrr_proxy", "runs_scored"], ascending=[False, False]), use_container_width=True)
