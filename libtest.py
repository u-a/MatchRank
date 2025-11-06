import nflreadpy as nfl

# Load team statistics for the specified years
team_stats_df = nfl.load_team_stats(seasons=[2025])

# Display the relevant columns for team records (wins, losses, ties)
if not team_stats_df.is_empty():
    # Select and display the columns related to team records
    team_records = team_stats_df[['team_abbr', 'season', 'wins', 'losses', 'ties']]
    print("Team Records for the 2025 Season:")
    print(team_records)
else:
    print(f"No team statistics found for the years: {[2025]}")