#!/usr/bin/env python3
"""
NBA Matchup Analysis Script - Optimized Version
Analyzes NBA games for today and upcoming week with enhanced readability
"""

from nba_api.stats.endpoints import leaguegamefinder, scoreboardv2, leaguestandingsv3
from nba_api.stats.static import teams
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import time
import warnings
warnings.filterwarnings('ignore')

# Configure NBA API to work with GitHub Actions and cloud IPs
# The NBA API blocks requests without proper headers
from nba_api.stats.library.http import NBAStatsHTTP
NBAStatsHTTP.timeout = 60  # Increase timeout for GitHub Actions
# Set headers to mimic browser requests
import requests
requests.Session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
    'Connection': 'keep-alive',
}


def get_current_season():
    """Determine the current NBA season based on date"""
    now = datetime.now()
    year = now.year
    month = now.month
    
    if month >= 10:  # October-December: season started this year
        return f"{year}-{str(year + 1)[-2:]}"
    elif month <= 6:  # January-June: season started last year
        return f"{year - 1}-{str(year)[-2:]}"
    else:  # July-September: offseason
        return f"{year - 1}-{str(year)[-2:]}"


def get_games_by_date_range(days_ahead=7):
    """
    Fetch games from today through the next N days
    Returns a DataFrame with game information including status
    """
    print(f"Fetching NBA games for the next {days_ahead + 1} days...")
    
    today = datetime.now()
    season = get_current_season()
    all_games = []
    
    # Build team ID to abbreviation map
    nba_teams = teams.get_teams()
    team_map = {team['id']: team['abbreviation'] for team in nba_teams}
    
    for i in range(days_ahead + 1):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        
        try:
            # Add headers to avoid being blocked by NBA API
            scoreboard = scoreboardv2.ScoreboardV2(
                game_date=date_str, 
                day_offset=0,
                timeout=60  # Increase timeout for slower connections
            )
            games_df = scoreboard.get_data_frames()[0]  # GameHeader
            line_score_df = scoreboard.get_data_frames()[1]  # LineScore
            
            if len(games_df) > 0:
                for _, game in games_df.iterrows():
                    home_team_id = game['HOME_TEAM_ID']
                    visitor_team_id = game['VISITOR_TEAM_ID']
                    game_status = game.get('GAME_STATUS_TEXT', 'Scheduled')
                    
                    # Extract scores from line_score_df if game is final
                    home_score = None
                    away_score = None
                    if 'Final' in game_status:
                        game_lines = line_score_df[line_score_df['GAME_ID'] == game['GAME_ID']]
                        for _, line in game_lines.iterrows():
                            if line['TEAM_ID'] == home_team_id:
                                home_score = line.get('PTS', 0)
                            elif line['TEAM_ID'] == visitor_team_id:
                                away_score = line.get('PTS', 0)
                    
                    all_games.append({
                        'game_id': game['GAME_ID'],
                        'game_date': check_date,
                        'away_team': team_map.get(visitor_team_id, str(visitor_team_id)),
                        'home_team': team_map.get(home_team_id, str(home_team_id)),
                        'game_status': game_status,
                        'away_score': away_score,
                        'home_score': home_score,
                        'is_today': check_date.date() == today.date()
                    })
            
            time.sleep(1.0)  # Increased rate limiting for GitHub Actions (was 0.6)
            
        except Exception as e:
            print(f"  Error for {date_str}: {str(e)}")
            continue
    
    if len(all_games) == 0:
        print("No games found in the specified date range.")
        return pd.DataFrame()
    
    games_df = pd.DataFrame(all_games)
    games_df = games_df.sort_values('game_date')
    
    print(f"Found {len(games_df)} total games")
    return games_df


