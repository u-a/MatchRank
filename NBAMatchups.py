#!/usr/bin/env python3
"""
NBA Matchup Analysis Script
Analyzes upcoming NBA games and ranks matchups based on team strength and competitiveness
"""

from nba_api.stats.endpoints import leaguegamefinder, scoreboardv2, leaguestandingsv3
from nba_api.stats.static import teams
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import time
import warnings
warnings.filterwarnings('ignore')

def get_current_season():
    """
    Determine the current NBA season based on date
    NBA seasons run from October to June
    """
    now = datetime.now()
    year = now.year
    month = now.month
    
    # NBA season spans two calendar years (e.g., 2024-25 season runs Oct 2024 - June 2025)
    # If we're in Jan-June, the season started previous year
    # If we're in Oct-Dec, the season started this year
    # If we're in July-Sept, it's offseason (use previous completed season)
    
    if month >= 10:  # October, November, December - season started this year
        return f"{year}-{str(year + 1)[-2:]}"
    elif month <= 6:  # January through June - season started last year
        return f"{year - 1}-{str(year)[-2:]}"
    else:  # July, August, September - offseason
        return f"{year - 1}-{str(year)[-2:]}"

def get_upcoming_matchups(days_ahead=7):
    """
    Identify NBA matchups in the next week using ScoreboardV2
    """
    print("=" * 60)
    print("STEP 1: Fetching Upcoming NBA Matchups")
    print("=" * 60)
    
    today = datetime.now()
    season = get_current_season()
    
    print(f"\nCurrent Date: {today.strftime('%Y-%m-%d')}")
    print(f"Current Season: {season}")
    print(f"Scanning for games over the next {days_ahead} days...")
    
    all_matchups = []
    
    # Try ScoreboardV2 for each day
    for i in range(days_ahead + 1):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        
        try:
            scoreboard = scoreboardv2.ScoreboardV2(
                game_date=date_str,
                day_offset=0
            )
            
            games_df = scoreboard.get_data_frames()[0]  # GameHeader
            line_score_df = scoreboard.get_data_frames()[1]  # LineScore
            
            if len(games_df) > 0:
                print(f"  {date_str}: Found {len(games_df)} game(s)")
                
                # Build team ID to abbreviation map
                from nba_api.stats.static import teams as static_teams
                nba_teams = static_teams.get_teams()
                team_map = {team['id']: team['abbreviation'] for team in nba_teams}
                
                for _, game in games_df.iterrows():
                    home_team_id = game['HOME_TEAM_ID']
                    visitor_team_id = game['VISITOR_TEAM_ID']
                    game_status_text = game.get('GAME_STATUS_TEXT', 'Scheduled')
                    
                    all_matchups.append({
                        'game_id': game['GAME_ID'],
                        'game_date': check_date,
                        'away_team': team_map.get(visitor_team_id, str(visitor_team_id)),
                        'home_team': team_map.get(home_team_id, str(home_team_id)),
                        'game_time': game_status_text,  # CHANGE THIS LINE
                        'game_status': game_status_text
                    })
            
            time.sleep(0.6)  # Rate limiting
            
        except Exception as e:
            print(f"  {date_str}: Error - {str(e)}")
            continue
    
    # If no upcoming games found, fall back to recent games
    if len(all_matchups) == 0:
        print("\nNo upcoming games found using ScoreboardV2.")
        print("This might be All-Star break or games not yet scheduled in API.")
        print("\nFalling back to recent games from LeagueGameFinder...")
        
        try:
            game_finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable='Regular Season',
                league_id_nullable='00'
            )
            
            all_games = game_finder.get_data_frames()[0]
            all_games['GAME_DATE'] = pd.to_datetime(all_games['GAME_DATE'])
            
            # Get recent completed games
            recent = all_games[all_games['GAME_DATE'] < today].copy()
            recent = recent.sort_values('GAME_DATE', ascending=False)
            unique_games = recent.drop_duplicates(subset=['GAME_ID']).head(10)
            
            # Process games
            for game_id in unique_games['GAME_ID'].unique():
                game_data = all_games[all_games['GAME_ID'] == game_id]
                
                if len(game_data) < 2:
                    continue
                
                game_date = game_data.iloc[0]['GAME_DATE']
                away_team = None
                home_team = None
                
                for _, row in game_data.iterrows():
                    matchup_str = row['MATCHUP']
                    if '@' in matchup_str:
                        away_team = row['TEAM_ABBREVIATION']
                    elif 'vs.' in matchup_str:
                        home_team = row['TEAM_ABBREVIATION']
                
                if away_team and home_team:
                    all_matchups.append({
                        'game_id': game_id,
                        'game_date': game_date,
                        'away_team': away_team,
                        'home_team': home_team,
                        'game_status': 'Recent Game (Sample)'
                    })
        
        except Exception as e:
            print(f"Error with fallback: {str(e)}")
    
    if len(all_matchups) == 0:
        print("\nCould not retrieve any matchups.")
        return pd.DataFrame()
    
    matchups_df = pd.DataFrame(all_matchups)
    matchups_df = matchups_df.sort_values('game_date')
    
    print(f"\nFound {len(matchups_df)} matchups:")
    print("-" * 60)
    
    for idx, row in matchups_df.iterrows():
        game_date = row['game_date'].strftime('%Y-%m-%d %A')
        game_time = row.get('game_status', 'TBD')
        print(f"{game_date} | {game_time}: {row['away_team']} @ {row['home_team']}")
    
    # Write to file
    with open('1_NBA_upcoming_matchups.txt', 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("NBA UPCOMING MATCHUPS\n")
        f.write(f"Season: {season}\n")
        f.write(f"Analysis Date: {today.date()}\n")
        f.write("=" * 60 + "\n\n")
        
        for idx, row in matchups_df.iterrows():
            game_date = row['game_date'].strftime('%Y-%m-%d %A')
            game_time = row.get('game_time', 'TBD')
            f.write(f"{game_date} | {game_time}\n")
            f.write(f"  {row['away_team']} @ {row['home_team']}\n")
            f.write(f"  Status: {row.get('game_status', 'Scheduled')}\n\n")
    
    print(f"\n✓ Matchups written to: 1_NBA_upcoming_matchups.txt")
    
    return matchups_df

def calculate_power_rankings():
    """
    Calculate power rankings using offensive and defensive efficiency
    """
    print("\n" + "=" * 60)
    print("STEP 2: Calculating Team Power Rankings")
    print("=" * 60)
    
    season = get_current_season()
    
    print(f"\nFetching team statistics for {season} season...")
    print("This may take a minute due to API rate limiting...")
    
    # Get all NBA teams
    nba_teams = teams.get_teams()
    
    # Get all games for the season to calculate stats
    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable='Regular Season',
            league_id_nullable='00'
        )
        
        all_games = game_finder.get_data_frames()[0]
        
        # Filter for completed games only
        all_games = all_games[all_games['PTS'].notna()].copy()
        
        if len(all_games) == 0:
            print("\nNo games have been played this season yet.")
            return pd.DataFrame()
        
        print(f"Analyzing {len(all_games)} game records...")
        
        team_stats = []
        
        for team in nba_teams:
            team_abbr = team['abbreviation']
            team_id = team['id']
            
            # Get this team's games
            team_games = all_games[all_games['TEAM_ID'] == team_id].copy()
            
            if len(team_games) == 0:
                continue
            
            games_played = len(team_games)
            wins = (team_games['WL'] == 'W').sum()
            losses = games_played - wins
            win_pct = wins / games_played if games_played > 0 else 0
            
            # Points scored and allowed
            pts_scored = team_games['PTS'].sum()
            pts_allowed = 0
            
            # Calculate points allowed by looking up opponent scores
            for _, game in team_games.iterrows():
                game_id = game['GAME_ID']
                opponent_game = all_games[
                    (all_games['GAME_ID'] == game_id) & 
                    (all_games['TEAM_ID'] != team_id)
                ]
                if len(opponent_game) > 0:
                    pts_allowed += opponent_game.iloc[0]['PTS']
            
            avg_pts = pts_scored / games_played
            avg_pts_allowed = pts_allowed / games_played
            
            # Point differential
            point_diff = pts_scored - pts_allowed
            net_rating = point_diff / games_played
            
            # Offensive and Defensive Efficiency estimate
            total_fga = team_games['FGA'].sum()
            total_fta = team_games['FTA'].sum()
            total_oreb = team_games['OREB'].sum()
            total_tov = team_games['TOV'].sum()
            
            possessions = total_fga + (0.44 * total_fta) - total_oreb + total_tov
            
            if possessions > 0:
                off_efficiency = (pts_scored / possessions) * 100
                def_efficiency = (pts_allowed / possessions) * 100
            else:
                off_efficiency = avg_pts
                def_efficiency = avg_pts_allowed
            
            # Power Score calculation
            max_net_rating = 15
            norm_net_rating = max(0, min(1, (net_rating + max_net_rating) / (2 * max_net_rating)))
            
            norm_off_eff = max(0, min(1, (off_efficiency - 95) / 30))
            norm_def_eff = max(0, min(1, (125 - def_efficiency) / 30))
            
            power_score = (
                0.50 * win_pct +
                0.20 * norm_net_rating +
                0.15 * norm_off_eff +
                0.15 * norm_def_eff
            ) * 100
            
            team_stats.append({
                'team': team_abbr,
                'team_name': team['full_name'],
                'games_played': games_played,
                'wins': wins,
                'losses': losses,
                'win_pct': win_pct,
                'avg_pts': avg_pts,
                'avg_pts_allowed': avg_pts_allowed,
                'point_diff': point_diff,
                'net_rating': net_rating,
                'off_efficiency': off_efficiency,
                'def_efficiency': def_efficiency,
                'power_score': power_score
            })
        
        rankings_df = pd.DataFrame(team_stats)
        
        if rankings_df.empty:
            print("\nCould not calculate rankings.")
            return rankings_df
        
        rankings_df = rankings_df.sort_values('power_score', ascending=False).reset_index(drop=True)
        rankings_df['rank'] = range(1, len(rankings_df) + 1)
        
        print(f"\nAnalyzed {len(rankings_df)} teams")
        print("\nTop 10 Teams by Power Ranking:")
        print("-" * 60)
        
        for idx, row in rankings_df.head(10).iterrows():
            print(f"{row['rank']:2d}. {row['team']:3s} | "
                  f"Power: {row['power_score']:5.2f} | "
                  f"Record: {row['wins']:.0f}-{row['losses']:.0f} | "
                  f"Net Rtg: {row['net_rating']:+.1f}")
        
        # Write to file
        with open('2_NBA_power_rankings.txt', 'w') as f:
            f.write("=" * 85 + "\n")
            f.write("NBA TEAM POWER RANKINGS\n")
            f.write(f"Season: {season}\n")
            f.write("=" * 85 + "\n\n")
            f.write("Ranking Methodology:\n")
            f.write("  - Win Percentage (35%)\n")
            f.write("  - Net Rating (30%)\n")
            f.write("  - Offensive Efficiency (20%)\n")
            f.write("  - Defensive Efficiency (15%)\n")
            f.write("  - Power Score: 0-100 scale (higher is better)\n\n")
            f.write("-" * 85 + "\n")
            f.write(f"{'Rank':<6}{'Team':<6}{'Power':<10}{'Record':<10}{'PPG':<8}{'PAPG':<8}"
                    f"{'NetRtg':<10}{'OffEff':<10}{'DefEff':<8}\n")
            f.write("-" * 85 + "\n")
            
            for idx, row in rankings_df.iterrows():
                f.write(f"{row['rank']:<6}{row['team']:<6}{row['power_score']:<10.2f}"
                       f"{row['wins']:.0f}-{row['losses']:.0f}{'':<5}"
                       f"{row['avg_pts']:<8.1f}{row['avg_pts_allowed']:<8.1f}"
                       f"{row['net_rating']:<10.2f}{row['off_efficiency']:<10.2f}"
                       f"{row['def_efficiency']:<8.2f}\n")
        
        print(f"\n✓ Rankings written to: 2_NBA_power_rankings.txt")
        
        return rankings_df
        
    except Exception as e:
        print(f"\nError calculating rankings: {str(e)}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def analyze_matchups(matchups, rankings):
    """
    Analyze and rank matchups based on team strength and competitiveness
    """
    print("\n" + "=" * 60)
    print("STEP 3: Analyzing and Ranking Matchups")
    print("=" * 60)
    
    if rankings.empty or matchups.empty:
        print("\nInsufficient data to analyze matchups.")
        return pd.DataFrame()
    
    # Create lookup dictionaries
    rank_dict = rankings.set_index('team')['power_score'].to_dict()
    team_rank_dict = rankings.set_index('team')['rank'].to_dict()
    
    matchup_analysis = []
    
    for idx, game in matchups.iterrows():
        away_team = game['away_team']
        home_team = game['home_team']
        
        # Get power scores
        away_score = rank_dict.get(away_team, 50)
        home_score = rank_dict.get(home_team, 50)
        
        away_rank = team_rank_dict.get(away_team, 15)
        home_rank = team_rank_dict.get(home_team, 15)
        
        # Ranking Score: Combined quality of teams (0-100)
        ranking_score = (away_score + home_score) / 2
        
        # Similarity Score: How evenly matched (0-100)
        score_diff = abs(away_score - home_score)
        max_diff = 100
        similarity_score = (1 - (score_diff / max_diff)) * 100
        
        # Matchup Score: 60% similarity (competitiveness), 40% quality
        matchup_score = (0.30 * similarity_score + 0.70 * ranking_score)
        
        matchup_analysis.append({
            'game_id': game['game_id'],
            'game_date': game['game_date'],
            'game_time': game.get('game_time', 'TBD'),
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
    
    matchup_df = pd.DataFrame(matchup_analysis)
    matchup_df = matchup_df.sort_values('matchup_score', ascending=False).reset_index(drop=True)
    
    print(f"\nTop Matchups (by Matchup Score):")
    print("-" * 60)
    
    for idx, row in matchup_df.iterrows():
        if isinstance(row['game_date'], datetime):
            game_date = row['game_date'].strftime('%m/%d')
        else:
            game_date = str(row['game_date'])
    
        game_time = row.get('game_time', 'TBD')
    
        print(f"{idx + 1}. [{game_date} {game_time}] {row['away_team']} @ {row['home_team']}")
        print(f"   Matchup Score: {row['matchup_score']:.1f}/100 | "
              f"Quality: {row['ranking_score']:.1f} | "
              f"Competitive: {row['similarity_score']:.1f}")
        print(f"   Team Ranks: #{row['away_rank']} vs #{row['home_rank']}")
        print()
    
    # Write to file
    with open('3_NBA_matchup_rankings.txt', 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("NBA MATCHUP RANKINGS\n")
        f.write(f"Analysis Date: {datetime.now().date()}\n")
        f.write("=" * 80 + "\n\n")
        f.write("Scoring Methodology:\n")
        f.write("  - Ranking Score: Average power rating of both teams (0-100)\n")
        f.write("  - Similarity Score: How evenly matched teams are (0-100)\n")
        f.write("  - Matchup Score: 60% quality + 40% similarity (0-100)\n")
        f.write("    Higher scores indicate competitive games between strong teams\n\n")
        f.write("=" * 80 + "\n\n")
        
        for idx, row in matchup_df.iterrows():
            if isinstance(row['game_date'], datetime):
                game_date = row['game_date'].strftime('%Y-%m-%d %A')
            else:
                game_date = str(row['game_date'])
    
            game_time = row.get('game_time', 'TBD')
    
            f.write(f"RANK {idx + 1}: MATCHUP SCORE = {row['matchup_score']:.1f}/100\n")
            f.write("-" * 80 + "\n")
            f.write(f"Date: {game_date}\n")
            f.write(f"Time: {game_time}\n")
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
    
    print(f"✓ Matchup analysis written to: 3_NBA_matchup_rankings.txt")
    
    return matchup_df

def main():
    """
    Main execution function
    """
    print("\n" + "=" * 60)
    print("NBA MATCHUP ANALYSIS PIPELINE")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Get upcoming matchups
        matchups = get_upcoming_matchups(days_ahead=7)
        
        # Step 2: Calculate power rankings
        rankings = calculate_power_rankings()
        
        if not rankings.empty and not matchups.empty:
            # Step 3: Analyze and rank matchups
            matchup_rankings = analyze_matchups(matchups, rankings)
        
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print("\nGenerated Files:")
        print("  1. 1_NBA_upcoming_matchups.txt - List of games in next 7 days")
        print("  2. 2_NBA_power_rankings.txt - Team power rankings")
        print("  3. 3_NBA_matchup_rankings.txt - Ranked matchups with analysis")
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()