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
tab_player, tab_comparison = st.tabs(["Player Performance", "Player Comparison"])

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

        # Batting position-wise runs chart
        if "batpos" in bat_f.columns and not bat_f["batpos"].isna().all():
            st.markdown("#### Position-wise Runs Analysis")
            
            # Create position categories
            bat_pos_data = bat_f[bat_f["batpos"].notna()].copy()
            bat_pos_data["position_group"] = pd.cut(
                bat_pos_data["batpos"],
                bins=[0, 2, 4, 6, 11],
                labels=["1-2 (Opening)", "3-4 (Middle)", "5-6 (Lower Middle)", "7-11 (Tail)"],
                include_lowest=True
            )
            
            pos_summary = bat_pos_data.groupby("position_group", as_index=False).agg(
                runs=("runs", "sum"),
                inns=("runs", "count")
            )
            
            if not pos_summary.empty:
                pos_summary = pos_summary.sort_values("runs", ascending=False)
                st.bar_chart(pos_summary.set_index("position_group")["runs"])

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