def calculate_power_rankings():
    """Calculate team power rankings using win%, net rating, and efficiency"""
    print("\nCalculating team power rankings...")
    
    season = get_current_season()
    nba_teams = teams.get_teams()
    
    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable='Regular Season',
            league_id_nullable='00'
        )
        
        all_games = game_finder.get_data_frames()[0]
        
        team_stats = []
        
        for team in nba_teams:
            team_abbr = team['abbreviation']
            team_games = all_games[all_games['TEAM_ABBREVIATION'] == team_abbr].copy()
            
            if len(team_games) == 0:
                continue
            
            # Calculate statistics
            wins = team_games['WL'].value_counts().get('W', 0)
            losses = team_games['WL'].value_counts().get('L', 0)
            total_games = wins + losses
            
            if total_games == 0:
                continue
            
            win_pct = wins / total_games
            avg_pts = team_games['PTS'].mean()
            avg_pts_allowed = team_games['PTS'].apply(
                lambda x: all_games[
                    (all_games['GAME_ID'] == team_games[team_games['PTS'] == x].iloc[0]['GAME_ID']) &
                    (all_games['TEAM_ABBREVIATION'] != team_abbr)
                ]['PTS'].iloc[0] if len(all_games[
                    (all_games['GAME_ID'] == team_games[team_games['PTS'] == x].iloc[0]['GAME_ID']) &
                    (all_games['TEAM_ABBREVIATION'] != team_abbr)
                ]) > 0 else 0
            ).mean() if len(team_games) > 0 else 0
            
            # Simplified calculation for allowed points
            avg_pts_allowed = team_games['PLUS_MINUS'].apply(lambda pm: avg_pts - pm).mean()
            
            net_rating = avg_pts - avg_pts_allowed
            off_efficiency = avg_pts
            def_efficiency = avg_pts_allowed
            
            # Power score calculation (0-100 scale)
            power_score = (
                win_pct * 35 +
                ((net_rating + 15) / 30) * 30 +
                (off_efficiency / 120) * 20 +
                ((120 - def_efficiency) / 120) * 15
            ) * 100 / 100
            
            team_stats.append({
                'team': team_abbr,
                'wins': wins,
                'losses': losses,
                'win_pct': win_pct,
                'avg_pts': avg_pts,
                'avg_pts_allowed': avg_pts_allowed,
                'net_rating': net_rating,
                'off_efficiency': off_efficiency,
                'def_efficiency': def_efficiency,
                'power_score': power_score
            })
        
        rankings_df = pd.DataFrame(team_stats)
        rankings_df = rankings_df.sort_values('power_score', ascending=False).reset_index(drop=True)
        rankings_df['rank'] = rankings_df.index + 1
        
        print(f"Power rankings calculated for {len(rankings_df)} teams")
        return rankings_df
        
    except Exception as e:
        print(f"Error calculating rankings: {str(e)}")
        return pd.DataFrame()


def analyze_matchups(games_df, rankings_df):
    """
    Analyze each game and determine watchability
    Returns games_df with added analysis columns
    """
    if rankings_df.empty or games_df.empty:
        return games_df
    
    # IMPORTANT: Deduplicate games by game_id to prevent duplicates in output
    # This fixes the issue where same game appears multiple times
    games_df = games_df.drop_duplicates(subset=['game_id'], keep='first').reset_index(drop=True)
    
    # Create lookup dictionaries
    rank_dict = rankings_df.set_index('team')['power_score'].to_dict()
    team_rank_dict = rankings_df.set_index('team')['rank'].to_dict()
    
    # Add analysis for each game
    games_df['away_power'] = games_df['away_team'].map(rank_dict).fillna(50)
    games_df['home_power'] = games_df['home_team'].map(rank_dict).fillna(50)
    games_df['away_rank'] = games_df['away_team'].map(team_rank_dict).fillna(15)
    games_df['home_rank'] = games_df['home_team'].map(team_rank_dict).fillna(15)
    
    # Calculate matchup quality scores
    # Keep this as simple average - it naturally centers around 50 with good spread (30-70 range)
    games_df['quality_score'] = (games_df['away_power'] + games_df['home_power']) / 2
    
    # IMPROVED: Calculate competitiveness with better distribution
    # Old formula: (1 - diff/100) * 100 gave 60-100 range (too compressed)
    # New formula: Use squared difference to amplify spread, then scale
    # This gives us a 0-100 range with better discrimination between matchups
    score_diff = abs(games_df['away_power'] - games_df['home_power'])
    
    # Use exponential decay for competitive score: more sensitive to differences
    # Perfect match (diff=0) = 100, Large diff (40+) approaches 0
    # Formula: 100 * e^(-diff/15) gives good spread across 0-100 range
    games_df['competitive_score'] = 100 * np.exp(-score_diff / 15)
    
    # Alternative simpler formula if you prefer: quadratic penalty
    # games_df['competitive_score'] = 100 * (1 - (score_diff / 50) ** 2).clip(0, 100)
    
    # Overall matchup score: Rebalanced to 60% quality, 40% competitiveness
    # Since competitive score now has better spread, we give it more weight
    games_df['matchup_score'] = (0.60 * games_df['quality_score'] + 
                                   0.40 * games_df['competitive_score'])
    
    # Determine watchability tier (adjusted thresholds for new scoring)
    def get_tier(score):
        if score >= 70:
            return "🔥 MUST WATCH"
        elif score >= 60:
            return "⭐ HIGHLY RECOMMENDED"
        elif score >= 50:
            return "👍 WORTH WATCHING"
        else:
            return "📺 Optional"
    
    games_df['tier'] = games_df['matchup_score'].apply(get_tier)
    
    # Sort by matchup score
    games_df = games_df.sort_values(['game_date', 'matchup_score'], 
                                     ascending=[True, False])
    
    return games_df


