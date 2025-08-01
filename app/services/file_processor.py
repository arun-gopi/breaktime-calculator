"""
File processing service for timesheet data
"""
import pandas as pd
import os
from typing import Dict, Any

from app.services.break_calculator import calculate_break_time, calculate_actual_breaks
from app.services.audit_service import audit_break_entries
from app.core.database import db_manager


def process_uploaded_file(file_path: str, file_id: str, user_id: int) -> Dict[str, Any]:
    """Process the uploaded CSV file and generate break time calculations"""
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Validate required columns
        required_columns = ['ProviderId', 'ProviderFirstName', 'ProviderLastName', 'DateOfService', 'TimeWorkedInHours', 'ProcedureCode']
        optional_timing_columns = ['DateTimeFrom', 'DateTimeTo']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}. Please download the template to see the correct format.")
        
        # Check if timing columns are available for enhanced auditing
        has_timing_data = all(col in df.columns for col in optional_timing_columns)
        
        # Validate data types and format
        if df.empty:
            raise ValueError("The uploaded CSV file is empty. Please upload a file with data.")
        
        # Check for required data
        if df['ProviderId'].isnull().any():
            raise ValueError("ProviderId column contains empty values. All providers must have an ID.")
        
        if df['TimeWorkedInHours'].isnull().any():
            raise ValueError("TimeWorkedInHours column contains empty values. All entries must have hours worked.")
        
        # Try to convert TimeWorkedInHours to numeric
        try:
            df['TimeWorkedInHours'] = pd.to_numeric(df['TimeWorkedInHours'], errors='raise')
        except ValueError:
            raise ValueError("TimeWorkedInHours column contains non-numeric values. Please ensure all values are numbers (e.g., 8.5, 6.0).")
        
        # Create provider full name column
        df['ProviderFullName'] = df['ProviderFirstName'] + ' ' + df['ProviderLastName']

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
        
        # Run audit system to check for data integrity issues
        audit_results = audit_break_entries(df)
        
        # Add timing audit information to results if available
        if has_timing_data:
            timing_audit_summary = f"Enhanced timing analysis enabled using DateTimeFrom/DateTimeTo columns"
        else:
            timing_audit_summary = f"Basic audit only - DateTimeFrom/DateTimeTo columns not available for timing analysis"
        
        # Group by provider and date to calculate daily hours worked (excluding breaks)
        # Filter out break and lunch entries when calculating work hours
        work_entries = df[~df['ProcedureCode'].isin(['10 Minute Break', 'Lunch Break'])]
        daily_hours = work_entries.groupby(['ProviderId', 'ProviderFullName', 'DateOfService'])['TimeWorkedInHours'].sum().reset_index()
        
        # Calculate required break time for each day based on actual work hours
        daily_hours['RequiredBreakMinutes'] = daily_hours['TimeWorkedInHours'].apply(calculate_break_time)
        daily_hours['RequiredBreakHours'] = daily_hours['RequiredBreakMinutes'] / 60
        
        # Calculate actual breaks taken for each provider-date combination
        actual_breaks_data = []
        for _, row in daily_hours.iterrows():
            provider_id = row['ProviderId']
            date_of_service = row['DateOfService']
            
            # Filter data for this specific provider and date
            provider_day_data = df[(df['ProviderId'] == provider_id) & (df['DateOfService'] == date_of_service)]
            
            # Calculate actual breaks
            total_break_minutes, lunch_break_minutes = calculate_actual_breaks(provider_day_data)
            
            actual_breaks_data.append({
                'ProviderId': provider_id,
                'ProviderFullName': row['ProviderFullName'],
                'DateOfService': row['DateOfService'].strftime('%m/%d/%Y') if hasattr(row['DateOfService'], 'strftime') else str(row['DateOfService']),
                'TimeWorkedInHours': row['TimeWorkedInHours'],
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
        
        # Ensure DateOfService is properly formatted as date string for grouping
        if not daily_hours.empty and 'DateOfService' in daily_hours.columns:
            daily_hours['DateOfService'] = daily_hours['DateOfService'].astype(str)
        
        # Create provider-date summary report (grouped by provider by date)
        provider_date_summary = daily_hours.groupby(['ProviderId', 'ProviderFullName', 'DateOfService']).agg({
            'TimeWorkedInHours': 'sum',
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
        # Summary by provider (overall totals)
        provider_summary = daily_hours.groupby(['ProviderId', 'ProviderFullName']).agg({
            'TimeWorkedInHours': 'sum',
            'RequiredBreakMinutes': 'sum',
            'ActualBreakMinutes': 'sum',
            'LunchBreakMinutes': 'sum',
            'BreakDeficitMinutes': 'sum',
            'DateOfService': 'count'
        }).rename(columns={'DateOfService': 'Timesheet Count'}).reset_index()
        
        provider_summary['RequiredBreakHours'] = provider_summary['RequiredBreakMinutes'] / 60
        provider_summary['ActualBreakHours'] = provider_summary['ActualBreakMinutes'] / 60
        provider_summary['LunchBreakHours'] = provider_summary['LunchBreakMinutes'] / 60
        provider_summary['BreakDeficitHours'] = provider_summary['BreakDeficitMinutes'] / 60
        provider_summary['OverallCompliance'] = provider_summary['BreakDeficitMinutes'].apply(
            lambda x: 'Compliant' if x == 0 else 'Non-Compliant'
        )
        
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
        
        # Save audit results if any issues found
        if audit_results:
            audit_df = pd.DataFrame(audit_results)
            audit_df.to_csv(audit_output_path, index=False)
        else:
            # Create empty audit file with headers to indicate no issues found
            audit_df = pd.DataFrame(columns=['Type', 'ProviderId', 'ProviderName', 'DateOfService', 'Issue', 'Severity'])
            audit_df.to_csv(audit_output_path, index=False)

        # Update database with processing results
        db_manager.update_file_upload(
            file_id,
            daily_output_path=daily_output_path,
            summary_output_path=summary_output_path,
            provider_date_output_path=provider_date_output_path,
            audit_output_path=audit_output_path,
            processed=True,
            total_records=len(df),
            total_providers=df['ProviderId'].nunique(),
            date_range=date_range
        )

        return {
            'daily_data': daily_hours,
            'summary_data': provider_summary,
            'provider_date_data': provider_date_summary,
            'audit_results': audit_results,
            'audit_output_path': audit_output_path,
            'total_records': len(df),
            'total_providers': df['ProviderId'].nunique(),
            'date_range': date_range,
            'audit_issues_count': len(audit_results),
            'has_timing_data': has_timing_data,
            'timing_audit_summary': timing_audit_summary
        }
        
    except Exception as e:
        # Update database with error status
        db_manager.update_file_upload(file_id, processed=False)
        raise e
