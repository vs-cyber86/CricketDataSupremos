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
    st.subheader("Player performance")

    # Dropdown 1: Player Name
    all_players = sorted(set(bat["playername"]).union(set(bowl["bowlername"])))
    player = st.selectbox("Player Name", ["(Select a player)"] + all_players)

    # Dropdown 2: Tournament
    if player == "(Select a player)":
        tourn_options = sorted(set(bat["tournamentkey"]).union(set(bowl["tournamentkey"])))
    else:
        bt = bat[bat["playername"] == player]
        bw = bowl[bowl["bowlername"] == player]
        tourn_options = sorted(set(bt["tournamentkey"]).union(set(bw["tournamentkey"])))

    tourn_display = [tournament_label(t) for t in tourn_options]
    display_to_key = {tournament_label(t): t for t in tourn_options}
    tourn_choice = st.selectbox("Tournament", ["(All)"] + tourn_display)

    # No data until a player is selected
    if player == "(Select a player)":
        st.info("Select a player to view batting and bowling performance.")
        st.stop()

    # Filter data for selected player
    bat_f = bat[bat["playername"] == player].copy()
    bowl_f = bowl[bowl["bowlername"] == player].copy()

    # Tournament filter (optional)
    if tourn_choice != "(All)":
        tkey = display_to_key[tourn_choice]
        bat_f = bat_f[bat_f["tournamentkey"] == tkey]
        bowl_f = bowl_f[bowl_f["tournamentkey"] == tkey]

    # Add pretty tournament name for display
    if not bat_f.empty:
        bat_f["tournament"] = bat_f["tournamentkey"].map(lambda x: tournament_label(x))
    if not bowl_f.empty:
        bowl_f["tournament"] = bowl_f["tournamentkey"].map(lambda x: tournament_label(x))

    # -------------------
    # Batting summary (top)
    # -------------------
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

        st.markdown("#### Batting: game-wise (tournament-wise included)")
        bat_game = bat_f.groupby(["tournament", "tournamentkey", "matchid", "inningsno", "battingteam"], as_index=False).agg(
            runs=("runs", "sum"),
            balls=("balls", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
        )
        bat_game["sr"] = (bat_game["runs"] * 100 / bat_game["balls"]).round(2)
        bat_game = bat_game.sort_values(["tournamentkey", "matchid", "inningsno"])
        st.dataframe(
            bat_game[["tournament", "matchid", "inningsno", "battingteam", "runs", "balls", "sr", "fours", "sixes"]],
            use_container_width=True,
        )

        st.markdown("#### Batting: innings details")
        bat_detail = bat_f.sort_values(["tournamentkey", "matchid", "inningsno"])
        st.dataframe(
            bat_detail[["tournament", "matchid", "inningsno", "battingteam", "runs", "balls", "sr", "fours", "sixes", "howout"]],
            use_container_width=True,
        )

    # -------------------
    # Bowling summary (below)
    # -------------------
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

        st.markdown("#### Bowling: game-wise (tournament-wise included)")
        bowl_game = bowl_f.groupby(["tournament", "tournamentkey", "matchid", "inningsno", "bowlingteam"], as_index=False).agg(
            balls=("balls_bowled", "sum"),
            runs=("runsconceded", "sum"),
            wkts=("wickets", "sum"),
        )
        bowl_game["overs"] = (bowl_game["balls"] / 6).round(1)
        bowl_game["econ"] = (bowl_game["runs"] / (bowl_game["balls"] / 6)).round(2)
        bowl_game = bowl_game.sort_values(["tournamentkey", "matchid", "inningsno"])
        st.dataframe(
            bowl_game[["tournament", "matchid", "inningsno", "bowlingteam", "overs", "runs", "wkts", "econ"]],
            use_container_width=True,
        )

        st.markdown("#### Bowling: spell details")
        bowl_detail = bowl_f.sort_values(["tournamentkey", "matchid", "inningsno"])
        st.dataframe(
            bowl_detail[["tournament", "matchid", "inningsno", "bowlingteam", "overs", "runsconceded", "wickets", "econ"]],
            use_container_width=True,
        )

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
    if not bm.empty:
        bm["run_rate"] = (bm["runs_scored"] * 6 / bm["balls_faced"]).round(2)

    # Bowling match trend
    wm = bowl_team.groupby(["tournamentkey", "matchid"], as_index=False).agg(
        runs_conceded=("runsconceded", "sum"),
        balls_bowled=("balls_bowled", "sum"),
        wickets_taken=("wickets", "sum"),
    )
    if not wm.empty:
        wm["overs_bowled"] = (wm["balls_bowled"] / 6)
        wm["economy"] = (wm["runs_conceded"] / wm["overs_bowled"]).round(2)

    # Merge
    mm = bm.merge(wm, on=["tournamentkey", "matchid"], how="outer")
    mm = mm.sort_values(["tournamentkey", "matchid"])

    # nrr proxy only if we have the inputs
    if all(c in mm.columns for c in ["runs_scored", "balls_faced", "runs_conceded", "overs_bowled"]):
        mm["nrr_proxy"] = ((mm["runs_scored"] * 6 / mm["balls_faced"]) - (mm["runs_conceded"] / mm["overs_bowled"])).round(2)
    else:
        mm["nrr_proxy"] = pd.NA

    # Charts (safe: show only if columns exist + data present)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Batting trend (match-by-match)")
        bat_cols = ["runs_scored", "wickets_lost", "run_rate"]
        if len(mm) == 0 or any(c not in mm.columns for c in bat_cols):
            st.info("No batting trend data found for this team filter. Try changing 'Team name contains' or tournament filter.")
        else:
            st.line_chart(mm.set_index(["tournamentkey", "matchid"])[bat_cols])

    with c2:
        st.markdown("### Bowling trend (match-by-match)")
        bowl_cols = ["runs_conceded", "wickets_taken", "economy"]
        if len(mm) == 0 or any(c not in mm.columns for c in bowl_cols):
            st.info("No bowling trend data found for this team filter. Try changing 'Team name contains' or tournament filter.")
        else:
            st.line_chart(mm.set_index(["tournamentkey", "matchid"])[bowl_cols])

    st.markdown("### Best vs worst matches (table)")
    if len(mm) == 0:
        st.info("No matches found for this team filter.")
    else:
        show_cols = [c for c in [
            "tournamentkey", "matchid",
            "runs_scored", "wickets_lost", "run_rate",
            "runs_conceded", "wickets_taken", "economy",
            "nrr_proxy"
        ] if c in mm.columns]
        out = mm.copy()
        out["tournament"] = out["tournamentkey"].map(lambda x: tournament_label(x))
        # Put tournament label first
        if "tournament" in out.columns:
            show_cols = ["tournament"] + [c for c in show_cols if c != "tournamentkey"]
        st.dataframe(
            out.sort_values(["nrr_proxy", "runs_scored"], ascending=[False, False])[show_cols],
            use_container_width=True,
        )