def format_game_markdown(row, rank_num=None, total_games=None):
    """Format a single game as markdown"""
    lines = []
    
    # Header with tier and matchup
    if rank_num and total_games:
        lines.append(f"### #{rank_num}/{total_games} - {row['tier']}")
    else:
        lines.append(f"### {row['tier']}")
    
    # Game matchup - check for NaN using pd.notna() or manual check
    has_scores = (row['away_score'] is not None and 
                  row['home_score'] is not None and 
                  not pd.isna(row['away_score']) and 
                  not pd.isna(row['home_score']))
    
    if has_scores:
        # Completed game with scores
        lines.append(f"**{row['away_team']} {int(row['away_score'])} @ "
                    f"{row['home_team']} {int(row['home_score'])}** - {row['game_status']}")
    else:
        # Upcoming game without scores
        lines.append(f"**{row['away_team']} @ {row['home_team']}** - {row['game_status']}")
    
    # Rankings and scores
    lines.append(f"- **Team Rankings:** #{int(row['away_rank'])} {row['away_team']} vs "
                f"#{int(row['home_rank'])} {row['home_team']}")
    lines.append(f"- **Matchup Score:** {row['matchup_score']:.1f}/100 "
                f"(Quality: {row['quality_score']:.1f}, Competitive: {row['competitive_score']:.1f})")
    
    return "\n".join(lines)


