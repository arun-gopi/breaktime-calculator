"""
Break time calculation services and business logic
"""
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional

from app.core.database import db_manager


def get_break_configuration() -> Dict[str, Any]:
    """
    Get all break-related configuration values in a single database call.
    
    Returns:
        Dictionary containing all break configuration values
    """
    config_keys = [
        'break_threshold_1', 'break_threshold_2', 'break_threshold_3', 'break_threshold_4',
        'break_duration_1', 'break_duration_2', 'break_duration_3', 'break_duration_4'
    ]
    
    defaults = {
        'break_threshold_1': 3.5,
        'break_threshold_2': 6.0,
        'break_threshold_3': 10.0,
        'break_threshold_4': 14.0,
        'break_duration_1': 10,
        'break_duration_2': 20,
        'break_duration_3': 30,
        'break_duration_4': 40
    }
    
    return db_manager.get_config_values(config_keys, defaults)


def calculate_break_time(hours_worked: float, break_config: Optional[Dict[str, Any]] = None) -> int:
    """
    Calculate required break time based on hours worked using configurable thresholds.
    
    Args:
        hours_worked: Number of hours worked
        break_config: Pre-fetched break configuration (for performance optimization)
        
    Returns:
        Required break time in minutes
    """
    if break_config is None:
        # Fallback to individual database calls if config not provided
        threshold_1 = db_manager.get_config_value('break_threshold_1', 3.5)
        threshold_2 = db_manager.get_config_value('break_threshold_2', 6.0)
        threshold_3 = db_manager.get_config_value('break_threshold_3', 10.0)
        threshold_4 = db_manager.get_config_value('break_threshold_4', 14.0)

        duration_1 = db_manager.get_config_value('break_duration_1', 10)
        duration_2 = db_manager.get_config_value('break_duration_2', 20)
        duration_3 = db_manager.get_config_value('break_duration_3', 30)
        duration_4 = db_manager.get_config_value('break_duration_4', 40)
    else:
        # Use pre-fetched configuration values
        threshold_1 = break_config.get('break_threshold_1', 3.5)
        threshold_2 = break_config.get('break_threshold_2', 6.0)
        threshold_3 = break_config.get('break_threshold_3', 10.0)
        threshold_4 = break_config.get('break_threshold_4', 14.0)

        duration_1 = break_config.get('break_duration_1', 10)
        duration_2 = break_config.get('break_duration_2', 20)
        duration_3 = break_config.get('break_duration_3', 30)
        duration_4 = break_config.get('break_duration_4', 40)

    if hours_worked >= threshold_4:
        return duration_4
    if hours_worked >= threshold_3:
        return duration_3
    elif hours_worked >= threshold_2:
        return duration_2
    elif hours_worked >= threshold_1:
        return duration_1
    else:
        return 0


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


def get_excluded_procedure_codes() -> List[str]:
    """
    Get the list of excluded procedure codes from configuration.
    
    Returns:
        List of procedure codes to exclude from work time calculations
    """
    return db_manager.get_config_value('excluded_procedure_codes', 
                                     ['Late Cancel by Client', '10 Minute Break', 'Lead BT', 'Lunch Break', 'Sick Leave'])


def calculate_total_hours_with_drive_time(df_provider_day: pd.DataFrame, excluded_codes: Optional[List[str]] = None) -> float:
    """
    Calculate total hours including drive time for a provider's day.
    Excludes procedure codes that are not considered work time.
    
    Args:
        df_provider_day: DataFrame with provider's data for a specific day
        excluded_codes: List of procedure codes to exclude (if None, will fetch from config)
        
    Returns:
        Total hours worked including drive time
    """
    if excluded_codes is None:
        excluded_codes = get_excluded_procedure_codes()
    
    # Filter out excluded procedure codes
    work_entries = df_provider_day[~df_provider_day['ProcedureCode'].isin(excluded_codes)]
    
    total_hours = 0.0
    
    # Sum TimeWorkedInHours for work entries
    if not work_entries.empty and 'TimeWorkedInHours' in work_entries.columns:
        total_hours += work_entries['TimeWorkedInHours'].sum()
    
    # Add DriveTimeMinutes if available, convert to hours
    if 'DriveTimeMinutes' in work_entries.columns:
        drive_time_hours = work_entries['DriveTimeMinutes'].sum() / 60.0
        total_hours += drive_time_hours
    
    return total_hours


