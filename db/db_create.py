import db_conn as db

conn = db.getConnection('compilers.db')

cursor = conn.cursor()

#############################################
#  DATABASE SCHEMA CREATION
#############################################
cursor.execute("PRAGMA foreign_keys = 0")

# Drop existing tables in reverse dependency order
cursor.execute("""DROP TABLE IF EXISTS TestResult;""")
cursor.execute("""DROP TABLE IF EXISTS Repository;""")
cursor.execute("""DROP TABLE IF EXISTS Version;""")
cursor.execute("""DROP TABLE IF EXISTS User;""")
cursor.execute("""DROP TABLE IF EXISTS Semester;""")

# Drop existing views
cursor.execute("""DROP VIEW IF EXISTS ReleaseStatus;""")
cursor.execute("""DROP VIEW IF EXISTS TestResultStatus;""")

# cursor.execute("PRAGMA foreign_keys = 1")

# Create Semester table (new)
cursor.execute("""
CREATE TABLE Semester (
    name TEXT PRIMARY KEY NOT NULL,
    language TEXT NOT NULL,
    extension TEXT NOT NULL,
    secret TEXT NOT NULL
);
""")

# Create User table (renamed from users, singular)
cursor.execute("""
CREATE TABLE User (
    git_username TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL
);
""")

# Create Repository table (renamed from repository, with semester_name FK)
cursor.execute("""
CREATE TABLE Repository (
    git_username TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    semester_name TEXT NOT NULL,
    compiled INTEGER check(compiled = 0 or compiled = 1),
    program_call TEXT NOT NULL,
    installation_id INTEGER,
    language TEXT NOT NULL,
    PRIMARY KEY(git_username, repository_name),
    FOREIGN KEY(git_username) REFERENCES User(git_username),
    FOREIGN KEY(semester_name) REFERENCES Semester(name)
);
""")

# Create Version table (renamed from version, with semester_name FK)
cursor.execute("""
CREATE TABLE Version (
    version_name TEXT NOT NULL,
    semester_name TEXT NOT NULL,
    direct_input INTEGER NOT NULL,
    date_from DATETIME NOT NULL,
    date_to   DATETIME NOT NULL,
    PRIMARY KEY(version_name, semester_name),
    FOREIGN KEY(semester_name) REFERENCES Semester(name)
);
""")

# Create TestResult table (renamed from test_result, CamelCase)
cursor.execute("""
CREATE TABLE TestResult (
    version_name TEXT NOT NULL,
    release_name TEXT NOT NULL,
    git_username TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    date_run DATETIME NOT NULL,
    test_status TEXT check(test_status = 'PASS' or test_status = 'ERROR' or test_status = 'FAILED'),
    issue_text TEXT,
    PRIMARY KEY(version_name, release_name, git_username, repository_name),
    FOREIGN KEY(repository_name, git_username) REFERENCES Repository(repository_name, git_username)   
);
""")

conn.commit()

#############################################
#  VIEWS CREATION
#############################################

# Create TestResultStatus view (renamed from test_result_status, CamelCase)
cursor.execute("""
CREATE VIEW TestResultStatus AS
    SELECT tes.git_username,
            tes.repository_name,
            tes.version_name,
            max(tes.test_status) AS test_status
       FROM TestResult tes
  LEFT JOIN Version as ver ON ver.version_name = tes.version_name
   GROUP BY tes.git_username, tes.repository_name, tes.version_name
   ORDER BY tes.git_username, tes.repository_name
""")

# Create ReleaseStatus view (renamed from release_status, CamelCase, updated with semester integration)
cursor.execute("""
CREATE VIEW ReleaseStatus AS
       SELECT rep.git_username,
              ver.version_name,
              rep.repository_name,
              rep.semester_name,
              CASE trs.test_status is null
                  WHEN 1
                     THEN 'NOT_FOUND'
                  ELSE trs.test_status
              END test_status,
              CASE trs.test_status is null OR trs.test_status = 'ERROR' OR trs.test_status = 'FAILED'
                  WHEN 1
                     THEN CASE datetime('now', '-3 hour') > ver.date_to
                             WHEN 1
                                THEN 'DELAYED'
                             ELSE 'ON_TIME'
                          END
                  ELSE (SELECT CASE min(date_run) > ver.date_to
                                     WHEN 1
                                        THEN 'DELAYED'
                                     ELSE 'ON_TIME'
                                END
                          FROM TestResult tes
                         WHERE tes.repository_name = rep.repository_name
                           AND tes.version_name = ver.version_name
                           AND tes.git_username = rep.git_username
                           AND tes.test_status = 'PASS')
              END delivery_status
         FROM Repository AS rep
         JOIN Version AS ver ON rep.semester_name = ver.semester_name
    LEFT JOIN TestResultStatus AS trs ON trs.version_name = ver.version_name
                                       AND trs.git_username = rep.git_username
                                       AND trs.repository_name = rep.repository_name
        WHERE ver.date_from < datetime('now', '-3 hour')
     ORDER BY rep.git_username, rep.repository_name, ver.version_name
""")

conn.commit()

conn.close()
