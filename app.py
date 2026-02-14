import streamlit as st
import pandas as pd

st.set_page_config(page_title="Cricket Performance Dashboard", layout="wide")

# -----------------------------
# Tournament display name mapping
# -----------------------------
TOURNAMENT_LABELS = {
    "zootermt20cb3": "Zooter Pink Ball",
    "zooterisdt8": "Zooter ISDT",
    "jfscdpl202526": "JFSC Dad's",
    "clt20s_pdf": "JFSC CLT20",
}


def tournament_label(k: str) -> str:
    k = str(k)
    return TOURNAMENT_LABELS.get(k, k)


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


def norm_opp(df: pd.DataFrame) -> pd.DataFrame:
    if "opponent" in df.columns:
        df["opponent"] = df["opponent"].fillna("").astype(str).str.strip()
        df.loc[df["opponent"] == "", "opponent"] = "(Unknown)"
    else:
        df["opponent"] = "(Unknown)"
    return df


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

if "batpos" in bat.columns:
    bat["batpos"] = pd.to_numeric(bat["batpos"], errors="coerce")

bowl["runsconceded"] = to_float(bowl.get("runsconceded"))
bowl["wickets"] = to_float(bowl.get("wickets"))
bowl["econ"] = to_float(bowl.get("econ"))
bowl["balls_bowled"] = overs_to_balls(bowl.get("overs", pd.Series(dtype=str)))

# Ensure opponent column exists + is clean for display
bat = norm_opp(bat)
bowl = norm_opp(bowl)

# Navigation
tab_player, tab_team = st.tabs(["Player performance", "Team match trends"])

# -------------------------
# Tab 1: Player performance
# -------------------------
with tab_player:
    st.subheader("Player performance")

    # Dropdown 1 - Player Name
    all_players = sorted(set(bat["playername"]).union(set(bowl["bowlername"])))
    player = st.selectbox("Player Name", ["(Select a player)"] + all_players)

    # Dropdown 2 - Tournament (options depend on selected player)
    if player == "(Select a player)":
        tourn_options = sorted(set(bat["tournamentkey"]).union(set(bowl["tournamentkey"])))
    else:
        bt = bat[bat["playername"] == player]
        bw = bowl[bowl["bowlername"] == player]
        tourn_options = sorted(set(bt["tournamentkey"]).union(set(bw["tournamentkey"])))

    tourn_display = [tournament_label(t) for t in tourn_options]
    display_to_key = {tournament_label(t): t for t in tourn_options}
    tourn_choice = st.selectbox("Tournament", ["(All)"] + tourn_display)

    # No data until player is selected
    if player == "(Select a player)":
        st.info("Select a player to view performance.")
        st.stop()

    # Filter data for selected player
    bat_f = bat[bat["playername"] == player].copy()
    bowl_f = bowl[bowl["bowlername"] == player].copy()

    # Apply tournament filter
    if tourn_choice != "(All)":
        tkey = display_to_key[tourn_choice]
        bat_f = bat_f[bat_f["tournamentkey"] == tkey]
        bowl_f = bowl_f[bowl_f["tournamentkey"] == tkey]

    # Add friendly tournament label
    if not bat_f.empty:
        bat_f["tournament"] = bat_f["tournamentkey"].map(lambda x: tournament_label(x))
    if not bowl_f.empty:
        bowl_f["tournament"] = bowl_f["tournamentkey"].map(lambda x: tournament_label(x))

    # Batting summary
    st.markdown("### Batting summary")
    if bat_f.empty:
        st.warning("No batting data for this selection.")
    else:
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

        st.markdown("#### Batting: innings details (Opponent instead of Match ID)")
        sort_cols = ["tournamentkey", "opponent", "inningsno"]
        if "batpos" in bat_f.columns:
            sort_cols.append("batpos")
        if "matchid" in bat_f.columns:
            sort_cols.append("matchid")

        bat_detail = bat_f.sort_values(sort_cols)

        cols = ["tournament", "opponent", "inningsno", "battingteam"]
        if "batpos" in bat_detail.columns:
            cols.append("batpos")
        cols += ["runs", "balls", "sr", "fours", "sixes", "howout"]

        st.dataframe(bat_detail[cols], use_container_width=True)

        st.markdown("#### Batting: opponent-wise (tournament-wise included)")
        group_cols = ["tournament", "tournamentkey", "opponent", "inningsno", "battingteam"]
        bat_game = bat_f.groupby(group_cols, as_index=False).agg(
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
        )
        bat_game["sr"] = (bat_game["runs"] * 100 / bat_game["balls"]).round(2)
        bat_game = bat_game.sort_values(["tournamentkey", "opponent", "inningsno"])

        show_cols = ["tournament", "opponent", "inningsno", "battingteam", "runs", "balls", "sr", "fours", "sixes"]
        st.dataframe(bat_game[show_cols], use_container_width=True)

    # Bowling summary (below)
    st.markdown("### Bowling summary")
    if bowl_f.empty:
        st.warning("No bowling data for this selection.")
    else:
        inns_b = len(bowl_f)
        balls_bowled = bowl_f["balls_bowled"].sum()
        overs_equiv = (balls_bowled / 6) if balls_bowled else 0
        runs_c = bowl_f["runsconceded"].sum(skipna=True)
        wkts = bowl_f["wickets"].sum(skipna=True)

        econ = (runs_c / overs_equiv) if overs_equiv else 0
        avg_b = (runs_c / wkts) if wkts else None
        sr_b = (balls_bowled / wkts) if wkts else None

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Spells", int(inns_b))
        k2.metric("Runs", int(runs_c) if pd.notna(runs_c) else 0)
        k3.metric("Wkts", int(wkts) if pd.notna(wkts) else 0)
        k4.metric("Econ", f"{econ:.2f}" if overs_equiv else "—")
        k5.metric("Avg / SR", f"{avg_b:.2f} / {sr_b:.1f}" if (avg_b is not None and sr_b is not None) else "—")

        st.markdown("#### Bowling: spell details (Opponent instead of Match ID)")
        sort_cols = ["tournamentkey", "opponent", "inningsno"]
        if "matchid" in bowl_f.columns:
            sort_cols.append("matchid")
        bowl_detail = bowl_f.sort_values(sort_cols)

        cols = ["tournament", "opponent", "inningsno", "bowlingteam", "overs", "runsconceded", "wickets", "econ"]
        st.dataframe(bowl_detail[cols], use_container_width=True)

        st.markdown("#### Bowling: opponent-wise (tournament-wise included)")
        group_cols = ["tournament", "tournamentkey", "opponent", "inningsno", "bowlingteam"]
        bowl_game = bowl_f.groupby(group_cols, as_index=False).agg(
            balls=("balls_bowled", "sum"),
            runs=("runsconceded", "sum"),
            wkts=("wickets", "sum"),
        )
        bowl_game["overs"] = (bowl_game["balls"] / 6).round(1)
        bowl_game["econ"] = (bowl_game["runs"] / (bowl_game["balls"] / 6)).round(2)
        bowl_game = bowl_game.sort_values(["tournamentkey", "opponent", "inningsno"])

        show_cols = ["tournament", "opponent", "inningsno", "bowlingteam", "overs", "runs", "wkts", "econ"]
        st.dataframe(bowl_game[show_cols], use_container_width=True)

