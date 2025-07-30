import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import date


class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to db/compilers.db relative to the project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'compilers.db')
        
        self.db_path = db_path
    
    def get_connection(self):
        """Get a database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def get_repository_info(self, git_username: str, repository_name: str) -> Optional[Dict[str, Any]]:
        """Get repository information including installation_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, s.language, s.extension, s.secret 
                FROM Repository r
                JOIN Semester s ON r.semester_name = s.name
                WHERE r.git_username = ? AND r.repository_name = ?
            """, (git_username, repository_name))
            
            row = cursor.fetchone()
            return dict(row) if row else None 
    
    def get_repository_status(self, git_username: str, repository_name: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a repository across all versions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT git_username, version_name, repository_name, semester_name, 
                       language, extension, test_status, delivery_status
                FROM ReleaseStatus 
                WHERE git_username = ? AND repository_name = ?
                ORDER BY version_name ASC
            """, (git_username, repository_name))
            
            rows = cursor.fetchall()
            if not rows:
                return None
            
            # Convert to list of dictionaries
            return [dict(row) for row in rows]
    
    def get_overall_repository_status(self, git_username: str, repository_name: str) -> str:
        """Get overall status for badge generation"""
        statuses = self.get_repository_status(git_username, repository_name)
        
        if not statuses:
            return "unknown"
        
        # Check if any version is passing
        for status in statuses:
            if status['test_status'] == 'PASS':
                return "passing"
        
        # Check if any test has been run
        for status in statuses:
            if status['test_status'] in ['ERROR', 'FAILED']:
                return "failing"
        
        return "unknown"
    
    def record_test_result(self, version_name: str, release_name: str, 
                          git_username: str, repository_name: str, 
                          test_status: str, issue_text: str = None, semester_name: str = None) -> bool:
        """Record a new test result"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # If semester_name is not provided, try to get it from repository
                if semester_name is None:
                    cursor.execute("""
                        SELECT semester_name FROM Repository 
                        WHERE git_username = ? AND repository_name = ?
                    """, (git_username, repository_name))
                    result = cursor.fetchone()
                    if result:
                        semester_name = result['semester_name']
                    else:
                        print(f"Error: Repository {git_username}/{repository_name} not found")
                        return False
                
                cursor.execute("""
                    INSERT OR REPLACE INTO TestResult 
                    (version_name, release_name, git_username, repository_name, 
                     date_run, test_status, issue_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (version_name, release_name, git_username, repository_name,
                      datetime.now().isoformat(), test_status, issue_text))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error recording test result: {e}")
            return False
    
    def get_repository_info(self, git_username: str, repository_name: str) -> Optional[Dict[str, Any]]:
        """Get repository configuration information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, s.language, s.extension, s.secret
                FROM Repository r
                JOIN Semester s ON r.semester_name = s.name
                WHERE r.git_username = ? AND r.repository_name = ?
            """, (git_username, repository_name))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_active_versions(self, semester_name: str = None) -> List[Dict[str, Any]]:
        """Get currently active versions (where date_from <= now <= date_to)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM Version 
                WHERE datetime('now', '-3 hour') >= date_from 
                AND datetime('now', '-3 hour') <= date_to
            """
            params = []
            
            if semester_name:
                query += " AND semester_name = ?"
                params.append(semester_name)
            
            query += " ORDER BY semester_name, version_name"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def verify_webhook_secret(self, repository_info: Dict[str, Any], provided_secret: str) -> bool:
        """Verify webhook secret for security"""
        return repository_info.get('secret') == provided_secret
    
    def get_semester_info(self, semester_name: str) -> Optional[Dict[str, Any]]:
        """Get semester information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Semester WHERE name = ?", (semester_name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_repositories_by_semester(self, semester_name: str) -> List[Dict[str, Any]]:
        """List all repositories in a semester"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, u.name, u.email 
                FROM Repository r
                JOIN User u ON r.git_username = u.git_username
                WHERE r.semester_name = ?
                ORDER BY r.git_username, r.repository_name
            """, (semester_name,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def save_repository_with_installation(self, git_username: str, repository_name: str, installation_id: int) -> bool:
        """Save repository with installation_id and empty/default values for other fields"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO Repository 
                    (git_username, repository_name, semester_name, compiled, program_call, installation_id)
                    VALUES (?, ?, '', 0, '', ?)
                """, (git_username, repository_name, installation_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving repository with installation: {e}")
            return False
    
    def update_repository_details(self, git_username: str, repository_name: str, 
                                semester_name: str, program_call: str) -> bool:
        """Update repository with complete details"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Repository 
                    SET semester_name = ?, program_call = ?, compiled = 1
                    WHERE git_username = ? AND repository_name = ?
                """, (semester_name, program_call, git_username, repository_name))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating repository details: {e}")
            return False
    
    def save_or_update_user(self, git_username: str, name: str, email: str) -> bool:
        """Save or update user with name and email"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO User (git_username, name, email)
                    VALUES (?, ?, ?)
                """, (git_username, name, email))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving user: {e}")
            return False

# Global database manager instance
db_manager = DatabaseManager()
