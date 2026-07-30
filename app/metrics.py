CALCULATIONS = {
    "per_game": "Per game",
    "total": "Total",
    "per_36": "Per 36 minutes",
    "per_100": "Per 100 possessions",
    "weighted": "Weighted percentage",
    "game_average": "Average game value",
    "minute_weighted": "Minute-weighted average",
    "possession_weighted": "Possession-weighted average",
}

SCOPES = {
    "window": "Best rolling window",
    "season": "Full season",
}

METRICS = {}


def add_count(
    metric_id,
    label,
    unit,
    category,
    calculations=None,
    per_game_unit=None,
    expression=None,
):
    calculations = calculations or [
        "per_game",
        "total",
        "per_36",
        "per_100",
    ]

    METRICS[metric_id] = {
        "label": label,
        "unit": unit,
        "category": category,
        "kind": "count",
        "column": metric_id,
        "expression": expression or metric_id,
        "calculations": calculations,
        "default_calculation": calculations[0],
        "per_game_unit": per_game_unit,
        "scale": 1.0,
        "default_direction": "high",
    }


def add_ratio(
    metric_id,
    label,
    unit,
    category,
    column,
    numerator,
    denominator,
    scale=100.0,
):
    METRICS[metric_id] = {
        "label": label,
        "unit": unit,
        "category": category,
        "kind": "ratio",
        "column": column,
        "numerator": numerator,
        "denominator": denominator,
        "calculations": ["weighted", "game_average"],
        "default_calculation": "weighted",
        "scale": scale,
        "default_direction": "high",
    }


def add_average(
    metric_id,
    label,
    unit,
    category,
    scale=1.0,
    expression=None,
    calculations=None,
    direction="high",
):
    calculations = calculations or [
        "game_average",
        "minute_weighted",
        "possession_weighted",
    ]

    METRICS[metric_id] = {
        "label": label,
        "unit": unit,
        "category": category,
        "kind": "average",
        "column": metric_id,
        "expression": expression or metric_id,
        "calculations": calculations,
        "default_calculation": calculations[0],
        "scale": scale,
        "default_direction": direction,
    }


add_count(
    "games_played",
    "Games played",
    "GP",
    "Availability",
    ["total"],
    expression="1.0",
)

add_count(
    "wins",
    "Wins",
    "W",
    "Availability",
    ["total"],
    expression="CASE WHEN win THEN 1.0 ELSE 0.0 END",
)

add_count(
    "losses",
    "Losses",
    "L",
    "Availability",
    ["total"],
    expression="CASE WHEN win THEN 0.0 ELSE 1.0 END",
)

add_count(
    "starts",
    "Games started",
    "GS",
    "Availability",
    ["total"],
    expression="CASE WHEN started THEN 1.0 ELSE 0.0 END",
)

add_average(
    "win_percentage",
    "Win percentage",
    "WIN%",
    "Availability",
    scale=100.0,
    expression="CASE WHEN win THEN 1.0 ELSE 0.0 END",
    calculations=["game_average"],
)

add_average(
    "start_percentage",
    "Start percentage",
    "START%",
    "Availability",
    scale=100.0,
    expression="CASE WHEN started THEN 1.0 ELSE 0.0 END",
    calculations=["game_average"],
)

