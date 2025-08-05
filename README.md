# Break Time Calculator

A FastAPI web application that calculates required break times for employees based on labor law requirements and timesheet data.

## 🎯 Purpose

This open-source application helps organizations comply with labor regulations by automatically calculating mandatory rest breaks for employees based on their work hours. It's designed to be generic and adaptable to various labor law requirements.

## Overview

This calculator processes timesheet CSV data through a user-friendly web interface and calculates mandatory rest breaks for each provider according to labor regulations. It features file upload, processing, and download capabilities with a modern, responsive design.

## Features

- 🔐 **User Authentication**: Secure login/registration system with session management  
- 🌐 **Web Interface**: Modern, responsive web application
- 📁 **File Upload**: Drag-and-drop CSV file upload
- 📊 **Real-time Processing**: Instant calculation results
- 💾 **PostgreSQL Database**: Robust database with user isolation
- 📥 **Download Reports**: Generate and download detailed CSV reports
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🎨 **Modern UI**: Clean interface with Tailwind CSS
- 📈 **Data Preview**: View sample results before downloading
- 👤 **User Isolation**: Each user can only access their own files and history
- 🔍 **Audit System**: Enhanced break time validation and timing analysis
- 🏗️ **Modular Architecture**: Clean FastAPI project structure with separation of concerns

## Break Time Rules

The calculator follows these break time requirements:

- **>4 hours worked**: 1 break (10 minutes)
- **>8 hours worked**: 2 breaks (20 minutes total)
- **>12 hours worked**: 3 breaks (30 minutes total)
- **Less than 4 hours**: No break required

*Note: Employees are entitled to a paid 10-minute rest break for every 4 hours worked or major fraction thereof.*

## 🏗️ Architecture

This application follows FastAPI best practices with a clean, modular architecture:

### Application Structure
- **`app/main.py`**: FastAPI application entry point and configuration
- **`app/api/routes/`**: API route definitions organized by functionality
- **`app/core/`**: Core application components (config, database, auth)
- **`app/services/`**: Business logic and data processing services
- **`app/models/`**: Data models and schemas (extensible for future use)
- **`app/utils/`**: Utility functions and helpers (extensible for future use)

### Key Design Principles
- **Separation of Concerns**: Clear separation between API routes, business logic, and data access
- **Dependency Injection**: FastAPI's dependency injection for authentication and database access
- **Service Layer Pattern**: Business logic encapsulated in service classes
- **Configuration Management**: Environment-based configuration with secure defaults
- **User Isolation**: Complete data separation between users at the database level

## 🔧 Customization

This application is designed to be easily customizable for different labor law requirements:

### Break Time Rules
The break calculation logic is in the `calculate_break_time()` function in `app.py`. You can modify this function to match your local labor regulations.

### CSV Format
The application expects specific CSV columns but can be adapted for different timesheet formats by modifying the `process_uploaded_file()` function.

### Branding
All styling uses standard Tailwind CSS classes and can be easily customized by modifying the template files in the `templates/` directory.

## Requirements

- Python 3.12+
- uv package manager (recommended) or pip
- FastAPI
- Pandas
- PostgreSQL database
- psycopg2-binary (PostgreSQL adapter)
- Uvicorn (ASGI server)

## Quick Start

### Option 1: Using uv (Recommended)
1. Install uv if you haven't: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Unix) or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows)
2. Run the startup script:
   - **Windows**: Double-click `start.bat`
   - **Unix/Mac**: Run `./start.sh`
3. Open your browser to http://127.0.0.1:8000

### Option 2: Manual Installation with uv
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Start the web server:
   ```bash
   uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

### Option 3: Using pip (Legacy)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the web server:
   ```bash
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
3. Open your browser to http://localhost:8000

> **Note**: This project has been restructured to follow FastAPI best practices. The old `app.py` has been reorganized into a modular structure under the `app/` directory. All existing functionality remains the same, but the codebase is now more maintainable and scalable.

## Usage

### Web Interface
1. **Upload File**: Go to the home page and upload your timesheet CSV
2. **View Results**: See processing results with summary statistics
3. **Download Reports**: Download detailed daily breakdown or provider summary
4. **View History**: Access previously processed files in the History section

### Command Line (Legacy)
```bash
python main.py
```

## Input Data Format

The timesheet CSV should contain these columns:
- `ProviderId`: Unique identifier for each provider
- `ProviderFirstName`: Provider's first name
- `ProviderLastName`: Provider's last name
- `DateOfService`: Date of work (MM/DD/YYYY format)
- `DateTimeFrom`: Start time of each entry (MM/DD/YYYY HH:MM format)
- `DateTimeTo`: End time of each entry (MM/DD/YYYY HH:MM format)
- `TimeWorkedInHours`: Hours worked (decimal format)
- `ProcedureCode`: Description of work type or break type (e.g., "Regular Time", "10 Minute Break", "Lunch Break")

## Output Files

The web application generates two types of reports:

### Output Files

The web application generates four types of reports:

### 1. Daily Breakdown Report
- **File**: `daily_break_calculation_[id].csv`
- **Contains**: Detailed daily break calculations for each provider
- **Columns**: ProviderId, ProviderFullName, DateOfService, TimeWorkedInHours, RequiredBreakMinutes, RequiredBreakHours, ActualBreakMinutes, BreakCompliance

