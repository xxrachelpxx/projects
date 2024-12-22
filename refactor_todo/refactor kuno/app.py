import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging 

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Helper function for database connection
def get_db_connection():
    connection = sqlite3.connect('todo_app.db')
    connection.row_factory = sqlite3.Row
    return connection

# Initialize SQLite database and create tables
def initialize_db():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Create the users table with an 'is_blocked' field to track blocked status
        cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user', -- Added role field with default 'user'
                is_blocked BOOLEAN DEFAULT 0 -- Add is_blocked field (0 = not blocked, 1 = blocked)
            )
        ''')

        # Create the tasks table (unchanged)
        cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                due_date DATE NOT NULL,
                priority TEXT DEFAULT 'LOW',
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        connection.commit()
        connection.close()
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")


initialize_db()

# Home route
@app.route("/")
def index():
    return render_template("login.html")

# Registration route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form["first_name"].strip()
        last_name = request.form["last_name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        role = request.form.get("role", "user")  # Get the role (default: 'user')

        if not first_name or not last_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute('''
                INSERT INTO users (first_name, last_name, email, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (first_name, last_name, email, password_hash, role))
            connection.commit()
            connection.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Error: Email already exists.', 'danger')
        except Exception as e:
            flash(f'Error: Unable to register. {str(e)}', 'danger')

    return render_template('registration.html')

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        if not email or not password:
            flash("Both email and password are required.", "danger")
            return redirect(url_for('login'))

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            connection.close()

            if user:
                if user['is_blocked']:
                    flash('Your account is blocked. Please contact an admin.', 'danger')
                    return redirect(url_for('login'))

                if check_password_hash(user["password_hash"], password):
                    session['user_id'] = user["id"]
                    session['user_name'] = f"{user['first_name']} {user['last_name']}"
                    session['role'] = user['role']  # Store role in session
                    flash('Login successful!', 'success')

                    # Redirect to the appropriate dashboard based on user role
                    if user['role'] == 'admin':
                        return redirect(url_for('admin_dashboard'))  # Admin dashboard
                    else:
                        return redirect(url_for('dashboard'))  # Regular user dashboard

            flash('Invalid email or password.', 'danger')
        except Exception as e:
            logging.error(f"Login failed: {e}")
            flash("Error: Unable to login. Please try again.", 'danger')

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Dashboard route (User dashboard)
@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    user_first_name = session.get('user_name', 'User').split()[0]

    # Fetch tasks for the logged-in user
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('''
        SELECT * FROM tasks WHERE user_id = ?
        ORDER BY due_date ASC, priority DESC
    ''', (session['user_id'],))
    tasks = cursor.fetchall()
    connection.close()

    return render_template("dashboard.html", user_first_name=user_first_name, tasks=tasks)

# Admin Dashboard route
@app.route("/admin_dashboard")
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('You do not have permission to access the admin dashboard.', 'danger')
        return redirect(url_for('dashboard'))

    # Fetch all users and tasks for the admin
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()

    cursor.execute('SELECT * FROM tasks')
    tasks = cursor.fetchall()

    connection.close()

    return render_template('admin_dashboard.html', users=users, tasks=tasks)

# Add task route
@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if 'user_id' not in session:
        flash('Please log in to add tasks.', 'warning')
        return redirect(url_for('login'))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()
        priority = request.form.get("priority", "LOW").strip()

        if not title or not description or not due_date:
            flash("All fields are required to add a task.", "danger")
            return redirect(url_for('add_task'))

        try:
            due_date = datetime.strptime(due_date, '%Y-%m-%d')  # Validate date format
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('add_task'))

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, title, description, due_date, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], title, description, due_date, priority))
        connection.commit()
        connection.close()

        flash('Task added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_task.html')

# Update task route
@app.route("/update_task/<int:task_id>", methods=["GET", "POST"])
def update_task(task_id):
    if 'user_id' not in session:
        flash('Please log in to update tasks.', 'warning')
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, session['user_id']))
    task = cursor.fetchone()

    if not task:
        connection.close()
        flash("Task not found or you don't have permission to edit it.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()
        priority = request.form.get("priority", "LOW").strip()
        status = request.form.get("status", "Pending").strip()

        if not title or not description or not due_date:
            flash("All fields are required to update the task.", "danger")
            return redirect(url_for('update_task', task_id=task_id))

        try:
            due_date = datetime.strptime(due_date, '%Y-%m-%d')  # Validate date format
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('update_task', task_id=task_id))

        cursor.execute('''
            UPDATE tasks
            SET title = ?, description = ?, due_date = ?, priority = ?, status = ?
            WHERE id = ? AND user_id = ?
        ''', (title, description, due_date, priority, status, task_id, session['user_id']))
        connection.commit()
        connection.close()

        flash('Task updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    connection.close()
    return render_template('update_task.html', task=task)

# Delete task route
@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if 'user_id' not in session:
        flash('Please log in to delete tasks.', 'warning')
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, session['user_id']))
    connection.commit()
    connection.close()

    flash('Task deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

#################################################

# Route to fetch all users
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    users = conn.execute('SELECT id, first_name || " " || last_name AS username, email, role, is_blocked FROM users').fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])  # Convert rows to dictionaries

# Route to block/unblock a user
@app.route('/api/users/<int:user_id>/block', methods=['PUT'])
def block_user(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch the current block status of the user
        cursor.execute('SELECT is_blocked FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()

        if not user:
            connection.close()
            return jsonify({'message': 'User not found.'}), 404

        # Toggle the block status: 0 -> 1 (blocked), 1 -> 0 (unblocked)
        new_block_status = 0 if user['is_blocked'] else 1

        cursor.execute('UPDATE users SET is_blocked = ? WHERE id = ?', (new_block_status, user_id))
        connection.commit()

        connection.close()

        return jsonify({'message': f'User {user_id} block status set to {new_block_status}.'})

    except Exception as e:
        logging.error(f"Error blocking/unblocking user: {e}")
        return jsonify({'message': 'Error processing request'}), 500

# Route to delete a user
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    connection = get_db_connection()
    connection.execute('DELETE FROM users WHERE id = ?', (user_id,))
    connection.commit()
    connection.close()
    return jsonify({'message': f'User {user_id} deleted.'})

if __name__ == '__main__':
    app.run(debug=True)
