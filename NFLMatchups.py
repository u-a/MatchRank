#!/usr/bin/env python3
"""
NFL Matchup Analysis Script - Optimized Version
Analyzes NFL games for today and upcoming week with enhanced readability
"""

import nfl_data_py as nfl
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import warnings
warnings.filterwarnings('ignore')


def get_games_by_date_range(days_ahead=7):
    """
    Fetch NFL games from today through the next N days
    Returns a DataFrame with game information
    """
    print(f"Fetching NFL games for the next {days_ahead + 1} days...")
    
    current_year = datetime.now().year
    schedules = nfl.import_schedules([current_year])
    
    # Filter for games in date range
    today = datetime.now().date()
    cutoff_date = today + timedelta(days=days_ahead)
    
    schedules['gameday'] = pd.to_datetime(schedules['gameday'])
    schedules['game_date'] = schedules['gameday'].dt.date
    
    upcoming = schedules[
        (schedules['game_date'] >= today) & 
        (schedules['game_date'] <= cutoff_date)
    ].copy()
    
    # Check if any games found
    if len(upcoming) == 0:
        print(f"No games found between {today} and {cutoff_date}")
        return pd.DataFrame()  # Return empty DataFrame
    
    # Sort by date
    upcoming = upcoming.sort_values('gameday')
    
    # Select relevant columns
    games_df = upcoming[[
        'game_id', 'gameday', 'gametime', 'away_team', 'home_team', 
        'away_score', 'home_score', 'week'
    ]].copy()
    
    # Add is_today flag
    games_df['is_today'] = games_df['gameday'].dt.date == today
    
    # Deduplicate by game_id to prevent duplicates
    games_df = games_df.drop_duplicates(subset=['game_id'], keep='first').reset_index(drop=True)
    
    print(f"Found {len(games_df)} total games")
    return games_df


def calculate_power_rankings():
    """Calculate team power rankings using modified Pythagorean expectation"""
    print("\nCalculating team power rankings...")
    
    current_year = datetime.now().year
    schedules = nfl.import_schedules([current_year])
    
    # Filter for completed games only
    completed = schedules[schedules['home_score'].notna()].copy()
    
    if len(completed) == 0:
        print("\nWarning: No completed games found. Using previous season data.")
        schedules = nfl.import_schedules([current_year - 1])
        completed = schedules[schedules['home_score'].notna()].copy()
    
    print(f"Analyzing {len(completed)} completed games from {current_year} season")
    
    # Get all unique teams
    teams = pd.concat([completed['home_team'], completed['away_team']]).unique()
    
    # Calculate statistics for each team
    team_stats = {}
    
    for team in teams:
        # Home and away games
        home_games = completed[completed['home_team'] == team]
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
    
    print(f"Power rankings calculated for {len(rankings_df)} teams")
    return rankings_df


