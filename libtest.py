import nflreadpy as nfl
import pandas as pd

# Load the current season's schedule data
schedule_df = nfl.load_schedules(None)

# Filter for the current week's matchups (you would need to determine the current week)
# The library might have a function to determine the current week, or you can filter based on date.
# Example: schedule_df[schedule_df['week'] == current_week_number]

# Print or process the matchups
print("Current Week's Matchups:")
print(type(schedule_df))