def write_markdown_report(games_df, rankings_df, output_file='NBA_Weekly_Report.md'):
    """Write comprehensive markdown report"""
    
    today = datetime.now()
    season = get_current_season()
    
    # Separate today's games from upcoming
    todays_games = games_df[games_df['is_today'] == True]
    upcoming_games = games_df[games_df['is_today'] == False]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# 🏀 NBA Weekly Matchup Report\n\n")
        f.write(f"**Season:** {season}  \n")
        f.write(f"**Generated:** {today.strftime('%A, %B %d, %Y at %I:%M %p')}  \n")
        f.write(f"**Coverage:** Next 7 days\n\n")
        
        f.write("---\n\n")
        
        # TODAY'S GAMES SECTION
        f.write(f"## 📅 TODAY'S GAMES - {today.strftime('%A, %B %d')}\n\n")
        
        if len(todays_games) == 0:
            f.write("*No games scheduled for today.*\n\n")
        else:
            f.write(f"**{len(todays_games)} game(s) today**\n\n")
            
            for idx, game in todays_games.iterrows():
                f.write(format_game_markdown(game))
                f.write("\n\n")
        
        f.write("---\n\n")
        
        # UPCOMING GAMES SECTION
        f.write("## 📆 UPCOMING GAMES (Next 7 Days)\n\n")
        
        if len(upcoming_games) == 0:
            f.write("*No upcoming games found in the next 7 days.*\n\n")
        else:
            # Group by date
            current_date = None
            rank_counter = 1
            total_upcoming = len(upcoming_games)
            
            for idx, game in upcoming_games.iterrows():
                game_date = game['game_date'].date()
                
                # New date header
                if current_date != game_date:
                    current_date = game_date
                    f.write(f"\n### 🗓️ {game['game_date'].strftime('%A, %B %d, %Y')}\n\n")
                
                f.write(format_game_markdown(game, rank_counter, total_upcoming))
                f.write("\n\n")
                rank_counter += 1
        
        f.write("---\n\n")
        
        # TOP MATCHUPS SUMMARY
        f.write("## 🌟 Top 5 Matchups This Week\n\n")
        top_5 = games_df.nlargest(5, 'matchup_score')
        
        for i, (idx, game) in enumerate(top_5.iterrows(), 1):
            date_str = game['game_date'].strftime('%a %m/%d')
            f.write(f"{i}. **{game['away_team']} @ {game['home_team']}** "
                   f"({date_str}) - Score: {game['matchup_score']:.1f}/100\n")
        
        f.write("\n---\n\n")
        
        # POWER RANKINGS
        f.write("## 📊 Current Power Rankings (Top 10)\n\n")
        f.write("| Rank | Team | Power Score | Record | Net Rating |\n")
        f.write("|------|------|-------------|--------|------------|\n")
        
        for idx, team in rankings_df.head(10).iterrows():
            f.write(f"| {int(team['rank'])} | {team['team']} | "
                   f"{team['power_score']:.1f} | "
                   f"{int(team['wins'])}-{int(team['losses'])} | "
                   f"{team['net_rating']:+.1f} |\n")
        
        f.write("\n---\n\n")
        
        # Methodology
        f.write("## 📈 Methodology\n\n")
        f.write("### Power Rankings\n")
        f.write("- **Win Percentage:** 35%\n")
        f.write("- **Net Rating:** 30%\n")
        f.write("- **Offensive Efficiency:** 20%\n")
        f.write("- **Defensive Efficiency:** 15%\n\n")
        
        f.write("### Matchup Scores\n")
        f.write("- **Quality Score:** Average power rating of both teams (0-100)\n")
        f.write("  - Higher scores indicate stronger teams overall\n")
        f.write("  - Typical range: 30-70 based on current team strengths\n\n")
        f.write("- **Competitive Score:** How evenly matched teams are (0-100)\n")
        f.write("  - Calculated using exponential decay: 100 × e^(-difference/15)\n")
        f.write("  - Perfect matchup (0 point difference) = 100\n")
        f.write("  - 10 point difference ≈ 51 (close game)\n")
        f.write("  - 20 point difference ≈ 26 (moderate mismatch)\n")
        f.write("  - 30+ point difference ≈ <15 (blowout likely)\n\n")
        f.write("- **Overall Matchup Score:** 60% quality + 40% competitiveness\n")
        f.write("  - Balances team strength with game competitiveness\n")
        f.write("  - Best games: strong teams that are evenly matched\n\n")
        
        f.write("### Watchability Tiers\n")
        f.write("- 🔥 **MUST WATCH** (70+): Elite matchups between top teams\n")
        f.write("- ⭐ **HIGHLY RECOMMENDED** (60-69): High-quality, competitive games\n")
        f.write("- 👍 **WORTH WATCHING** (50-59): Solid matchups\n")
        f.write("- 📺 **Optional** (<50): Lower-tier or lopsided games\n")
    
    print(f"\n✅ Report written to: {output_file}")


def main():
    """Main execution function"""
    print("\n" + "=" * 60)
    print("NBA MATCHUP ANALYSIS - OPTIMIZED VERSION")
    print("=" * 60 + "\n")
    
    try:
        # Step 1: Get games
        games_df = get_games_by_date_range(days_ahead=7)
        
        if games_df.empty:
            print("\n" + "=" * 60)
            print("NO GAMES FOUND")
            print("=" * 60)
            print("\nNo NBA games scheduled in the next 7 days.")
            print("This is likely due to:")
            print("  - NBA offseason (July - September)")
            print("  - All-Star break (mid-February)")
            print("  - Between regular season and playoffs")
            print("\nTry again during the NBA season (October - June)")
            print("=" * 60)
            return
        
        # Step 2: Calculate power rankings
        rankings_df = calculate_power_rankings()
        
        if rankings_df.empty:
            print("Could not calculate rankings. Exiting.")
            return
        
        # Step 3: Analyze matchups
        games_df = analyze_matchups(games_df, rankings_df)
        
        # Step 4: Write markdown report
        write_markdown_report(games_df, rankings_df)
        
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print("\n📄 Generated File: NBA_Weekly_Report.md")
        print("   - Today's games with scores (if completed)")
        print("   - Upcoming games ranked by watchability")
        print("   - Top 5 matchups summary")
        print("   - Current power rankings")
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()