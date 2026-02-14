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
    # Keep blank opponents as "(Unknown)" for display
    if "opponent" in df.columns:
        df["opponent"] = df["opponent"].fillna("").astype(str).str.strip()
        df.loc[df["opponent"] == "", "opponent"] = "(Unknown)"
    else:
        df["opponent"] = "(Unknown)"
    return df


st.title("Cricket Performance Dashboard")

bat = load_csv(None, "battinginnings.csv")
bowl = load_csv(None, "bowlinginnings.csv")

# -----------------------------
# Basic cleaning
# -----------------------------
bat["runs"] = to_float(bat.get("runs"))
bat["balls"] = to_float(bat.get("balls"))
bat["fours"] = to_float(bat.get("fours"))
bat["sixes"] = to_float(bat.get("sixes"))
bat["sr"] = to_float(bat.get("sr"))

if "batpos" in bat.columns:
    bat["batpos"] = pd.to_numeric(bat["batpos"], errors="coerce")

# Normalize player names to lowercase for consistent deduplication
if "playername" in bat.columns:
    bat["playername"] = bat["playername"].str.lower()

bowl["runsconceded"] = to_float(bowl.get("runsconceded"))
bowl["wickets"] = to_float(bowl.get("wickets"))
bowl["econ"] = to_float(bowl.get("econ"))
bowl["balls_bowled"] = overs_to_balls(bowl.get("overs", pd.Series(dtype=str)))

# Normalize bowler names to lowercase for consistent deduplication
if "bowlername" in bowl.columns:
    bowl["bowlername"] = bowl["bowlername"].str.lower()

bat = norm_opp(bat)
bowl = norm_opp(bowl)

# Navigation
tab_player, tab_comparison, tab_team = st.tabs(["Player Performance", "Player Comparison", "Team Trends"])

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

    # Batting summary (top)
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

        st.markdown("#### Match-wise Batting Summary")
        sort_cols = ["tournamentkey", "opponent", "inningsno"]
        if "batpos" in bat_f.columns:
            sort_cols.append("batpos")
        if "matchid" in bat_f.columns:
            sort_cols.append("matchid")  # for stable ordering only (hidden)

        bat_detail = bat_f.sort_values(sort_cols)

        cols = ["tournament", "opponent", "inningsno", "battingteam"]
        if "batpos" in bat_detail.columns:
            cols.append("batpos")
        cols += ["runs", "balls", "sr", "fours", "sixes", "howout"]

        st.dataframe(bat_detail[cols], use_container_width=True)

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

        st.markdown("#### Match-wise Bowling Summary")
        sort_cols = ["tournamentkey", "opponent", "inningsno"]
        if "matchid" in bowl_f.columns:
            sort_cols.append("matchid")  # stable ordering only (hidden)
        bowl_detail = bowl_f.sort_values(sort_cols)

        cols = ["tournament", "opponent", "inningsno", "bowlingteam", "overs", "runsconceded", "wickets", "econ"]
        st.dataframe(bowl_detail[cols], use_container_width=True)

# -------------------------
# Tab 2: Player-wise overall comparison
# -------------------------
with tab_comparison:
    st.subheader("Player-wise Overall Comparison")

    # Option to select all players or specific players
    all_players_list = sorted(set(bat["playername"]).union(set(bowl["bowlername"])))
    
    select_all = st.checkbox("Select all players", value=False)
    if select_all:
        selected_players = all_players_list
    else:
        selected_players = st.multiselect(
            "Select players to compare",
            all_players_list,
            default=[all_players_list[0]] if all_players_list else []
        )

    if not selected_players:
        st.info("Select at least one player to view comparison.")
    else:
        # Batting comparison
        st.markdown("### Batting Comparison")
        bat_comp = bat[bat["playername"].isin(selected_players)].copy()
        if bat_comp.empty:
            st.warning("No batting data for selected players.")
        else:
            bat_summary = bat_comp.groupby("playername", as_index=False).agg(
                inns=("runs", "count"),
                runs=("runs", "sum"),
                balls=("balls", "sum"),
                fours=("fours", "sum"),
                sixes=("sixes", "sum"),
            )
            
            # Calculate average separately
            bat_dismissals = bat_comp.copy()
            bat_dismissals["dismissal"] = (bat_dismissals["howout"].fillna("").str.lower() != "not out").astype(int)
            dismissal_counts = bat_dismissals.groupby("playername")["dismissal"].sum()
            
            bat_summary["avg"] = bat_summary.apply(
                lambda row: (row["runs"] / dismissal_counts.get(row["playername"], 0)) 
                if dismissal_counts.get(row["playername"], 0) > 0 else None,
                axis=1
            ).round(2)
            bat_summary["sr"] = (bat_summary["runs"] * 100 / bat_summary["balls"]).round(2)
            
            bat_summary = bat_summary.sort_values("runs", ascending=False)
            display_cols = ["playername", "inns", "runs", "balls", "avg", "sr", "fours", "sixes"]
            st.dataframe(bat_summary[display_cols], use_container_width=True)

        # Bowling comparison
        st.markdown("### Bowling Comparison")
        bowl_comp = bowl[bowl["bowlername"].isin(selected_players)].copy()
        if bowl_comp.empty:
            st.warning("No bowling data for selected players.")
        else:
            bowl_summary = bowl_comp.groupby("bowlername", as_index=False).agg(
                spells=("runsconceded", "count"),
                runs=("runsconceded", "sum"),
                balls=("balls_bowled", "sum"),
                wickets=("wickets", "sum"),
            )
            # Calculate metrics
            bowl_summary["overs"] = (bowl_summary["balls"] / 6).round(1)
            bowl_summary["econ"] = (bowl_summary["runs"] / (bowl_summary["balls"] / 6)).round(2)
            bowl_summary["avg"] = (bowl_summary["runs"] / bowl_summary["wickets"]).round(2)
            bowl_summary["sr"] = (bowl_summary["balls"] / bowl_summary["wickets"]).round(1)
            
            bowl_summary = bowl_summary.sort_values("wickets", ascending=False)
            display_cols = ["bowlername", "spells", "runs", "overs", "wickets", "avg", "econ", "sr"]
            st.dataframe(bowl_summary[display_cols], use_container_width=True)