### 2. Provider Summary Report
- **File**: `provider_break_summary_[id].csv`
- **Contains**: Summary totals by provider across all dates
- **Columns**: ProviderId, ProviderFullName, TimeWorkedInHours (total), RequiredBreakMinutes (total), ActualBreakMinutes (total), BreakDeficitMinutes, OverallCompliance

### 3. Provider Date Totals Report
- **File**: `provider_date_totals_[id].csv`
- **Contains**: Daily totals grouped by provider and date
- **Columns**: ProviderId, ProviderFullName, DateOfService, TimeWorkedInHours, RequiredBreakMinutes, ActualBreakMinutes, BreakCompliance

### 4. Audit Report
- **File**: `audit_report_[id].csv`
- **Contains**: Data quality issues and timing analysis findings
- **Columns**: Type, ProviderId, ProviderName, DateOfService, Issue, Severity

## Web Interface Features

### Home Page
- Clean, modern interface with drag-and-drop file upload
- Break time rules clearly displayed
- Required CSV column specifications

### Results Page
- Processing summary with key statistics
- Data preview showing top providers
- Download buttons for both report types

### History Page
- View all previously processed files
- Download reports from past uploads (daily, summary, provider-date, and audit reports)
- Processing status indicators
- Complete audit trail of all uploads

## API Endpoints

- `GET /` - Home page with upload form
- `POST /upload` - Handle file upload and processing
- `GET /download/{file_type}/{file_id}` - Download generated reports
- `GET /history` - View upload history

## Project Structure

```
breaktime-calculator/
├── app/                             # Main application package
│   ├── main.py                      # FastAPI application entry point
│   ├── __init__.py                  # Package initialization
│   ├── api/                         # API layer
│   │   ├── __init__.py              # API package init
│   │   └── routes/                  # Route definitions
│   │       ├── __init__.py          # Routes package init
│   │       ├── auth.py              # Authentication routes
│   │       ├── upload.py            # File upload routes
│   │       └── files.py             # File management routes
│   ├── core/                        # Core application components
│   │   ├── __init__.py              # Core package init
│   │   ├── config.py                # Configuration management
│   │   ├── database.py              # Database abstraction layer
│   │   └── auth.py                  # Authentication utilities
│   └── services/                    # Business logic services
│       ├── __init__.py              # Services package init
│       ├── break_calculator.py      # Break time calculation logic
│       ├── audit_service.py         # Audit and validation services
│       └── file_processor.py        # File processing services
├── templates/                       # Jinja2 HTML templates
│   ├── base.html                    # Base template with navigation
│   ├── index.html                   # Home page with upload form
│   ├── results.html                 # Results page with download options
│   ├── history.html                 # Upload history page
│   ├── login.html                   # Login page
│   ├── register.html                # Registration page
│   └── error.html                   # Error handling page
├── static/                          # Static files
│   └── breaktime_calculator_template.csv  # CSV template file
├── uploads/                         # Uploaded CSV files (user-specific directories)
├── output/                          # Generated report files (user-specific directories)
├── pyproject.toml                   # Project configuration
├── requirements.txt                 # Python dependencies
├── uv.lock                          # uv lock file for reproducible builds
├── .env.example                     # Environment variables example
├── .env                             # Environment variables (not in git)
├── docker-compose.yml               # Docker development setup
├── docker-compose.prod.yml          # Docker production setup
├── Dockerfile                       # Docker image definition
├── start.bat                        # Windows startup script
├── start.sh                         # Unix/Mac startup script
├── start-production.sh              # Production startup script
└── README.md                        # This documentation
```

## Development Workflow

The project uses `uv` for fast, reliable dependency management and follows FastAPI best practices:

- **Install dependencies**: `uv sync`
- **Run web app**: `uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
- **Add dependencies**: `uv add <package-name>`
- **Install dev dependencies**: `uv sync --dev`

### Quick Start Commands
```bash
# Development server
uv run uvicorn app.main:app --reload

# Production server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run with environment variables
uv run uvicorn app.main:app --env-file .env
```

## Sample Output

When you run the calculator, you'll see:

```
AGES Break Time Calculator
==================================================
Break Time Rules:
- Employees get a paid 10-minute rest break for every 4 hours worked
- 3.5–6 hours: 1 break (10 minutes)
- 6–10 hours: 2 breaks (20 minutes)
- 10–14 hours: 3 breaks (30 minutes)
==================================================

=== DAILY BREAK TIME CALCULATION ===
Total records processed: 4980
Total providers: 97
Date range: 6/10/2025 10:00 to 6/9/2025 9:45

=== DAILY BREAKDOWN ===
[Detailed daily breakdown for each provider...]

=== PROVIDER SUMMARY ===
[Summary table with totals by provider...]

Detailed results saved to:
- daily_break_calculation.csv
- provider_break_summary.csv

Processing completed successfully!
```

## Legal Compliance

This calculator implements break time requirements based on standard labor regulations:
- Rest breaks should be scheduled in the middle of each 4-hour work period when practicable
- Breaks are paid time
- Major fraction rule applies (anything more than 2 hours counts as a major fraction)

## Contributing

We welcome contributions! Please feel free to submit issues, feature requests, or pull requests to improve the calculator's functionality or accuracy.

### Development Setup

This project follows FastAPI best practices with a clean, modular architecture. All development can be done using the commands shown in the Development Workflow section above.

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.