def analyze_lunch_compliance(df_provider_day: pd.DataFrame, excluded_codes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Analyze California lunch timing compliance for a single provider-day.
    Rule: If an employee works 5+ hours, a 30-minute unpaid meal period must begin before the end of the 5th hour of work.

    Returns a dict with fields to merge into daily outputs and an optional audit issue text when non-compliant.
    """
    result: Dict[str, Any] = {
        'LunchTimingRequired': False,
        'LunchTimingCompliant': None,  # True/False/None (unknown)
        'LunchTimingStatus': 'Not required',
        'FirstWorkStart': None,
        'FirstLunchStart': None,
        'LunchDeadline': None,
        'CumulativeWorkBeforeLunchHours': None,
        'LunchFirstDurationMinutes': 0,
    }

    try:
        if excluded_codes is None:
            excluded_codes = get_excluded_procedure_codes()

        # Must have timing columns
        if not all(col in df_provider_day.columns for col in ['DateTimeFrom', 'DateTimeTo']):
            result['LunchTimingStatus'] = 'Insufficient timing data'
            return result

        df = df_provider_day.copy()
        # Parse datetimes
        df['DateTimeFrom_parsed'] = pd.to_datetime(df['DateTimeFrom'], errors='coerce')
        df['DateTimeTo_parsed'] = pd.to_datetime(df['DateTimeTo'], errors='coerce')

        # Filter work and lunch entries
        work_entries = df[~df['ProcedureCode'].isin(excluded_codes)].copy()
        lunch_entries = df[df['ProcedureCode'] == 'Lunch Break'].copy()

        # Ensure valid times
        work_entries = work_entries.dropna(subset=['DateTimeFrom_parsed', 'DateTimeTo_parsed'])
        lunch_entries = lunch_entries.dropna(subset=['DateTimeFrom_parsed', 'DateTimeTo_parsed'])

        if work_entries.empty:
            result['LunchTimingStatus'] = 'No work entries'
            return result

        # Determine if lunch is required (5+ hours of work during the day)
        # Use timing-based durations for accuracy
        work_total_seconds = ((work_entries['DateTimeTo_parsed'] - work_entries['DateTimeFrom_parsed']).apply(lambda x: x.total_seconds() if pd.notna(x) else 0)).clip(lower=0).sum()
        work_total_hours = work_total_seconds / 3600.0
        result['LunchTimingRequired'] = work_total_hours >= 5.0

        # Set first work start and deadline
        first_work_start = work_entries['DateTimeFrom_parsed'].min()
        if pd.notna(first_work_start):
            result['FirstWorkStart'] = first_work_start.strftime('%H:%M')
            deadline_dt = first_work_start + pd.Timedelta(hours=5)
            result['LunchDeadline'] = deadline_dt.strftime('%H:%M')

        if not result['LunchTimingRequired']:
            result['LunchTimingCompliant'] = True  # Not required implies compliant
            result['LunchTimingStatus'] = 'Not required (<5 hours worked)'
            return result

        # If required, assess lunch timing and duration
        if lunch_entries.empty:
            result['LunchTimingCompliant'] = False
            result['LunchTimingStatus'] = 'No lunch taken (required)'
            return result

        # First lunch occurrence
        first_lunch = lunch_entries.sort_values('DateTimeFrom_parsed').iloc[0]
        lunch_start = first_lunch['DateTimeFrom_parsed']
        lunch_end = first_lunch['DateTimeTo_parsed']
        if pd.isna(lunch_start) or pd.isna(lunch_end):
            result['LunchTimingCompliant'] = None
            result['LunchTimingStatus'] = 'Lunch timing unavailable'
            return result

        # Lunch duration minutes
        lunch_first_minutes = max(0.0, (lunch_end - lunch_start).total_seconds() / 60.0)
        result['LunchFirstDurationMinutes'] = int(round(lunch_first_minutes))
        result['FirstLunchStart'] = lunch_start.strftime('%H:%M')

        # Cumulative worked hours before lunch start
        work_before = work_entries[work_entries['DateTimeFrom_parsed'] < lunch_start].copy()
        if not work_before.empty:
            clipped = work_before.copy()
            clipped['clipped_end'] = clipped['DateTimeTo_parsed'].apply(lambda t: min(t, lunch_start))
            clipped_seconds = ((clipped['clipped_end'] - clipped['DateTimeFrom_parsed']).apply(lambda x: x.total_seconds() if pd.notna(x) else 0)).clip(lower=0)
            cumulative_hours = clipped_seconds.sum() / 3600.0
        else:
            cumulative_hours = 0.0
        result['CumulativeWorkBeforeLunchHours'] = round(cumulative_hours, 2)

        # Compliance checks
        timing_ok = cumulative_hours <= 5.0 + 1e-6  # allow tiny epsilon
        duration_ok = lunch_first_minutes >= 30.0
        result['LunchTimingCompliant'] = bool(timing_ok and duration_ok)

        if result['LunchTimingCompliant']:
            result['LunchTimingStatus'] = 'Compliant'
        else:
            # Build status message
            reasons = []
            if not timing_ok:
                reasons.append(f'lunch started after 5 hours of work ({cumulative_hours:.2f}h)')
            if not duration_ok:
                reasons.append(f'lunch under 30 minutes ({result["LunchFirstDurationMinutes"]}m)')
            result['LunchTimingStatus'] = 'Non-compliant: ' + '; '.join(reasons)

        return result
    except Exception:
        # Don't break processing on errors; mark unknown
        result['LunchTimingCompliant'] = None
        result['LunchTimingStatus'] = 'Error analyzing lunch timing'
        return result
