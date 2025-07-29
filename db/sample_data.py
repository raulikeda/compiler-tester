import db_conn as db

conn = db.getConnection('compilers.db')
cursor = conn.cursor()

#############################################
#  SAMPLE DATA INSERTION
#############################################

# Insert sample semesters
cursor.execute("""
INSERT OR REPLACE INTO Semester (name, language, extension, secret) VALUES
    ('2025-1', 'python', '.py', 'secret_2025_1'),
    ('2025-2', 'java', '.java', 'secret_2025_2'),
    ('2024-2', 'cpp', '.cpp', 'secret_2024_2')
""")

# Insert sample users
cursor.execute("""
INSERT OR REPLACE INTO User (git_username, name, surname) VALUES
    ('raulikeda', 'Raul', 'Ikeda'),
    ('student1', 'John', 'Doe'),
    ('student2', 'Jane', 'Smith')
""")

# Insert sample repositories
cursor.execute("""
INSERT OR REPLACE INTO Repository (git_username, repository_name, semester_name, compiled, program_call) VALUES
    ('raulikeda', 'compiler-tester', '2025-1', 0, 'python main.py'),
    ('student1', 'assignment1', '2025-1', 1, 'python compile.py'),
    ('student2', 'project-alpha', '2025-2', 1, 'javac Main.java && java Main')
""")

# Insert sample versions
cursor.execute("""
INSERT OR REPLACE INTO Version (version_name, semester_name, direct_input, date_from, date_to) VALUES
    ('v1.0', '2025-1', 1, '2025-01-15 00:00:00', '2025-02-15 23:59:59'),
    ('v1.1', '2025-1', 0, '2025-02-16 00:00:00', '2025-03-15 23:59:59'),
    ('v2.0', '2025-2', 1, '2025-03-01 00:00:00', '2025-04-01 23:59:59')
""")

# Insert sample test results
cursor.execute("""
INSERT OR REPLACE INTO TestResult (version_name, release_name, git_username, repository_name, date_run, test_status, issue_text) VALUES
    ('v1.0', 'release-1.0', 'raulikeda', 'compiler-tester', '2025-01-20 10:30:00', 'PASS', NULL),
    ('v1.0', 'release-1.0', 'student1', 'assignment1', '2025-01-25 14:15:00', 'FAILED', 'Compilation error: missing import'),
    ('v1.1', 'release-1.1', 'student2', 'project-alpha', '2025-02-20 16:45:00', 'PASS', NULL)
""")

conn.commit()
print("Sample data inserted successfully!")

# Query to verify the data
cursor.execute("SELECT * FROM ReleaseStatus")
results = cursor.fetchall()

print("\n=== ReleaseStatus View Results ===")
for row in results:
    print(f"User: {row[0]}, Version: {row[1]}, Repo: {row[2]}, Semester: {row[3]}, Language: {row[4]}, Status: {row[6]}, Delivery: {row[7]}")

conn.close()
