import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="my_budget",
        user="postgres",
        password="",
        host="localhost",
        port="5432"
    )
