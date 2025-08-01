import db_conn as db

conn = db.getConnection('compilers.db')
cursor = conn.cursor()

#############################################
#  SAMPLE DATA INSERTION
#############################################

# Insert sample semesters
cursor.execute("""
INSERT OR REPLACE INTO Semester (name, language, extension, secret) VALUES
    ('BCC-2025-2', 'C', 'c', 'secret_2025_2'),
    ('ENG-2025-2', 'C', 'c', 'secret_2025_2')
""")

# Insert sample users
cursor.execute("""
INSERT OR REPLACE INTO User (git_username, name, email) VALUES
    ('raulikeda', 'Raul', 'a@a.com')
""")

# Insert sample repositories
cursor.execute("""
INSERT OR REPLACE INTO Repository (git_username, repository_name, semester_name, compiled, program_call, instalation_id, language) VALUES
    ('raulikeda', 'compiler-tester-eng', 'ENG-2025-2', 0, 'python main.py', 1, 'Python'),
    ('raulikeda', 'compiler-tester-bcc', 'BCC-2025-2', 0, 'python main.py', 2, 'Python'),
""")

# Insert sample versions
cursor.execute("""
INSERT OR REPLACE INTO Version (version_name, semester_name, direct_input, date_from, date_to) VALUES
    ('v0.0', 'BCC-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.0', 'BCC-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.1', 'BCC-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.2', 'BCC-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v2.0', 'BCC-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.1', 'BCC-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.2', 'BCC-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.3', 'BCC-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v3.0', 'BCC-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v0.0', 'ENG-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.0', 'ENG-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.1', 'ENG-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v1.2', 'ENG-2025-2', 0, '2025-07-15 00:00:00', '2025-12-15 23:59:59'),
    ('v2.0', 'ENG-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.1', 'ENG-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.2', 'ENG-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v2.3', 'ENG-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59'),
    ('v3.0', 'ENG-2025-2', 1, '2025-07-15 00:00:00', '2025-12-01 23:59:59')
""")

# Insert sample test results
cursor.execute("""
INSERT OR REPLACE INTO TestResult (version_name, release_name, git_username, repository_name, date_run, test_status, issue_text) VALUES
    ('v0.0', 'v0.0.0', 'raulikeda', 'compiler-tester-eng', '2025-01-20 10:30:00', 'PASS', NULL),
    ('v0.0', 'v0.0.0', 'raulikeda', 'compiler-tester-bcc', '2025-01-20 10:30:00', 'PASS', NULL),
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
