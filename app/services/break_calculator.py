"""
Break time calculation services and business logic
"""
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any


def calculate_break_time(hours_worked: float) -> int:
    """
    Calculate required break time based on hours worked.
    
    Rules:
    - 3.5–6 hours: 1 break (10 minutes)
    - 6–10 hours: 2 breaks (20 minutes)
    - 10–14 hours: 3 breaks (30 minutes)
    
    Args:
        hours_worked: Number of hours worked
        
    Returns:
        Required break time in minutes
    """
    if hours_worked >= 10:
        return 3 * 10  # 3 breaks of 10 minutes each
    elif hours_worked >= 6:
        return 2 * 10  # 2 breaks of 10 minutes each
    elif hours_worked >= 3.5:
        return 1 * 10  # 1 break of 10 minutes
    else:
        return 0  # No break required


def calculate_actual_breaks(df_provider_day: pd.DataFrame) -> Tuple[int, int]:
    """
    Calculate actual breaks taken by checking ProcedureCode column.
    Returns tuple: (total_break_minutes, lunch_break_minutes) rounded to nearest minute
    
    Args:
        df_provider_day: DataFrame with provider's data for a specific day
        
    Returns:
        Tuple of (total_break_minutes, lunch_break_minutes)
    """
    total_break_minutes = 0
    lunch_break_minutes = 0
    
    if 'ProcedureCode' in df_provider_day.columns:
        # Calculate 10 minute breaks - sum the actual time from TimeWorkedInHours
        break_entries = df_provider_day[df_provider_day['ProcedureCode'] == '10 Minute Break']
        if not break_entries.empty:
            total_break_minutes = round(break_entries['TimeWorkedInHours'].sum() * 60)  # Convert hours to minutes and round
        
        # Calculate lunch breaks - sum the actual time from TimeWorkedInHours
        lunch_entries = df_provider_day[df_provider_day['ProcedureCode'] == 'Lunch Break']
        if not lunch_entries.empty:
            lunch_break_minutes = round(lunch_entries['TimeWorkedInHours'].sum() * 60)  # Convert hours to minutes and round
        
    return total_break_minutes, lunch_break_minutes
