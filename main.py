import nflreadpy as nfl
import polars as pl
from datetime import datetime, timedelta

# 1. Get upcoming matchups
today = datetime.now()
seven_days_from_now = today + timedelta(days=7)

# Load the 2025 schedule
schedule = nfl.load_schedules(2025)

# Filter for games in the next 7 days using Polars syntax
upcoming_games = schedule.filter(
    (pl.col('gameday').str.to_datetime() >= today) &
    (pl.col('gameday').str.to_datetime() <= seven_days_from_now)
)


# Write matchups to a file
with open('upcoming_matchups.txt', 'w') as f:
    for row in upcoming_games.iter_rows(named=True):
        f.write(f"{row['away_team']} at {row['home_team']}\n")

# 2. Develop a power ranking
# Load team stats and standings
team_stats = nfl.load_team_stats(2025)
standings = nfl.load_standings(2025)

# Calculate Pythagorean expectation
k = 2.37
team_stats = team_stats.with_columns(
    pyth_exp=(pl.col('points_for')**k / (pl.col('points_for')**k + pl.col('points_against')**k))
)

# Add wins, losses and ties from standings to the team_stats dataframe
team_stats = team_stats.join(standings.select(['team', 'wins', 'losses', 'ties']), left_on='team_abbr', right_on='team', how='left')

# Simple Ranking System (SRS)
# srs = margin of victory + strength of schedule
team_stats = team_stats.with_columns(
    mov=((pl.col('points_for') - pl.col('points_against')) / (pl.col('wins') + pl.col('losses') + pl.col('ties')))
)

# For simplicity, we'll use a combination of Pythagorean expectation and margin of victory
team_stats = team_stats.with_columns(
    power_ranking=(pl.col('pyth_exp') * 10 + pl.col('mov'))
)

# Sort by power ranking to get the rank
team_stats = team_stats.sort('power_ranking', descending=True).with_row_count('rank')
# The rank column will be 0-indexed, so add 1
team_stats = team_stats.with_columns(
    rank = pl.col('rank') + 1
)


# Write rankings to a file
with open('power_rankings.txt', 'w') as f:
    for row in team_stats.iter_rows(named=True):
        f.write(f"Rank {row['rank']}: {row['team_abbr']} (Power Ranking: {row['power_ranking']:.2f})\n")

# 3. Generate matchup scores
matchups = []
for row in upcoming_games.iter_rows(named=True):
    team1 = row['away_team']
    team2 = row['home_team']

    # Get the rankings for each team using Polars syntax
    rank1 = team_stats.filter(pl.col('team_abbr') == team1).select('rank').item()
    rank2 = team_stats.filter(pl.col('team_abbr') == team2).select('rank').item()

    # Calculate combined rank and similarity score
    combined_rank = rank1 + rank2
    similarity_score = 1 - (abs(rank1 - rank2) / (len(team_stats) - 1))

    # Calculate matchup score
    # We want a high score for good matchups (low combined rank) and close matchups (high similarity)
    # The weights here (0.6 and 0.4) can be adjusted
    matchup_score = ( (1 - (combined_rank / (len(team_stats)*2))) * 0.6 + similarity_score * 0.4) * 100
    matchups.append({
        'matchup': f"{team1} at {team2}",
        'team1_rank': rank1,
        'team2_rank': rank2,
        'combined_rank': combined_rank,
        'similarity_score': similarity_score,
        'matchup_score': matchup_score
    })

# Sort matchups by matchup score
sorted_matchups = sorted(matchups, key=lambda x: x['matchup_score'], reverse=True)

# 4. Output and write to file
with open('matchup_rankings.txt', 'w') as f:
    f.write("Upcoming Matchups Ranked by Matchup Score:\n\n")
    for matchup in sorted_matchups:
        f.write(f"Matchup: {matchup['matchup']}\n")
        f.write(f"  Team 1 Rank: {matchup['team1_rank']}\n")
        f.write(f"  Team 2 Rank: {matchup['team2_rank']}\n")
        f.write(f"  Combined Rank: {matchup['combined_rank']}\n")
        f.write(f"  Similarity Score: {matchup['similarity_score']:.2f}\n")
        f.write(f"  Matchup Score: {matchup['matchup_score']:.2f}\n\n")

print("Script completed successfully. Check the generated files for the results.")