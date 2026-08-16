import mysql.connector


def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="saiteja@1603",
        database="job_tracker"
    )

    return connection