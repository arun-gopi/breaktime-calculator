"""
Progress tracking system for long-running calculations
"""
import threading
import time
from typing import Dict, Optional
from enum import Enum

class ProgressStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class ProgressTracker:
    def __init__(self):
        self._progress: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def start_task(self, task_id: str, total_steps: int = 100) -> None:
        """Start tracking a new task"""
        with self._lock:
            self._progress[task_id] = {
                "status": ProgressStatus.PENDING.value,
                "current_step": 0,
                "total_steps": total_steps,
                "percentage": 0,
                "message": "Initializing...",
                "start_time": time.time(),
                "error": None
            }
    
    def update_progress(self, task_id: str, current_step: int, message: str = "") -> None:
        """Update progress for a task"""
        with self._lock:
            if task_id in self._progress:
                progress = self._progress[task_id]
                progress["current_step"] = current_step
                progress["percentage"] = min(100, (current_step / progress["total_steps"]) * 100)
                progress["message"] = message or progress["message"]
                progress["status"] = ProgressStatus.PROCESSING.value
    
    def complete_task(self, task_id: str, result: Optional[Dict] = None) -> None:
        """Mark a task as completed"""
        with self._lock:
            if task_id in self._progress:
                progress = self._progress[task_id]
                progress["status"] = ProgressStatus.COMPLETED.value
                progress["percentage"] = 100
                progress["message"] = "Processing completed successfully"
                progress["result"] = result or {}
                progress["end_time"] = time.time()
    
    def error_task(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed"""
        with self._lock:
            if task_id in self._progress:
                progress = self._progress[task_id]
                progress["status"] = ProgressStatus.ERROR.value
                progress["error"] = error_message
                progress["message"] = f"Error: {error_message}"
                progress["end_time"] = time.time()
    
    def get_progress(self, task_id: str) -> Optional[Dict]:
        """Get current progress for a task"""
        with self._lock:
            progress = self._progress.get(task_id, None)
            if progress:
                # Ensure all values are JSON serializable
                serializable_progress = {}
                for key, value in progress.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_progress[key] = value
                    elif isinstance(value, dict):
                        serializable_progress[key] = value
                    elif hasattr(value, 'value'):  # Enum
                        serializable_progress[key] = value.value if hasattr(value, 'value') else str(value)
                    else:
                        serializable_progress[key] = str(value)
                return serializable_progress
            return None
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        """Remove old completed tasks"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self._lock:
            to_remove = []
            for task_id, progress in self._progress.items():
                if "end_time" in progress:
                    age = current_time - progress["end_time"]
                    if age > max_age_seconds:
                        to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._progress[task_id]

# Global progress tracker instance
progress_tracker = ProgressTracker()
