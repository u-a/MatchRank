#!/usr/bin/env python3
"""
Simple test script to check NBA API capabilities for fetching upcoming games
"""

from nba_api.stats.endpoints import scoreboardv2
from datetime import datetime, timedelta
import time

def test_scoreboard_api():
    """
    Test the ScoreboardV2 endpoint for upcoming games
    """
    print("=" * 70)
    print("Testing NBA API - ScoreboardV2 Endpoint")
    print("=" * 70)
    
    today = datetime.now()
    
    print(f"\nCurrent date: {today.strftime('%Y-%m-%d')}")
    print("\nTesting dates from today through next 7 days...\n")
    
    for i in range(8):  # Today + next 7 days
        test_date = today + timedelta(days=i)
        date_str = test_date.strftime('%Y-%m-%d')
        day_name = test_date.strftime('%A')
        
        print(f"Checking {date_str} ({day_name}):")
        print("-" * 70)
        
        try:
            # Try fetching scoreboard for this date
            scoreboard = scoreboardv2.ScoreboardV2(
                game_date=date_str,
                day_offset=0
            )
            
            games = scoreboard.get_data_frames()[0]  # GameHeader dataframe
            
            if len(games) > 0:
                print(f"  ✓ Found {len(games)} game(s):")
                for idx, game in games.iterrows():
                    game_status = game.get('GAME_STATUS_TEXT', 'Unknown')
                    home_team = game.get('HOME_TEAM_ID', 'Unknown')
                    visitor_team = game.get('VISITOR_TEAM_ID', 'Unknown')
                    game_id = game.get('GAME_ID', 'Unknown')
                    
                    print(f"    - Game ID: {game_id}")
                    print(f"      Visitor: {visitor_team} @ Home: {home_team}")
                    print(f"      Status: {game_status}")
                    print()
            else:
                print(f"  ✗ No games found")
            
            print()
            
            # Rate limiting
            time.sleep(0.6)
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}\n")
            continue
    
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nWhat we learned:")
    print("1. ScoreboardV2 can query specific dates")
    print("2. It returns scheduled games (not just completed ones)")
    print("3. The 'game_date' parameter uses YYYY-MM-DD format")
    print("\nNote: If no upcoming games are found, it might be:")
    print("  - The All-Star break")
    print("  - End of season / Playoffs")
    print("  - Games not yet scheduled in the API")

def test_team_abbreviations():
    """
    Quick test to verify we can get team abbreviations from game data
    """
    print("\n" + "=" * 70)
    print("Bonus: Testing Team Data Extraction")
    print("=" * 70)
    
    try:
        from nba_api.stats.static import teams
        
        nba_teams = teams.get_teams()
        
        # Create team ID to abbreviation mapping
        team_map = {team['id']: team['abbreviation'] for team in nba_teams}
        
        print(f"\nSuccessfully loaded {len(team_map)} teams")
        print("\nSample teams:")
        for i, (team_id, abbr) in enumerate(list(team_map.items())[:5]):
            print(f"  Team ID {team_id}: {abbr}")
        
        print("\n✓ Team mapping works correctly")
        
    except Exception as e:
        print(f"\n✗ Error with team mapping: {str(e)}")

if __name__ == "__main__":
    test_scoreboard_api()
    test_team_abbreviations()