count_metrics = [
    ("minutes", "Minutes", "MIN", "Playing time", ["per_game", "total"], "MPG"),
    ("pts", "Points", "PTS", "Traditional", None, "PPG"),
    ("reb", "Rebounds", "REB", "Traditional", None, "RPG"),
    ("ast", "Assists", "AST", "Traditional", None, "APG"),
    ("stl", "Steals", "STL", "Traditional", None, "STL/G"),
    ("blk", "Blocks", "BLK", "Traditional", None, "BLK/G"),
    ("tov", "Turnovers", "TOV", "Traditional", None, "TOV/G"),
    ("pf", "Personal fouls", "PF", "Traditional", None, "PF/G"),
    ("plus_minus", "Plus-minus", "+/-", "Traditional", None, "+/-/G"),
    ("fgm", "Field goals made", "FGM", "Shooting volume", None, "FGM/G"),
    ("fga", "Field goals attempted", "FGA", "Shooting volume", None, "FGA/G"),
    ("fg3m", "Three-pointers made", "3PM", "Shooting volume", None, "3PM/G"),
    ("fg3a", "Three-pointers attempted", "3PA", "Shooting volume", None, "3PA/G"),
    ("ftm", "Free throws made", "FTM", "Shooting volume", None, "FTM/G"),
    ("fta", "Free throws attempted", "FTA", "Shooting volume", None, "FTA/G"),
    ("oreb", "Offensive rebounds", "OREB", "Rebounding", None, "OREB/G"),
    ("dreb", "Defensive rebounds", "DREB", "Rebounding", None, "DREB/G"),
    ("blocks_against", "Shots blocked against", "BA", "Advanced counts", None, "BA/G"),
    ("fouls_against", "Fouls drawn", "FD", "Advanced counts", None, "FD/G"),
    (
        "possessions",
        "Possessions",
        "POSS",
        "Advanced counts",
        ["per_game", "total"],
        "POSS/G",
    ),
    (
        "points_off_turnovers",
        "Points off turnovers",
        "PTS OFF TO",
        "Scoring context",
        None,
        "PTS OFF TO/G",
    ),
    (
        "points_second_chance",
        "Second-chance points",
        "2ND PTS",
        "Scoring context",
        None,
        "2ND PTS/G",
    ),
    (
        "points_fast_break",
        "Fast-break points",
        "FB PTS",
        "Scoring context",
        None,
        "FB PTS/G",
    ),
    (
        "points_in_paint",
        "Points in the paint",
        "PAINT PTS",
        "Scoring context",
        None,
        "PAINT PTS/G",
    ),
    (
        "opponent_points_off_turnovers",
        "Opponent points off turnovers",
        "OPP PTS OFF TO",
        "Opponent context",
        None,
        "OPP PTS OFF TO/G",
    ),
    (
        "opponent_points_second_chance",
        "Opponent second-chance points",
        "OPP 2ND PTS",
        "Opponent context",
        None,
        "OPP 2ND PTS/G",
    ),
    (
        "opponent_points_fast_break",
        "Opponent fast-break points",
        "OPP FB PTS",
        "Opponent context",
        None,
        "OPP FB PTS/G",
    ),
    (
        "opponent_points_in_paint",
        "Opponent points in the paint",
        "OPP PAINT PTS",
        "Opponent context",
        None,
        "OPP PAINT PTS/G",
    ),
    (
        "double_double",
        "Double-doubles",
        "DD",
        "Milestones",
        ["per_game", "total"],
        "DD/G",
    ),
    (
        "triple_double",
        "Triple-doubles",
        "TD",
        "Milestones",
        ["per_game", "total"],
        "TD/G",
    ),
]

for (
    metric_id,
    label,
    unit,
    category,
    calculations,
    per_game_unit,
) in count_metrics:
    add_count(
        metric_id,
        label,
        unit,
        category,
        calculations,
        per_game_unit,
    )

add_ratio(
    "field_goal_percentage",
    "Field-goal percentage",
    "FG%",
    "Shooting efficiency",
    "fg_pct",
    "fgm",
    "fga",
)

add_ratio(
    "three_point_percentage",
    "Three-point percentage",
    "3P%",
    "Shooting efficiency",
    "fg3_pct",
    "fg3m",
    "fg3a",
)

add_ratio(
    "free_throw_percentage",
    "Free-throw percentage",
    "FT%",
    "Shooting efficiency",
    "ft_pct",
    "ftm",
    "fta",
)

add_ratio(
    "effective_field_goal_percentage",
    "Effective field-goal percentage",
    "eFG%",
    "Shooting efficiency",
    "effective_field_goal_percentage",
    "(fgm + 0.5 * fg3m)",
    "fga",
)

add_ratio(
    "true_shooting_percentage",
    "True shooting percentage",
    "TS%",
    "Shooting efficiency",
    "true_shooting_percentage",
    "pts",
    "(2.0 * (fga + 0.44 * fta))",
)

add_ratio(
    "assist_to_turnover_ratio",
    "Assist-to-turnover ratio",
    "AST/TO",
    "Playmaking",
    "assist_to_turnover_ratio",
    "ast",
    "tov",
    scale=1.0,
)

