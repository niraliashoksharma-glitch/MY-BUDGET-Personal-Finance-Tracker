import psycopg2

def get_connection():
    return psycopg2.connect(
        dbname="my_budget",
        user="postgres",
        password="Nirali2121!",
        host="localhost",
        port="5432"
    )
