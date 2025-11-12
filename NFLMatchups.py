#!/usr/bin/env python3
"""
NFL Matchup Analysis Script
Analyzes upcoming NFL games and ranks matchups based on team strength and competitiveness
"""

import nfl_data_py as nfl
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def get_upcoming_matchups(days_ahead=7):
    """
    Identify NFL matchups in the next week
    """
    print("=" * 60)
    print("STEP 1: Fetching Upcoming NFL Matchups")
    print("=" * 60)
    
    # Get current season schedule
    current_year = datetime.now().year
    schedules = nfl.import_schedules([current_year])
    
    # Filter for upcoming games (today through next 7 days)
    today = datetime.now().date()
    cutoff_date = today + timedelta(days=days_ahead)
    
    schedules['gameday'] = pd.to_datetime(schedules['gameday'])
    schedules['game_date'] = schedules['gameday'].dt.date
    
    upcoming = schedules[
        (schedules['game_date'] >= today) & 
        (schedules['game_date'] <= cutoff_date)
    ].copy()
    
    # Sort by date
    upcoming = upcoming.sort_values('gameday')
    
    # Select relevant columns
    matchups = upcoming[[
        'game_id', 'gameday', 'gametime', 'away_team', 'home_team', 
        'away_score', 'home_score', 'week'
    ]].copy()
    
    print(f"\nFound {len(matchups)} matchups between {today} and {cutoff_date}")
    print(f"\nUpcoming Matchups:")
    print("-" * 60)
    
    for idx, row in matchups.iterrows():
        game_date = row['gameday'].strftime('%Y-%m-%d %A')
        game_time = row['gametime'] if pd.notna(row['gametime']) else 'TBD'
        print(f"{game_date} {game_time} | Week {row['week']}: {row['away_team']} @ {row['home_team']}")
    
    # Write to file
    with open('1_NFL_upcoming_matchups.txt', 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("NFL UPCOMING MATCHUPS\n")
        f.write(f"Analysis Date: {today}\n")
        f.write(f"Looking ahead: {days_ahead} days\n")
        f.write("=" * 60 + "\n\n")
        
        for idx, row in matchups.iterrows():
            game_date = row['gameday'].strftime('%Y-%m-%d %A')
            game_time = row['gametime'] if pd.notna(row['gametime']) else 'TBD'
            f.write(f"{game_date} | {game_time} | Week {row['week']}\n")
            f.write(f"  {row['away_team']} @ {row['home_team']}\n\n")
    
    print(f"\n✓ Matchups written to: 1_NFL_upcoming_matchups.txt")
    
    return matchups

def calculate_power_rankings():
    """
    Calculate power rankings using modified Pythagorean expectation
    """
    print("\n" + "=" * 60)
    print("STEP 2: Calculating Team Power Rankings")
    print("=" * 60)
    
    current_year = datetime.now().year
    
    # Get season data
    schedules = nfl.import_schedules([current_year])
    
    # Filter for completed games only
    completed = schedules[schedules['home_score'].notna()].copy()
    
    if len(completed) == 0:
        print("\nWarning: No completed games found. Using previous season data.")
        schedules = nfl.import_schedules([current_year - 1])
        completed = schedules[schedules['home_score'].notna()].copy()
    
    print(f"\nAnalyzing {len(completed)} completed games from {current_year} season")
    
    # Get all unique teams
    teams = pd.concat([completed['home_team'], completed['away_team']]).unique()
    
    # Calculate statistics for each team
    team_stats = {}
    
    for team in teams:
        # Home games
        home_games = completed[completed['home_team'] == team]
        # Away games
        away_games = completed[completed['away_team'] == team]
        
        # Points scored and allowed
        points_scored = (
            home_games['home_score'].sum() + 
            away_games['away_score'].sum()
        )
        points_allowed = (
            home_games['away_score'].sum() + 
            away_games['home_score'].sum()
        )
        
        # Wins and losses
        home_wins = (home_games['home_score'] > home_games['away_score']).sum()
        away_wins = (away_games['away_score'] > away_games['home_score']).sum()
        wins = home_wins + away_wins
        
        games_played = len(home_games) + len(away_games)
        losses = games_played - wins
        
        # Modified Pythagorean Expectation (exponent = 2.37 for NFL)
        if points_allowed > 0:
            pyth_exp = (points_scored ** 2.37) / (
                points_scored ** 2.37 + points_allowed ** 2.37
            )
        else:
            pyth_exp = 1.0
        
        # Point differential
        point_diff = points_scored - points_allowed
        
        # Win percentage
        win_pct = wins / games_played if games_played > 0 else 0
        
        # Combined ranking score (weighted average)
        # 40% Pythagorean, 30% Win%, 30% Point Differential (normalized)
        max_point_diff = 300  # Normalization factor
        norm_point_diff = max(0, min(1, (point_diff + max_point_diff) / (2 * max_point_diff)))
        
        power_score = (
            0.40 * pyth_exp + 
            0.30 * win_pct + 
            0.30 * norm_point_diff
        ) * 100
        
        team_stats[team] = {
            'team': team,
            'games_played': games_played,
            'wins': wins,
            'losses': losses,
            'win_pct': win_pct,
            'points_scored': points_scored,
            'points_allowed': points_allowed,
            'point_diff': point_diff,
            'pyth_expectation': pyth_exp,
            'power_score': power_score
        }
    
    # Create DataFrame and sort by power score
    rankings_df = pd.DataFrame(team_stats.values())
    rankings_df = rankings_df.sort_values('power_score', ascending=False).reset_index(drop=True)
    rankings_df['rank'] = range(1, len(rankings_df) + 1)
    
    print("\nTop 10 Teams by Power Ranking:")
    print("-" * 60)
    for idx, row in rankings_df.head(10).iterrows():
        print(f"{row['rank']:2d}. {row['team']:3s} | "
              f"Power Score: {row['power_score']:5.2f} | "
              f"Record: {row['wins']:.0f}-{row['losses']:.0f} | "
              f"Pt Diff: {row['point_diff']:+.0f}")
    
    # Write to file
    with open('2_NFL_power_rankings.txt', 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("NFL TEAM POWER RANKINGS\n")
        f.write(f"Season: {current_year}\n")
        f.write(f"Games Analyzed: {len(completed)}\n")
        f.write("=" * 80 + "\n\n")
        f.write("Ranking Methodology:\n")
        f.write("  - Modified Pythagorean Expectation (40%)\n")
        f.write("  - Win Percentage (30%)\n")
        f.write("  - Point Differential (30%)\n")
        f.write("  - Power Score: 0-100 scale (higher is better)\n\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Rank':<6}{'Team':<6}{'Power':<10}{'Record':<12}{'PF':<8}{'PA':<8}{'Diff':<8}{'Pyth':<8}\n")
        f.write("-" * 80 + "\n")
        
        for idx, row in rankings_df.iterrows():
            f.write(f"{row['rank']:<6}{row['team']:<6}{row['power_score']:<10.2f}"
                   f"{row['wins']:.0f}-{row['losses']:.0f}{'':<7}"
                   f"{row['points_scored']:<8.0f}{row['points_allowed']:<8.0f}"
                   f"{row['point_diff']:<8.0f}{row['pyth_expectation']:<8.3f}\n")
    
    print(f"\n✓ Rankings written to: 2_NFL_power_rankings.txt")
    
    return rankings_df

def analyze_matchups(matchups, rankings):
    """
    Analyze and rank matchups based on team strength and competitiveness
    """
    print("\n" + "=" * 60)
    print("STEP 3: Analyzing and Ranking Matchups")
    print("=" * 60)
    
    # Create lookup dictionary for rankings
    rank_dict = rankings.set_index('team')['power_score'].to_dict()
    team_rank_dict = rankings.set_index('team')['rank'].to_dict()
    
    matchup_analysis = []
    
    for idx, game in matchups.iterrows():
        away_team = game['away_team']
        home_team = game['home_team']
        
        # Get power scores (default to 50 if team not found)
        away_score = rank_dict.get(away_team, 50)
        home_score = rank_dict.get(home_team, 50)
        
        away_rank = team_rank_dict.get(away_team, 16)
        home_rank = team_rank_dict.get(home_team, 16)
        
        # Ranking Score: Combined quality of teams (0-100)
        # Higher score = better combined team quality
        ranking_score = (away_score + home_score) / 2
        
        # Similarity Score: How evenly matched are the teams (0-100)
        # Higher score = more competitive/closer matchup
        score_diff = abs(away_score - home_score)
        max_diff = 100  # Maximum possible difference
        similarity_score = (1 - (score_diff / max_diff)) * 100
        
        # Matchup Score: Holistic score combining both factors
        # Weight: 40% similarity (competitiveness), 60% ranking (quality)
        # This prioritizes close games between good teams
        matchup_score = (0.40 * similarity_score + 0.60 * ranking_score)
        
        matchup_analysis.append({
            'game_id': game['game_id'],
            'gameday': game['gameday'],
            'gametime': game['gametime'],
            'week': game['week'],
            'away_team': away_team,
            'home_team': home_team,
            'away_power': away_score,
            'home_power': home_score,
            'away_rank': away_rank,
            'home_rank': home_rank,
            'ranking_score': ranking_score,
            'similarity_score': similarity_score,
            'matchup_score': matchup_score
        })
    
    # Create DataFrame and sort by matchup score
    matchup_df = pd.DataFrame(matchup_analysis)
    matchup_df = matchup_df.sort_values('matchup_score', ascending=False).reset_index(drop=True)
    
    print(f"\nTop Matchups (by Matchup Score):")
    print("-" * 60)
    
    for idx, row in matchup_df.iterrows():
        game_date = row['gameday'].strftime('%m/%d')
        game_time = row['gametime'] if pd.notna(row['gametime']) else 'TBD'
        print(f"{idx + 1}. [{game_date} {game_time}] {row['away_team']} @ {row['home_team']}")
        print(f"   Matchup Score: {row['matchup_score']:.1f}/100 | "
              f"Quality: {row['ranking_score']:.1f} | "
              f"Competitive: {row['similarity_score']:.1f}")
        print(f"   Team Ranks: #{row['away_rank']} vs #{row['home_rank']}")
        print()
    
    # Write to file
    with open('3_NFL_matchup_rankings.txt', 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("NFL MATCHUP RANKINGS\n")
        f.write(f"Analysis Date: {datetime.now().date()}\n")
        f.write("=" * 80 + "\n\n")
        f.write("Scoring Methodology:\n")
        f.write("  - Ranking Score: Average power rating of both teams (0-100)\n")
        f.write("  - Similarity Score: How evenly matched teams are (0-100)\n")
        f.write("  - Matchup Score: 60% similarity + 40% quality (0-100)\n")
        f.write("    Higher scores indicate competitive games between strong teams\n\n")
        f.write("=" * 80 + "\n\n")
        
        for idx, row in matchup_df.iterrows():
            game_date = row['gameday'].strftime('%Y-%m-%d %A')
            game_time = row['gametime'] if pd.notna(row['gametime']) else 'TBD'
            f.write(f"RANK {idx + 1}: MATCHUP SCORE = {row['matchup_score']:.1f}/100\n")
            f.write("-" * 80 + "\n")
            f.write(f"Date: {game_date}\n")
            f.write(f"Time: {game_time}\n")
            f.write(f"Week: {row['week']}\n")
            f.write(f"Matchup: {row['away_team']} @ {row['home_team']}\n\n")
            f.write(f"  Away Team: {row['away_team']}\n")
            f.write(f"    - Power Rank: #{row['away_rank']} (Score: {row['away_power']:.2f})\n\n")
            f.write(f"  Home Team: {row['home_team']}\n")
            f.write(f"    - Power Rank: #{row['home_rank']} (Score: {row['home_power']:.2f})\n\n")
            f.write(f"  Scores:\n")
            f.write(f"    - Combined Quality Score: {row['ranking_score']:.1f}/100\n")
            f.write(f"    - Competitiveness Score: {row['similarity_score']:.1f}/100\n")
            f.write(f"    - Overall Matchup Score: {row['matchup_score']:.1f}/100\n\n")
            f.write("=" * 80 + "\n\n")
    
    print(f"✓ Matchup analysis written to: 3_NFL_matchup_rankings.txt")
    
    return matchup_df

def main():
    """
    Main execution function
    """
    print("\n" + "=" * 60)
    print("NFL MATCHUP ANALYSIS PIPELINE")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Get upcoming matchups
        matchups = get_upcoming_matchups(days_ahead=7)
        
        if len(matchups) == 0:
            print("\nNo upcoming matchups found in the next 7 days.")
            return
        
        # Step 2: Calculate power rankings
        rankings = calculate_power_rankings()
        
        # Step 3: Analyze and rank matchups
        matchup_rankings = analyze_matchups(matchups, rankings)
        
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print("\nGenerated Files:")
        print("  1. 1_NFL_upcoming_matchups.txt - List of games in next 7 days")
        print("  2. 2_NFL_power_rankings.txt - Team power rankings")
        print("  3. 3_NFL_matchup_rankings.txt - Ranked matchups with analysis")
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()