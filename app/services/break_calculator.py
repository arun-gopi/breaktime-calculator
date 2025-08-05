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
        'break_threshold_1', 'break_threshold_2', 'break_threshold_3',
        'break_duration_1', 'break_duration_2', 'break_duration_3'
    ]
    
    defaults = {
        'break_threshold_1': 4.0,
        'break_threshold_2': 8.0,
        'break_threshold_3': 12.0,
        'break_duration_1': 10,
        'break_duration_2': 20,
        'break_duration_3': 30
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
        threshold_1 = db_manager.get_config_value('break_threshold_1', 4.0)
        threshold_2 = db_manager.get_config_value('break_threshold_2', 8.0)
        threshold_3 = db_manager.get_config_value('break_threshold_3', 12.0)
        
        duration_1 = db_manager.get_config_value('break_duration_1', 10)
        duration_2 = db_manager.get_config_value('break_duration_2', 20)
        duration_3 = db_manager.get_config_value('break_duration_3', 30)
    else:
        # Use pre-fetched configuration values
        threshold_1 = break_config.get('break_threshold_1', 4.0)
        threshold_2 = break_config.get('break_threshold_2', 8.0)
        threshold_3 = break_config.get('break_threshold_3', 12.0)
        
        duration_1 = break_config.get('break_duration_1', 10)
        duration_2 = break_config.get('break_duration_2', 20)
        duration_3 = break_config.get('break_duration_3', 30)
    
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