def analyze_matchups(games_df, rankings_df):
    """
    Analyze each game and determine watchability
    Returns games_df with added analysis columns
    """
    if rankings_df.empty or games_df.empty:
        return games_df
    
    # Create lookup dictionaries
    rank_dict = rankings_df.set_index('team')['power_score'].to_dict()
    team_rank_dict = rankings_df.set_index('team')['rank'].to_dict()
    
    # Add analysis for each game
    games_df['away_power'] = games_df['away_team'].map(rank_dict).fillna(50)
    games_df['home_power'] = games_df['home_team'].map(rank_dict).fillna(50)
    games_df['away_rank'] = games_df['away_team'].map(team_rank_dict).fillna(16)
    games_df['home_rank'] = games_df['home_team'].map(team_rank_dict).fillna(16)
    
    # Calculate matchup quality scores
    games_df['quality_score'] = (games_df['away_power'] + games_df['home_power']) / 2
    
    # IMPROVED: Calculate competitiveness with exponential decay
    # Better spread across 0-100 range compared to linear formula
    score_diff = abs(games_df['away_power'] - games_df['home_power'])
    games_df['competitive_score'] = 100 * np.exp(-score_diff / 15)
    
    # Overall matchup score: 60% quality, 40% competitiveness
    games_df['matchup_score'] = (0.60 * games_df['quality_score'] + 
                                   0.40 * games_df['competitive_score'])
    
    # Determine watchability tier
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
    games_df = games_df.sort_values(['gameday', 'matchup_score'], 
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
    
    # Game matchup - check for completed games
    has_scores = (pd.notna(row['away_score']) and pd.notna(row['home_score']))
    
    game_time = row['gametime'] if pd.notna(row['gametime']) else 'TBD'
    
    if has_scores:
        # Completed game with scores
        lines.append(f"**{row['away_team']} {int(row['away_score'])} @ "
                    f"{row['home_team']} {int(row['home_score'])}** - Final")
    else:
        # Upcoming game
        lines.append(f"**{row['away_team']} @ {row['home_team']}** - {game_time}")
    
    # Week and rankings
    lines.append(f"- **Week {int(row['week'])}**")
    lines.append(f"- **Team Rankings:** #{int(row['away_rank'])} {row['away_team']} vs "
                f"#{int(row['home_rank'])} {row['home_team']}")
    lines.append(f"- **Matchup Score:** {row['matchup_score']:.1f}/100 "
                f"(Quality: {row['quality_score']:.1f}, Competitive: {row['competitive_score']:.1f})")
    
    return "\n".join(lines)


def write_markdown_report(games_df, rankings_df, output_file='NFL_Weekly_Report.md'):
    """Write comprehensive markdown report"""
    
    today = datetime.now()
    current_year = today.year
    
    # Separate today's games from upcoming
    todays_games = games_df[games_df['is_today'] == True]
    upcoming_games = games_df[games_df['is_today'] == False]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# 🏈 NFL Weekly Matchup Report\n\n")
        f.write(f"**Season:** {current_year}  \n")
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
                game_date = game['gameday'].date()
                
                # New date header
                if current_date != game_date:
                    current_date = game_date
                    f.write(f"\n### 🗓️ {game['gameday'].strftime('%A, %B %d, %Y')}\n\n")
                
                f.write(format_game_markdown(game, rank_counter, total_upcoming))
                f.write("\n\n")
                rank_counter += 1
        
        f.write("---\n\n")
        
        # TOP MATCHUPS SUMMARY
        f.write("## 🌟 Top 5 Matchups This Week\n\n")
        top_5 = games_df.nlargest(5, 'matchup_score')
        
        for i, (idx, game) in enumerate(top_5.iterrows(), 1):
            date_str = game['gameday'].strftime('%a %m/%d')
            game_time = game['gametime'] if pd.notna(game['gametime']) else 'TBD'
            f.write(f"{i}. **{game['away_team']} @ {game['home_team']}** "
                   f"({date_str} {game_time}) - Score: {game['matchup_score']:.1f}/100\n")
        
        f.write("\n---\n\n")
        
        # POWER RANKINGS
        f.write("## 📊 Current Power Rankings (Top 10)\n\n")
        f.write("| Rank | Team | Power Score | Record | Pt Diff |\n")
        f.write("|------|------|-------------|--------|----------|\n")
        
        for idx, team in rankings_df.head(10).iterrows():
            f.write(f"| {int(team['rank'])} | {team['team']} | "
                   f"{team['power_score']:.1f} | "
                   f"{int(team['wins'])}-{int(team['losses'])} | "
                   f"{team['point_diff']:+.0f} |\n")
        
        f.write("\n---\n\n")
        
        # Methodology
        f.write("## 📈 Methodology\n\n")
        f.write("### Power Rankings\n")
        f.write("- **Modified Pythagorean Expectation:** 40% (exponent 2.37 for NFL)\n")
        f.write("- **Win Percentage:** 30%\n")
        f.write("- **Point Differential:** 30% (normalized)\n\n")
        
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
    print("NFL MATCHUP ANALYSIS - OPTIMIZED VERSION")
    print("=" * 60 + "\n")
    
    try:
        # Step 1: Get games
        games_df = get_games_by_date_range(days_ahead=7)
        
        if games_df.empty:
            print("\n" + "=" * 60)
            print("NO GAMES FOUND")
            print("=" * 60)
            print("\nNo NFL games scheduled in the next 7 days.")
            print("This is likely due to:")
            print("  - NFL offseason (February - August)")
            print("  - Bye week for all teams")
            print("  - Between regular season and playoffs")
            print("\nTry again during the NFL season (September - February)")
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
        print("\n📄 Generated File: NFL_Weekly_Report.md")
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