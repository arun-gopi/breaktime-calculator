"""
Audit system for break time validation and timing analysis
"""
import pandas as pd
from typing import List, Dict, Any


def audit_break_entries(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Audit system to check if break entries are properly categorized and not counted as work hours.
    Analyzes break timing positions using DateTimeFrom and DateTimeTo columns.
    Returns a list of audit findings/issues.
    
    Args:
        df: DataFrame with timesheet data
        
    Returns:
        List of audit issues found
    """
    audit_issues = []
    
    if 'ProcedureCode' not in df.columns:
        return audit_issues
    
    # Check if timing columns are available for enhanced auditing
    has_timing_data = all(col in df.columns for col in ['DateTimeFrom', 'DateTimeTo'])
    
    # Check for break entries that might be miscategorized
    break_entries = df[df['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])].copy()
    
    if not break_entries.empty:
        # Group by provider and date to check for potential issues
        for provider_id in break_entries['ProviderId'].unique():
            provider_breaks = break_entries[break_entries['ProviderId'] == provider_id]
            
            for date_service in provider_breaks['DateOfService'].unique():
                date_breaks = provider_breaks[provider_breaks['DateOfService'] == date_service]
                
                # Check if break times are reasonable
                for _, break_entry in date_breaks.iterrows():
                    break_hours = break_entry['TimeWorkedInHours']
                    break_type = break_entry['ProcedureCode']
                    provider_name = f"{break_entry.get('ProviderFirstName', '')} {break_entry.get('ProviderLastName', '')}"
                    
                    # Flag suspicious break durations
                    if break_type == '10 Minute Break':
                        if break_hours > 0.5:  # More than 30 minutes for a 10-minute break
                            audit_issues.append({
                                'Type': 'Suspicious Break Duration',
                                'ProviderId': provider_id,
                                'ProviderName': provider_name,
                                'DateOfService': date_service,
                                'Issue': f'10 Minute Break recorded as {break_hours:.2f} hours ({break_hours*60:.0f} minutes)',
                                'Severity': 'Medium'
                            })
                        elif break_hours < 0.1:  # Less than 6 minutes for a 10-minute break
                            audit_issues.append({
                                'Type': 'Short Break Duration',
                                'ProviderId': provider_id,
                                'ProviderName': provider_name,
                                'DateOfService': date_service,
                                'Issue': f'10 Minute Break recorded as only {break_hours:.2f} hours ({break_hours*60:.0f} minutes)',
                                'Severity': 'Low'
                            })
                    
                    elif break_type == 'Lunch Break':
                        if break_hours > 2.0:  # More than 2 hours for lunch
                            audit_issues.append({
                                'Type': 'Long Lunch Duration',
                                'ProviderId': provider_id,
                                'ProviderName': provider_name,
                                'DateOfService': date_service,
                                'Issue': f'Lunch Break recorded as {break_hours:.2f} hours ({break_hours*60:.0f} minutes)',
                                'Severity': 'Medium'
                            })
                        elif break_hours < 0.25:  # Less than 15 minutes for lunch
                            audit_issues.append({
                                'Type': 'Short Lunch Duration',
                                'ProviderId': provider_id,
                                'ProviderName': provider_name,
                                'DateOfService': date_service,
                                'Issue': f'Lunch Break recorded as only {break_hours:.2f} hours ({break_hours*60:.0f} minutes)',
                                'Severity': 'Low'
                            })
    
    # Enhanced timing analysis if DateTimeFrom and DateTimeTo are available
    if has_timing_data:
        audit_issues.extend(audit_break_timing_positions(df))
    
    # Check for potential data integrity issues
    all_entries = df.copy()
    
    # Group by provider and date to check for consistency
    for provider_id in all_entries['ProviderId'].unique():
        provider_data = all_entries[all_entries['ProviderId'] == provider_id]
        
        for date_service in provider_data['DateOfService'].unique():
            date_data = provider_data[provider_data['DateOfService'] == date_service]
            
            # Check if work entries and break entries have consistent patterns
            work_entries = date_data[~date_data['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])]
            break_entries_day = date_data[date_data['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])]
            
            total_work_hours = work_entries['TimeWorkedInHours'].sum()
            total_break_hours = break_entries_day['TimeWorkedInHours'].sum()
            
            provider_name = f"{date_data.iloc[0].get('ProviderFirstName', '')} {date_data.iloc[0].get('ProviderLastName', '')}"
            
            # Flag if someone has excessive break time compared to work time
            if total_work_hours > 0 and total_break_hours > (total_work_hours * 0.3):  # Break time more than 30% of work time
                audit_issues.append({
                    'Type': 'Excessive Break Time',
                    'ProviderId': provider_id,
                    'ProviderName': provider_name,
                    'DateOfService': date_service,
                    'Issue': f'Break time ({total_break_hours:.2f}h) is {(total_break_hours/total_work_hours)*100:.1f}% of work time ({total_work_hours:.2f}h)',
                    'Severity': 'High'
                })
            
            # Flag if work hours are very low but breaks are recorded
            if total_work_hours < 2.0 and total_break_hours > 0:
                audit_issues.append({
                    'Type': 'Low Work Hours with Breaks',
                    'ProviderId': provider_id,
                    'ProviderName': provider_name,
                    'DateOfService': date_service,
                    'Issue': f'Only {total_work_hours:.2f} work hours but {total_break_hours:.2f} break hours recorded',
                    'Severity': 'Medium'
                })
    
    return audit_issues


def audit_break_timing_positions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Audit break timing positions using DateTimeFrom and DateTimeTo columns.
    Checks if breaks occur at appropriate times (middle of sessions vs end of sessions).
    
    Args:
        df: DataFrame with timesheet data including DateTimeFrom and DateTimeTo
        
    Returns:
        List of timing-related audit issues
    """
    timing_audit_issues = []
    
    if not all(col in df.columns for col in ['DateTimeFrom', 'DateTimeTo']):
        return timing_audit_issues
    
    try:
        # Convert timing columns to datetime
        df = df.copy()
        df['DateTimeFrom_parsed'] = pd.to_datetime(df['DateTimeFrom'], errors='coerce')
        df['DateTimeTo_parsed'] = pd.to_datetime(df['DateTimeTo'], errors='coerce')
        
        # Group by provider and date for timing analysis
        for provider_id in df['ProviderId'].unique():
            provider_data = df[df['ProviderId'] == provider_id]
            
            for date_service in provider_data['DateOfService'].unique():
                date_data = provider_data[provider_data['DateOfService'] == date_service].copy()
                
                # Sort by start time to analyze session flow
                date_data = date_data.sort_values('DateTimeFrom_parsed')
                
                # Get work entries and break entries separately
                work_entries = date_data[~date_data['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])]
                break_entries = date_data[date_data['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])]
                
                if break_entries.empty or work_entries.empty:
                    continue
                
                provider_name = f"{date_data.iloc[0].get('ProviderFirstName', '')} {date_data.iloc[0].get('ProviderLastName', '')}"
                
                # Analyze each break entry
                for _, break_entry in break_entries.iterrows():
                    break_start = break_entry['DateTimeFrom_parsed']
                    break_end = break_entry['DateTimeTo_parsed']
                    break_type = break_entry['ProcedureCode']
                    
                    if pd.isna(break_start) or pd.isna(break_end):
                        continue
                    
                    # Check break positioning relative to work sessions
                    break_position = analyze_break_position(break_start, break_end, work_entries, date_data)
                    
                    # Flag issues based on break positioning
                    if break_position['type'] == 'isolated':
                        timing_audit_issues.append({
                            'Type': 'Isolated Break Entry',
                            'ProviderId': provider_id,
                            'ProviderName': provider_name,
                            'DateOfService': date_service,
                            'Issue': f'{break_type} appears isolated from work sessions ({break_start.strftime("%H:%M")} - {break_end.strftime("%H:%M")})',
                            'Severity': 'Medium'
                        })
                    
                    elif break_position['type'] == 'end_of_day':
                        timing_audit_issues.append({
                            'Type': 'Break at End of Day',
                            'ProviderId': provider_id,
                            'ProviderName': provider_name,
                            'DateOfService': date_service,
                            'Issue': f'{break_type} occurs at end of work day ({break_start.strftime("%H:%M")} - {break_end.strftime("%H:%M")})',
                            'Severity': 'Low'
                        })
                    
                    elif break_position['type'] == 'overlapping':
                        timing_audit_issues.append({
                            'Type': 'Overlapping Break and Work',
                            'ProviderId': provider_id,
                            'ProviderName': provider_name,
                            'DateOfService': date_service,
                            'Issue': f'{break_type} overlaps with work session ({break_start.strftime("%H:%M")} - {break_end.strftime("%H:%M")})',
                            'Severity': 'High'
                        })
                    
                    elif break_position['type'] == 'back_to_back_breaks':
                        timing_audit_issues.append({
                            'Type': 'Back-to-Back Breaks',
                            'ProviderId': provider_id,
                            'ProviderName': provider_name,
                            'DateOfService': date_service,
                            'Issue': f'{break_type} occurs immediately after another break ({break_start.strftime("%H:%M")} - {break_end.strftime("%H:%M")})',
                            'Severity': 'Medium'
                        })
                    
                    # Check for unreasonably long gaps between work and breaks
                    if break_position.get('gap_before_minutes', 0) > 60:
                        timing_audit_issues.append({
                            'Type': 'Long Gap Before Break',
                            'ProviderId': provider_id,
                            'ProviderName': provider_name,
                            'DateOfService': date_service,
                            'Issue': f'{break_type} has {break_position["gap_before_minutes"]:.0f} minute gap from previous work session',
                            'Severity': 'Low'
                        })
                
    except Exception as e:
        # If timing analysis fails, add a general note but don't break the audit
        timing_audit_issues.append({
            'Type': 'Timing Analysis Error',
            'ProviderId': 'N/A',
            'ProviderName': 'System',
            'DateOfService': 'N/A',
            'Issue': f'Could not analyze break timing positions: {str(e)}',
            'Severity': 'Low'
        })
    
    return timing_audit_issues


def analyze_break_position(break_start, break_end, work_entries, all_entries) -> Dict[str, Any]:
    """
    Analyze the position of a break relative to work sessions.
    Returns information about break positioning.
    
    Args:
        break_start: Break start datetime
        break_end: Break end datetime
        work_entries: DataFrame of work entries
        all_entries: DataFrame of all entries for the day
        
    Returns:
        Dictionary with break position analysis
    """
    position_info = {'type': 'normal', 'gap_before_minutes': 0, 'gap_after_minutes': 0}
    
    if work_entries.empty:
        position_info['type'] = 'isolated'
        return position_info
    
    # Get all entries sorted by time
    all_sorted = all_entries.sort_values('DateTimeFrom_parsed')
    
    # Find work sessions before and after this break
    work_before = work_entries[work_entries['DateTimeTo_parsed'] <= break_start]
    work_after = work_entries[work_entries['DateTimeFrom_parsed'] >= break_end]
    
    # Check for overlapping work sessions
    overlapping_work = work_entries[
        (work_entries['DateTimeFrom_parsed'] < break_end) & 
        (work_entries['DateTimeTo_parsed'] > break_start)
    ]
    
    if not overlapping_work.empty:
        position_info['type'] = 'overlapping'
        return position_info
    
    # Check if break is isolated (no work before or after)
    if work_before.empty and work_after.empty:
        position_info['type'] = 'isolated'
        return position_info
    
    # Check if break is at end of day (no work after)
    if work_after.empty and not work_before.empty:
        position_info['type'] = 'end_of_day'
        return position_info
    
    # Check for back-to-back breaks
    break_entries_around = all_entries[
        (all_entries['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])) &
        (all_entries['DateTimeFrom_parsed'] != break_start)  # Exclude current break
    ]
    
    # Check for breaks immediately before or after
    for _, other_break in break_entries_around.iterrows():
        other_start = other_break['DateTimeFrom_parsed']
        other_end = other_break['DateTimeTo_parsed']
        
        # If another break ends when this one starts, or starts when this one ends
        if (abs((other_end - break_start).total_seconds()) < 300) or \
           (abs((break_end - other_start).total_seconds()) < 300):  # Within 5 minutes
            position_info['type'] = 'back_to_back_breaks'
            return position_info
    
    # Calculate gaps
    if not work_before.empty:
        last_work_end = work_before['DateTimeTo_parsed'].max()
        gap_before = (break_start - last_work_end).total_seconds() / 60
        position_info['gap_before_minutes'] = gap_before
    
    if not work_after.empty:
        next_work_start = work_after['DateTimeFrom_parsed'].min()
        gap_after = (next_work_start - break_end).total_seconds() / 60
        position_info['gap_after_minutes'] = gap_after
    
    return position_info
