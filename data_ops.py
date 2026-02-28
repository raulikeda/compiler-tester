from db.database import db_manager
from typing import List, Dict, Any

def get_repositories_with_status(semester_name: str) -> List[Dict[str, Any]]:
    """Get all repositories in a semester with their release statuses."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rs.git_username, rs.version_name, rs.repository_name, rs.semester_name, rs.test_status, rs.delivery_status, r.language, u.name,
                   (SELECT release_name FROM TestResult 
                    WHERE git_username = rs.git_username 
                      AND repository_name = rs.repository_name 
                      AND version_name = rs.version_name 
                    ORDER BY date_run DESC LIMIT 1) as last_release_name
            FROM ReleaseStatus rs
            JOIN Repository r ON rs.git_username = r.git_username AND rs.repository_name = r.repository_name
            JOIN User u ON rs.git_username = u.git_username
            WHERE rs.semester_name like ?
            ORDER BY rs.semester_name, rs.version_name, rs.test_status desc, rs.git_username
        """, (f"%{semester_name}%",))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_last_test_results(semester_name: str) -> List[Dict[str, Any]]:
    """Get the last TestResult row for each git_username, version_name in the given semester."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tr.*
            FROM TestResult tr
            INNER JOIN Repository r ON tr.git_username = r.git_username AND tr.repository_name = r.repository_name
            WHERE r.semester_name like ?
              AND tr.date_run = (
                  SELECT MAX(date_run)
                  FROM TestResult
                  WHERE git_username = tr.git_username
                    AND repository_name = tr.repository_name
                    AND version_name = tr.version_name
              )
            ORDER BY tr.git_username, tr.version_name
        """, (f"%{semester_name}%",))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]