# -------------------------
# Tab 2: Team match trends
# -------------------------
with tab_team:
    st.subheader("Team trends by match")

    team_query = st.text_input("Team name contains (e.g., 'SUPREMOS')", value="SUPREMOS")

    tourn2 = st.multiselect(
        "Tournament filter",
        sorted(set(bat["tournamentkey"]).union(set(bowl["tournamentkey"]))),
        default=[],
        format_func=tournament_label,
    )

    group_by_opponent = st.checkbox("Group by opponent (if available)", value=True)

    bat_t = bat.copy()
    bowl_t = bowl.copy()

    if tourn2:
        bat_t = bat_t[bat_t["tournamentkey"].isin(tourn2)]
        bowl_t = bowl_t[bowl_t["tournamentkey"].isin(tourn2)]

    bat_team = bat_t[pick_team_mask(bat_t["battingteam"], team_query)]
    bowl_team = bowl_t[pick_team_mask(bowl_t["bowlingteam"], team_query)]

    if group_by_opponent and ("opponent" in bat_team.columns) and ("opponent" in bowl_team.columns):
        trend_key = "opponent"
    else:
        trend_key = "matchid"

    bm = bat_team.groupby(["tournamentkey", trend_key], as_index=False).agg(
        runs_scored=("runs", "sum"),
        balls_faced=("balls", "sum"),
        wickets_lost=("howout", lambda s: (s.fillna("").str.lower() != "not out").sum()),
    )
    if not bm.empty:
        bm["run_rate"] = (bm["runs_scored"] * 6 / bm["balls_faced"]).round(2)

    wm = bowl_team.groupby(["tournamentkey", trend_key], as_index=False).agg(
        runs_conceded=("runsconceded", "sum"),
        balls_bowled=("balls_bowled", "sum"),
        wickets_taken=("wickets", "sum"),
    )
    if not wm.empty:
        wm["overs_bowled"] = (wm["balls_bowled"] / 6)
        wm["economy"] = (wm["runs_conceded"] / wm["overs_bowled"]).round(2)

    mm = bm.merge(wm, on=["tournamentkey", trend_key], how="outer")
    mm = mm.sort_values(["tournamentkey", trend_key])

    if all(c in mm.columns for c in ["runs_scored", "balls_faced", "runs_conceded", "overs_bowled"]):
        mm["nrr_proxy"] = ((mm["runs_scored"] * 6 / mm["balls_faced"]) - (mm["runs_conceded"] / mm["overs_bowled"])).round(2)
    else:
        mm["nrr_proxy"] = pd.NA

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Batting trend")
        bat_cols = ["runs_scored", "wickets_lost", "run_rate"]
        if len(mm) == 0 or any(c not in mm.columns for c in bat_cols):
            st.info("No batting trend data found for this filter.")
        else:
            st.line_chart(mm.set_index(["tournamentkey", trend_key])[bat_cols])

    with c2:
        st.markdown("### Bowling trend")
        bowl_cols = ["runs_conceded", "wickets_taken", "economy"]
        if len(mm) == 0 or any(c not in mm.columns for c in bowl_cols):
            st.info("No bowling trend data found for this filter.")
        else:
            st.line_chart(mm.set_index(["tournamentkey", trend_key])[bowl_cols])

    st.markdown("### Best vs worst (table)")
    if len(mm) == 0:
        st.info("No data found for this filter.")
    else:
        out = mm.copy()
        out["tournament"] = out["tournamentkey"].map(lambda x: tournament_label(x))

        display_cols = [
            "tournament",
            trend_key,
            "runs_scored",
            "wickets_lost",
            "run_rate",
            "runs_conceded",
            "wickets_taken",
            "economy",
            "nrr_proxy",
        ]
        display_cols = [c for c in display_cols if c in out.columns]

        st.dataframe(
            out.sort_values(["nrr_proxy", "runs_scored"], ascending=[False, False])[display_cols],
            use_container_width=True,
        )
