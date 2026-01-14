import pyodbc

def get_connection():
    conn = pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=.;"
        "Database=SellerGenAI;"
        "Trusted_Connection=yes;"
    )
    return conn


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("✅ SQL Server connected successfully!")
        conn.close()
    except Exception as e:
        print("❌ Connection failed:", e)
