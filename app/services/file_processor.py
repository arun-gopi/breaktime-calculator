"""
File processing service for timesheet data
"""
import pandas as pd
import os
from typing import Dict, Any, Optional

from app.services.break_calculator import calculate_break_time, calculate_actual_breaks, get_excluded_procedure_codes, calculate_total_hours_with_drive_time, get_break_configuration
from app.services.audit_service import audit_break_entries
from app.core.database import db_manager


def process_uploaded_file(file_path: str, file_id: str, user_id: int, progress_tracker=None) -> Dict[str, Any]:
    """Process the uploaded CSV file and generate break time calculations"""
    def update_progress(step: int, message: str):
        if progress_tracker:
            progress_tracker.update_progress(file_id, step, message)
    
    try:
        update_progress(5, "Reading CSV file...")
        
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        update_progress(10, "Validating file structure...")
        
        # Validate required columns
        required_columns = ['ProviderId', 'ProviderFirstName', 'ProviderLastName', 'DateOfService', 'TimeWorkedInHours', 'ProcedureCode']
        optional_timing_columns = ['DateTimeFrom', 'DateTimeTo']
        optional_drive_columns = ['DriveTimeMinutes']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}. Please download the template to see the correct format.")
        
        # Check if timing columns are available for enhanced auditing
        has_timing_data = all(col in df.columns for col in optional_timing_columns)
        has_drive_data = 'DriveTimeMinutes' in df.columns
        
        # Validate data types and format
        update_progress(15, "Validating data formats...")
        
        if df.empty:
            raise ValueError("The uploaded CSV file is empty. Please upload a file with data.")
        
        # Check for required data
        if df['ProviderId'].isnull().any():
            raise ValueError("ProviderId column contains empty values. All providers must have an ID.")
        
        if df['TimeWorkedInHours'].isnull().any():
            raise ValueError("TimeWorkedInHours column contains empty values. All entries must have hours worked.")
        
        update_progress(20, "Converting data types...")
        
        # Try to convert TimeWorkedInHours to numeric
        try:
            df['TimeWorkedInHours'] = pd.to_numeric(df['TimeWorkedInHours'], errors='raise')
        except ValueError:
            raise ValueError("TimeWorkedInHours column contains non-numeric values. Please ensure all values are numbers (e.g., 8.5, 6.0).")
        
        # Convert DriveTimeMinutes to numeric if the column exists
        if has_drive_data:
            try:
                df['DriveTimeMinutes'] = pd.to_numeric(df['DriveTimeMinutes'], errors='coerce').fillna(0)
                # Ensure no negative values
                df['DriveTimeMinutes'] = df['DriveTimeMinutes'].apply(lambda x: max(0, x))
            except ValueError:
                raise ValueError("DriveTimeMinutes column contains invalid values. Please ensure all values are numbers (e.g., 30, 45) or empty.")
        else:
            # Add DriveTimeMinutes column with zeros if it doesn't exist
            df['DriveTimeMinutes'] = 0
            has_drive_data = True  # Now we have the column
        
        # Create provider full name column
        df['ProviderFullName'] = df['ProviderFirstName'] + ' ' + df['ProviderLastName']

        update_progress(25, "Processing dates...")
        
        # Convert DateOfService to datetime and then to date format (mm/dd/yyyy) without time
        df['DateOfService'] = pd.to_datetime(df['DateOfService'], errors='coerce')
        
        # Convert to date-only format (removes time component)
        df['DateOfService'] = df['DateOfService'].dt.date
        
        # Convert back to datetime for processing but maintain date-only format
        df['DateOfService_datetime'] = pd.to_datetime(df['DateOfService']).dt.date
        
        # Calculate date range
        date_min = df['DateOfService_datetime'].min().strftime('%m/%d/%Y')
        date_max = df['DateOfService_datetime'].max().strftime('%m/%d/%Y')
        date_range = f"{date_min} to {date_max}"
        
        update_progress(30, "Running data quality audit...")
        
        # Run audit system to check for data integrity issues
        audit_results = audit_break_entries(df)
        
        # Add timing audit information to results if available
        if has_timing_data:
            timing_audit_summary = f"Enhanced timing analysis enabled using DateTimeFrom/DateTimeTo columns"
        else:
            timing_audit_summary = f"Basic audit only - DateTimeFrom/DateTimeTo columns not available for timing analysis"
        
        # Add drive time information to audit summary
        if has_drive_data and df['DriveTimeMinutes'].sum() > 0:
            drive_audit_summary = f"Drive time data included - Total drive time: {df['DriveTimeMinutes'].sum()} minutes"
        else:
            drive_audit_summary = f"No drive time data available or all values are zero"
        
        update_progress(35, "Calculating work hours by provider and date...")
        
        # Group by provider and date to calculate daily hours worked (excluding breaks)
        # Get excluded procedure codes from configuration
        excluded_codes = get_excluded_procedure_codes()
        
        # Filter out excluded entries when calculating work hours
        work_entries = df[~df['ProcedureCode'].isin(excluded_codes)]
        
        # Group by provider and date first
        grouped_data = []
        total_groups = len(df.groupby(['ProviderId', 'ProviderFullName', 'DateOfService']))
        current_group = 0
        
        for (provider_id, provider_name, date_of_service), group in df.groupby(['ProviderId', 'ProviderFullName', 'DateOfService']):
            current_group += 1
            if current_group % 50 == 0:  # Update progress every 50 groups
                progress = 35 + (current_group / total_groups) * 15  # Progress from 35% to 50%
                update_progress(int(progress), f"Processing provider groups... ({current_group}/{total_groups})")
            
            # Calculate total hours including drive time for this provider-date combination
            total_hours = calculate_total_hours_with_drive_time(group, excluded_codes)
            
            grouped_data.append({
                'ProviderId': provider_id,
                'ProviderFullName': provider_name,
                'DateOfService': date_of_service,
                'TimeWorkedInHours': total_hours
            })
        
        daily_hours = pd.DataFrame(grouped_data)
        
        update_progress(50, "Calculating required break times...")
        
        # Get break configuration once for performance optimization
        break_config = get_break_configuration()
        
        # Calculate required break time for each day based on actual work hours
        daily_hours['RequiredBreakMinutes'] = daily_hours['TimeWorkedInHours'].apply(
            lambda hours: calculate_break_time(hours, break_config)
        )
        daily_hours['RequiredBreakHours'] = daily_hours['RequiredBreakMinutes'] / 60
        
        update_progress(60, "Calculating actual breaks taken...")
        
        # Calculate actual breaks taken for each provider-date combination
        actual_breaks_data = []
        total_rows = len(daily_hours)
        
        for idx, (_, row) in enumerate(daily_hours.iterrows()):
            if idx % 10 == 0:  # Update progress every 10 rows
                progress = 60 + (idx / total_rows) * 15  # Progress from 60% to 75%
                update_progress(int(progress), f"Analyzing breaks... ({idx}/{total_rows} records)")
            
            provider_id = row['ProviderId']
            date_of_service = row['DateOfService']
            
            # Filter data for this specific provider and date
            provider_day_data = df[(df['ProviderId'] == provider_id) & (df['DateOfService'] == date_of_service)]
            
            # Calculate actual breaks
            total_break_minutes, lunch_break_minutes = calculate_actual_breaks(provider_day_data)
            
            # Calculate drive time for this provider-date combination
            # Only include drive time from non-excluded entries
            work_entries_day = provider_day_data[~provider_day_data['ProcedureCode'].isin(excluded_codes)]
            drive_time_minutes = work_entries_day['DriveTimeMinutes'].sum() if not work_entries_day.empty else 0
            
            # Calculate pure work hours (excluding drive time)
            work_hours_only = row['TimeWorkedInHours'] - (drive_time_minutes / 60.0)
            
            actual_breaks_data.append({
                'ProviderId': provider_id,
                'ProviderFullName': row['ProviderFullName'],
                'DateOfService': row['DateOfService'].strftime('%m/%d/%Y') if hasattr(row['DateOfService'], 'strftime') else str(row['DateOfService']),
                'TimeWorkedInHours': work_hours_only,
                'DriveTimeMinutes': drive_time_minutes,
                'DriveTimeHours': drive_time_minutes / 60.0,
                'TotalWorkedHours': row['TimeWorkedInHours'],  # This already includes drive time
                'RequiredBreakMinutes': row['RequiredBreakMinutes'],
                'RequiredBreakHours': row['RequiredBreakHours'],
                'ActualBreakMinutes': total_break_minutes,
                'ActualBreakHours': total_break_minutes / 60,
                'LunchBreakMinutes': lunch_break_minutes,
                'LunchBreakHours': lunch_break_minutes / 60,
                'BreakCompliance': 'Compliant' if total_break_minutes >= row['RequiredBreakMinutes'] else 'Non-Compliant',
                'BreakDeficitMinutes': max(0, row['RequiredBreakMinutes'] - total_break_minutes)
            })
        
        # Convert to DataFrame
        daily_hours = pd.DataFrame(actual_breaks_data)
        
        update_progress(75, "Generating summary reports...")
        
        # Ensure DateOfService is properly formatted as date string for grouping
        if not daily_hours.empty and 'DateOfService' in daily_hours.columns:
            daily_hours['DateOfService'] = daily_hours['DateOfService'].astype(str)
        
        # Create provider-date summary report (grouped by provider by date)
        provider_date_summary = daily_hours.groupby(['ProviderId', 'ProviderFullName', 'DateOfService']).agg({
            'TimeWorkedInHours': 'sum',
            'DriveTimeMinutes': 'sum',
            'DriveTimeHours': 'sum',
            'TotalWorkedHours': 'sum',
            'RequiredBreakMinutes': 'sum',
            'RequiredBreakHours': 'sum',
            'ActualBreakMinutes': 'sum',
            'ActualBreakHours': 'sum',
            'LunchBreakMinutes': 'sum',
            'LunchBreakHours': 'sum',
            'BreakDeficitMinutes': 'sum'
        }).reset_index()
        
        # Recalculate compliance for grouped data
        provider_date_summary['BreakCompliance'] = provider_date_summary['BreakDeficitMinutes'].apply(
            lambda x: 'Compliant' if x == 0 else 'Non-Compliant'
        )
        
        update_progress(80, "Calculating provider summaries...")
        
        # Summary by provider (overall totals)
        provider_summary = daily_hours.groupby(['ProviderId', 'ProviderFullName']).agg({
            'TimeWorkedInHours': 'sum',
            'DriveTimeMinutes': 'sum',
            'TotalWorkedHours': 'sum',
            'RequiredBreakMinutes': 'sum',
            'ActualBreakMinutes': 'sum',
            'LunchBreakMinutes': 'sum',
            'BreakDeficitMinutes': 'sum',
            'DateOfService': 'count'
        }).rename(columns={'DateOfService': 'Timesheet Count'}).reset_index()
        
        provider_summary['DriveTimeHours'] = provider_summary['DriveTimeMinutes'] / 60
        provider_summary['RequiredBreakHours'] = provider_summary['RequiredBreakMinutes'] / 60
        provider_summary['ActualBreakHours'] = provider_summary['ActualBreakMinutes'] / 60
        provider_summary['LunchBreakHours'] = provider_summary['LunchBreakMinutes'] / 60
        provider_summary['BreakDeficitHours'] = provider_summary['BreakDeficitMinutes'] / 60
        provider_summary['OverallCompliance'] = provider_summary['BreakDeficitMinutes'].apply(
            lambda x: 'Compliant' if x == 0 else 'Non-Compliant'
        )
        
        update_progress(85, "Generating output files...")
        
        # Save output files with user-specific directory
        user_output_dir = f"output/user_{user_id}"
        os.makedirs(user_output_dir, exist_ok=True)
        
        daily_output_path = f"{user_output_dir}/daily_break_calculation_{file_id}.csv"
        summary_output_path = f"{user_output_dir}/provider_break_summary_{file_id}.csv"
        provider_date_output_path = f"{user_output_dir}/provider_date_totals_{file_id}.csv"
        audit_output_path = f"{user_output_dir}/audit_report_{file_id}.csv"
        
        daily_hours.to_csv(daily_output_path, index=False)
        provider_summary.to_csv(summary_output_path, index=False)
        provider_date_summary.to_csv(provider_date_output_path, index=False)
        
        update_progress(90, "Saving audit results...")
        
        # Save audit results if any issues found
        if audit_results:
            audit_df = pd.DataFrame(audit_results)
            audit_df.to_csv(audit_output_path, index=False)
        else:
            # Create empty audit file with headers to indicate no issues found
            audit_df = pd.DataFrame(columns=['Type', 'ProviderId', 'ProviderName', 'DateOfService', 'Issue', 'Severity'])
            audit_df.to_csv(audit_output_path, index=False)

        update_progress(95, "Updating database...")

        # Update database with processing results
        db_manager.update_file_upload(
            file_id,
            daily_output_path=daily_output_path,
            summary_output_path=summary_output_path,
            provider_date_output_path=provider_date_output_path,
            audit_output_path=audit_output_path,
            processed=True,
            total_records=int(len(df)),
            total_providers=int(df['ProviderId'].nunique()),
            date_range=date_range
        )

        result = {
            'daily_data': daily_hours.to_dict('records') if not daily_hours.empty else [],
            'summary_data': provider_summary.to_dict('records') if not provider_summary.empty else [],
            'provider_date_data': provider_date_summary.to_dict('records') if not provider_date_summary.empty else [],
            'audit_results': audit_results,
            'audit_output_path': audit_output_path,
            'total_records': int(len(df)),
            'total_providers': int(df['ProviderId'].nunique()),
            'date_range': date_range,
            'audit_issues_count': len(audit_results),
            'has_timing_data': has_timing_data,
            'timing_audit_summary': timing_audit_summary,
            'has_drive_data': has_drive_data,
            'drive_audit_summary': drive_audit_summary
        }
        
        update_progress(100, "Processing completed successfully!")
        return result
        
    except Exception as e:
        # Update database with error status
        db_manager.update_file_upload(file_id, processed=False)
        # Update progress tracker if available
        if progress_tracker:
            progress_tracker.error_task(file_id, str(e))
        raise e
