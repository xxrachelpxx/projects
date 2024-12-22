import sqlite3

# Helper function for database connection
def get_db_connection():
    connection = sqlite3.connect('todo_app.db')
    connection.row_factory = sqlite3.Row
    return connection

# Function to alter the table and add the 'is_blocked' column
def alter_table_add_is_blocked():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if the 'is_blocked' column already exists
        cursor.execute("PRAGMA table_info(users);")
        columns = [column[1] for column in cursor.fetchall()]
        if 'is_blocked' in columns:
            print("The 'is_blocked' column already exists. No changes made.")
            return

        # Add the 'is_blocked' column with a default value of 0 (unblocked)
        cursor.execute('''
            ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0 NOT NULL;
        ''')

        connection.commit()
        print("Table altered successfully. 'is_blocked' column added.")

    except sqlite3.OperationalError as e:
        print(f"Error altering table: {e}")
        # Handle unexpected errors
    finally:
        if connection:
            connection.close()

# Call the function to alter the table
alter_table_add_is_blocked()