# -------------------------
# Tab 3: Team match trends
# -------------------------
with tab_team:
    st.subheader("Team trends")

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
        wm["overs_bowled"] = (wm["balls_bowled"] / 6).round(1)
        wm["economy"] = (wm["runs_conceded"] / wm["overs_bowled"]).round(2)

    # Merge batting and bowling data
    mm = bm.merge(wm, on=["tournamentkey", trend_key], how="outer").sort_values(["tournamentkey", trend_key])
    
    # Add tournament label
    if len(mm) > 0:
        mm = mm.copy()
        mm["tournament"] = mm["tournamentkey"].map(lambda x: tournament_label(x))
    
    # ---- Game-wise comparison table ----
    st.markdown("### Game-wise Summary")
    if len(mm) == 0:
        st.info("No game data found for this filter.")
    else:
        # Determine win/loss based on run rate comparison (SUPREMOS run rate > Opposition run rate)
        mm["opposition_run_rate"] = (mm["runs_conceded"] * 6 / mm["balls_bowled"]).round(2)
        mm["result"] = mm.apply(
            lambda row: "Won" if (pd.notna(row["run_rate"]) and pd.notna(row["opposition_run_rate"]) 
                                   and row["run_rate"] > row["opposition_run_rate"]) else "Lost",
            axis=1
        )
        
        display_cols = [
            "tournament",
            trend_key,
            "runs_scored",
            "wickets_lost",
            "run_rate",
            "runs_conceded",
            "wickets_taken",
            "opposition_run_rate",
            "result",
        ]
        display_cols = [c for c in display_cols if c in mm.columns]
        
        game_table = mm[display_cols].sort_values(["tournament", trend_key])
        st.dataframe(game_table, use_container_width=True)
    
    # ---- Trend analysis ----
    st.markdown("### Trend Analysis")
    if len(mm) == 0:
        st.info("No data for trend analysis.")
    else:
        # Analyze patterns
        total_games = len(mm)
        wins = (mm["result"] == "Won").sum()
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        st.write(f"**Overall Record:** {wins}/{total_games} wins ({win_rate:.1f}%)")
        
        # Pattern 1: Runs scored >= 150
        high_score_games = mm[mm["runs_scored"] >= 150]
        if len(high_score_games) > 0:
            high_score_wins = (high_score_games["result"] == "Won").sum()
            high_score_rate = (high_score_wins / len(high_score_games) * 100)
            st.write(f"• **Runs ≥ 150:** {high_score_wins}/{len(high_score_games)} wins ({high_score_rate:.1f}%)")
        
        # Pattern 2: Runs scored >= 130
        medium_score_games = mm[mm["runs_scored"] >= 130]
        if len(medium_score_games) > 0:
            medium_score_wins = (medium_score_games["result"] == "Won").sum()
            medium_score_rate = (medium_score_wins / len(medium_score_games) * 100)
            st.write(f"• **Runs ≥ 130:** {medium_score_wins}/{len(medium_score_games)} wins ({medium_score_rate:.1f}%)")
        
        # Pattern 3: Run rate >= 10
        high_rr_games = mm[mm["run_rate"] >= 10]
        if len(high_rr_games) > 0:
            high_rr_wins = (high_rr_games["result"] == "Won").sum()
            high_rr_rate = (high_rr_wins / len(high_rr_games) * 100)
            st.write(f"• **Run Rate ≥ 10:** {high_rr_wins}/{len(high_rr_games)} wins ({high_rr_rate:.1f}%)")
        
        # Pattern 4: Wickets lost <= 3
        low_wkts_games = mm[mm["wickets_lost"] <= 3]
        if len(low_wkts_games) > 0:
            low_wkts_wins = (low_wkts_games["result"] == "Won").sum()
            low_wkts_rate = (low_wkts_wins / len(low_wkts_games) * 100)
            st.write(f"• **Wickets Lost ≤ 3:** {low_wkts_wins}/{len(low_wkts_games)} wins ({low_wkts_rate:.1f}%)")
        
        # Pattern 5: Economy <= 7
        low_econ_games = mm[mm["economy"] <= 7]
        if len(low_econ_games) > 0:
            low_econ_wins = (low_econ_games["result"] == "Won").sum()
            low_econ_rate = (low_econ_wins / len(low_econ_games) * 100)
            st.write(f"• **Bowling Economy ≤ 7:** {low_econ_wins}/{len(low_econ_games)} wins ({low_econ_rate:.1f}%)")
