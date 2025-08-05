"""
Database abstraction layer for Break Time Calculator
PostgreSQL-only implementation
"""
import os
import hashlib
from typing import Optional, List, Tuple, Any, Union, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/breaktime_calculator")
        
        if not POSTGRES_AVAILABLE:
            raise ImportError("PostgreSQL support requires psycopg2-binary. Install with: pip install psycopg2-binary")
    
    def get_connection(self):
        """Get PostgreSQL database connection"""
        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch_one: bool = False, fetch_all: bool = False) -> Union[dict, List[dict], int, None]:
        """Execute a query and return results"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
            else:
                conn.commit()
                return cursor.rowcount
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize PostgreSQL database tables"""
        print("Initializing PostgreSQL database...")
        
        # Users table
        users_table = '''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT true
            )
        '''
        
        # File uploads table
        uploads_table = '''
            CREATE TABLE IF NOT EXISTS file_uploads (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                upload_path TEXT NOT NULL,
                daily_output_path TEXT,
                summary_output_path TEXT,
                provider_date_output_path TEXT,
                audit_output_path TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT false,
                total_records INTEGER,
                total_providers INTEGER,
                date_range TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        '''
        
        # Configuration table
        config_table = '''
            CREATE TABLE IF NOT EXISTS configurations (
                id SERIAL PRIMARY KEY,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                config_type TEXT NOT NULL DEFAULT 'string',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        
        # Execute table creation
        self.execute_query(users_table)
        self.execute_query(uploads_table)
        self.execute_query(config_table)
        
        # Run migrations
        self._run_migrations()
        
        # Initialize default configurations
        self._init_default_configs()
        
        # Check if we need to migrate existing data or create default user
        users_result = self.execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        user_count = 0
        if isinstance(users_result, dict) and 'count' in users_result:
            user_count = users_result['count']
        
        if user_count == 0:
            print("Creating default admin user...")
            self.create_user("admin", "admin@company.com", "admin123", "System Administrator")
        
        print("PostgreSQL database initialization completed.")
    
    def _run_migrations(self):
        """Run database migrations for schema updates"""
        try:
            # Check if audit_output_path column exists
            check_column_query = '''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'file_uploads' AND column_name = 'audit_output_path'
            '''
            result = self.execute_query(check_column_query, fetch_one=True)
            
            if not result:
                print("Adding audit_output_path column to file_uploads table...")
                alter_query = '''
                    ALTER TABLE file_uploads 
                    ADD COLUMN audit_output_path TEXT
                '''
                self.execute_query(alter_query)
                print("Migration completed: audit_output_path column added.")
        except Exception as e:
            print(f"Migration warning: {e}")
    
    def create_user(self, username: str, email: str, password: str, full_name: str) -> int:
        """Create a new user"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        query = '''
            INSERT INTO users (username, email, password_hash, full_name) 
            VALUES (%s, %s, %s, %s) RETURNING id
        '''
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (username, email, password_hash, full_name))
            result = cursor.fetchone()
            user_id = result['id'] if result is not None else 0
            conn.commit()
            return user_id
        finally:
            conn.close()
    
    def get_user_by_credentials(self, username: str, password: str) -> Optional[dict]:
        """Get user by username and password"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        query = "SELECT * FROM users WHERE username = %s AND password_hash = %s"
        result = self.execute_query(query, (username, password_hash), fetch_one=True)
        return result if isinstance(result, dict) else None
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user by ID"""
        query = "SELECT * FROM users WHERE id = %s"
        result = self.execute_query(query, (user_id,), fetch_one=True)
        return result if isinstance(result, dict) else None
    
    def create_file_upload(self, upload_id: str, user_id: int, original_filename: str, upload_path: str) -> None:
        """Create file upload record"""
        query = '''
            INSERT INTO file_uploads (id, user_id, original_filename, upload_path) 
            VALUES (%s, %s, %s, %s)
        '''
        self.execute_query(query, (upload_id, user_id, original_filename, upload_path))
    
    def update_file_upload(self, upload_id: str, **kwargs) -> None:
        """Update file upload record"""
        set_clauses = []
        params = []
        
        for key, value in kwargs.items():
            set_clauses.append(f"{key} = %s")
            params.append(value)
        
        params.append(upload_id)
        query = f"UPDATE file_uploads SET {', '.join(set_clauses)} WHERE id = %s"
        self.execute_query(query, tuple(params))
    
    def get_user_uploads(self, user_id: int) -> List[dict]:
        """Get all uploads for a user"""
        query = '''
            SELECT id, original_filename, upload_date, processed, total_records, 
                   total_providers, date_range, audit_output_path
            FROM file_uploads 
            WHERE user_id = %s 
            ORDER BY upload_date DESC
        '''
        result = self.execute_query(query, (user_id,), fetch_all=True)
        return result if isinstance(result, list) else []
    
    def get_upload_by_id(self, upload_id: str) -> Optional[dict]:
        """Get upload by ID"""
        query = "SELECT * FROM file_uploads WHERE id = %s"
        result = self.execute_query(query, (upload_id,), fetch_one=True)
        return result if isinstance(result, dict) else None
    
    def _init_default_configs(self):
        """Initialize default configuration values"""
        defaults = [
            ('excluded_procedure_codes', 'Late Cancel by Client,10 Minute Break,Lead BT,Lunch Break,Sick Leave', 'list', 'Comma-separated list of procedure codes to exclude from work time calculations'),
            ('break_threshold_1', '4.0', 'float', 'First break threshold in hours'),
            ('break_threshold_2', '8.0', 'float', 'Second break threshold in hours'),
            ('break_threshold_3', '12.0', 'float', 'Third break threshold in hours'),
            ('break_duration_1', '10', 'int', 'Duration for first break in minutes'),
            ('break_duration_2', '20', 'int', 'Total duration for two breaks in minutes'),
            ('break_duration_3', '30', 'int', 'Total duration for three breaks in minutes'),
            ('continuous_hours', 'true', 'boolean', 'Use continuous hours for break calculations: timestamps when available, otherwise work + drive time'),
        ]
        
        for config_key, config_value, config_type, description in defaults:
            # Check if config already exists
            existing = self.get_config(config_key)
            if not existing:
                self.set_config(config_key, config_value, config_type, description)
    
    def get_config(self, config_key: str) -> Optional[dict]:
        """Get configuration value by key"""
        query = "SELECT * FROM configurations WHERE config_key = %s"
        result = self.execute_query(query, (config_key,), fetch_one=True)
        return result if isinstance(result, dict) else None
    
    def set_config(self, config_key: str, config_value: str, config_type: str = 'string', description: str = '') -> None:
        """Set configuration value"""
        # Check if config exists
        existing = self.get_config(config_key)
        
        if existing:
            # Update existing config
            query = '''
                UPDATE configurations 
                SET config_value = %s, config_type = %s, description = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE config_key = %s
            '''
            self.execute_query(query, (config_value, config_type, description, config_key))
        else:
            # Insert new config
            query = '''
                INSERT INTO configurations (config_key, config_value, config_type, description) 
                VALUES (%s, %s, %s, %s)
            '''
            self.execute_query(query, (config_key, config_value, config_type, description))
    
    def get_all_config(self) -> List[dict]:
        """Get all configuration values"""
        query = "SELECT * FROM configurations ORDER BY config_key"
        result = self.execute_query(query, fetch_all=True)
        return result if isinstance(result, list) else []
    
    def get_config_value(self, config_key: str, default_value: Any = None) -> Any:
        """Get configuration value with type conversion"""
        config = self.get_config(config_key)
        if not config:
            return default_value
        
        config_value = config['config_value']
        config_type = config['config_type']
        
        try:
            if config_type == 'int':
                return int(config_value)
            elif config_type == 'float':
                return float(config_value)
            elif config_type == 'boolean':
                return config_value.lower() in ('true', '1', 'yes', 'on')
            elif config_type == 'list':
                return [item.strip() for item in config_value.split(',') if item.strip()]
            else:
                return config_value
        except (ValueError, AttributeError):
            return default_value
    
    def get_config_values(self, config_keys: List[str], defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get multiple configuration values in a single database call for better performance"""
        if not config_keys:
            return {}
        
        defaults = defaults or {}
        placeholders = ','.join(['%s'] * len(config_keys))
        query = f"SELECT config_key, config_value, config_type FROM configurations WHERE config_key IN ({placeholders})"
        
        result = self.execute_query(query, tuple(config_keys), fetch_all=True)
        
        # Process results and apply type conversion
        config_values = {}
        found_keys = set()
        
        if isinstance(result, list):
            for row in result:
                key = row['config_key']
                value = row['config_value']
                config_type = row['config_type']
                found_keys.add(key)
                
                try:
                    if config_type == 'int':
                        config_values[key] = int(value)
                    elif config_type == 'float':
                        config_values[key] = float(value)
                    elif config_type == 'boolean':
                        config_values[key] = value.lower() in ('true', '1', 'yes', 'on')
                    elif config_type == 'list':
                        config_values[key] = [item.strip() for item in value.split(',') if item.strip()]
                    else:
                        config_values[key] = value
                except (ValueError, AttributeError):
                    config_values[key] = defaults.get(key)
        
        # Add default values for missing keys
        for key in config_keys:
            if key not in found_keys:
                config_values[key] = defaults.get(key)
        
        return config_values

# Global database manager instance
db_manager = DatabaseManager()