average_metrics = [
    (
        "estimated_offensive_rating",
        "Estimated offensive rating",
        "Est. ORtg",
        "Ratings",
        1.0,
        "high",
    ),
    ("offensive_rating", "Offensive rating", "ORtg", "Ratings", 1.0, "high"),
    (
        "sp_work_offensive_rating",
        "Secondary offensive rating",
        "ORtg",
        "Ratings",
        1.0,
        "high",
    ),
    (
        "estimated_defensive_rating",
        "Estimated defensive rating",
        "Est. DRtg",
        "Ratings",
        1.0,
        "low",
    ),
    ("defensive_rating", "Defensive rating", "DRtg", "Ratings", 1.0, "low"),
    (
        "sp_work_defensive_rating",
        "Secondary defensive rating",
        "DRtg",
        "Ratings",
        1.0,
        "low",
    ),
    (
        "estimated_net_rating",
        "Estimated net rating",
        "Est. Net",
        "Ratings",
        1.0,
        "high",
    ),
    ("net_rating", "Net rating", "Net", "Ratings", 1.0, "high"),
    (
        "sp_work_net_rating",
        "Secondary net rating",
        "Net",
        "Ratings",
        1.0,
        "high",
    ),
    (
        "assist_percentage",
        "Assist percentage",
        "AST%",
        "Playmaking",
        100.0,
        "high",
    ),
    ("assist_ratio", "Assist ratio", "AST ratio", "Playmaking", 1.0, "high"),
    (
        "offensive_rebound_percentage",
        "Offensive rebound percentage",
        "OREB%",
        "Rebounding rates",
        100.0,
        "high",
    ),
    (
        "defensive_rebound_percentage",
        "Defensive rebound percentage",
        "DREB%",
        "Rebounding rates",
        100.0,
        "high",
    ),
    (
        "rebound_percentage",
        "Rebound percentage",
        "REB%",
        "Rebounding rates",
        100.0,
        "high",
    ),
    (
        "team_turnover_percentage",
        "Turnover percentage",
        "TOV%",
        "Possession rates",
        100.0,
        "low",
    ),
    (
        "estimated_turnover_percentage",
        "Estimated turnover percentage",
        "Est. TOV%",
        "Possession rates",
        100.0,
        "low",
    ),
    (
        "usage_percentage",
        "Usage percentage",
        "USG%",
        "Possession rates",
        100.0,
        "high",
    ),
    (
        "estimated_usage_percentage",
        "Estimated usage percentage",
        "Est. USG%",
        "Possession rates",
        100.0,
        "high",
    ),
    ("estimated_pace", "Estimated pace", "Est. Pace", "Pace", 1.0, "high"),
    ("pace", "Pace", "Pace", "Pace", 1.0, "high"),
    ("pace_per_40", "Pace per 40", "Pace/40", "Pace", 1.0, "high"),
    ("sp_work_pace", "Secondary pace", "Pace", "Pace", 1.0, "high"),
    (
        "player_impact_estimate",
        "Player impact estimate",
        "PIE",
        "Impact",
        100.0,
        "high",
    ),
]

share_metrics = [
    ("percent_field_goal_attempts_2_point", "Two-point attempt share"),
    ("percent_field_goal_attempts_3_point", "Three-point attempt share"),
    ("percent_points_2_point", "Points from two-pointers"),
    ("percent_points_2_point_mid_range", "Points from mid-range shots"),
    ("percent_points_3_point", "Points from three-pointers"),
    ("percent_points_fast_break", "Points from fast breaks"),
    ("percent_points_free_throw", "Points from free throws"),
    ("percent_points_off_turnovers", "Points off turnovers share"),
    ("percent_points_in_paint", "Points in the paint share"),
    ("percent_assisted_2_point_made", "Assisted two-point make share"),
    ("percent_unassisted_2_point_made", "Unassisted two-point make share"),
    ("percent_assisted_3_point_made", "Assisted three-point make share"),
    ("percent_unassisted_3_point_made", "Unassisted three-point make share"),
    ("percent_assisted_field_goals_made", "Assisted field-goal make share"),
    (
        "percent_unassisted_field_goals_made",
        "Unassisted field-goal make share",
    ),
    ("percent_team_field_goals_made", "Team field goals made share"),
    ("percent_team_field_goals_attempted", "Team field-goal attempt share"),
    ("percent_team_three_pointers_made", "Team three-pointers made share"),
    (
        "percent_team_three_pointers_attempted",
        "Team three-point attempt share",
    ),
    ("percent_team_free_throws_made", "Team free throws made share"),
    ("percent_team_free_throws_attempted", "Team free-throw attempt share"),
    ("percent_team_offensive_rebounds", "Team offensive rebound share"),
    ("percent_team_defensive_rebounds", "Team defensive rebound share"),
    ("percent_team_rebounds", "Team rebound share"),
    ("percent_team_assists", "Team assist share"),
    ("percent_team_turnovers", "Team turnover share"),
    ("percent_team_steals", "Team steal share"),
    ("percent_team_blocks", "Team block share"),
    ("percent_team_blocks_against", "Team shots blocked against share"),
    ("percent_team_fouls_personal", "Team personal foul share"),
    ("percent_team_fouls_drawn", "Team fouls drawn share"),
    ("percent_team_points", "Team scoring share"),
]

for (
    metric_id,
    label,
    unit,
    category,
    scale,
    direction,
) in average_metrics:
    add_average(
        metric_id,
        label,
        unit,
        category,
        scale=scale,
        direction=direction,
    )

for metric_id, label in share_metrics:
    add_average(
        metric_id,
        label,
        "%",
        "Scoring and team shares",
        scale=100.0,
    )

LEGACY_METRICS = {
    "points": ("pts", "per_game"),
    "rebounds": ("reb", "per_game"),
    "assists": ("ast", "per_game"),
    "points_per_36": ("pts", "per_36"),
}
