# File: app.py

import os
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, g
from functools import wraps
import datetime

app = Flask(__name__)
# Pro použití session je potřeba nastavit tajný klíč
app.secret_key = 'tajny-klic-pro-session'

# Heslo pro přístup do systému
PASSWORD = "admin"

# --- MySQL nastavení ---
DB_HOST = "Gelbic.mysql.pythonanywhere-services.com"
DB_USER = "Gelbic"
DB_NAME = "Gelbic$default"
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD") # Načte heslo z proměnné prostředí

# --- Správa databáze ---
def get_db_connection():
    """Vytvoří připojení k databázi MySQL."""
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    return conn

def init_db():
    """Vytvoří databázové tabulky, pokud neexistují."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabulka pro zákazníky
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                company VARCHAR(255),
                address VARCHAR(255),
                phone VARCHAR(255),
                email VARCHAR(255)
            ) ENGINE=InnoDB;
        """)
        
        # Tabulka pro zakázky
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_number VARCHAR(255) UNIQUE NOT NULL,
                job_name VARCHAR(255) NOT NULL,
                description TEXT,
                customer_id INT,
                status VARCHAR(255) NOT NULL,
                due_date DATE,
                price_type VARCHAR(255),
                price DECIMAL(10, 2),
                deposit DECIMAL(10, 2),
                total_paid DECIMAL(10, 2),
                is_invoiced TINYINT DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            ) ENGINE=InnoDB;
        """)

        # Tabulka pro úkoly
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_id INT,
                task_name VARCHAR(255) NOT NULL,
                notes TEXT,
                due_date DATE,
                is_completed TINYINT DEFAULT 0,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            ) ENGINE=InnoDB;
        """)

        conn.commit()
        cursor.close()
        print("Tabulky byly úspěšně vytvořeny nebo již existují.")
    except Exception as e:
        print(f"Chyba při inicializaci databáze: {e}")
    finally:
        if conn:
            conn.close()

# Spuštění inicializace databáze
init_db()

# --- Autentifikace a routy ---

def login_required(f):
    """Dekorátor pro ochranu rout heslem."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    """Přihlašovací stránka."""
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template("login.html", error="Nesprávné heslo")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Odhlášení."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.before_request
def before_request():
    g.user = None
    if 'logged_in' in session:
        g.user = "admin"

@app.route("/")
@login_required
def index():
    """Hlavní dashboard s přehledem aktivních zakázek."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(id) AS count FROM jobs")
    jobs_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(id) AS count FROM customers")
    customers_count = cursor.fetchone()['count']
    
    # Načtení zakázek s daty zákazníka
    cursor.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY due_date ASC
        LIMIT 5
    """)
    jobs = cursor.fetchall()

    # Nová část: Zakázky před termínem (do 10 dnů)
    today = datetime.date.today()
    in_ten_days = today + datetime.timedelta(days=10)

    cursor.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.due_date BETWEEN %s AND %s
        ORDER BY due_date ASC
    """, (today.isoformat(), in_ten_days.isoformat(),))
    upcoming_jobs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template("index.html", jobs_count=jobs_count, customers_count=customers_count, jobs=jobs, upcoming_jobs=upcoming_jobs)

@app.route("/jobs")
@login_required
def job_list():
    """Zobrazí seznam všech zakázek."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY due_date ASC
    """)
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("job_list.html", jobs=jobs)

@app.route("/jobs/add", methods=["GET", "POST"])
@login_required
def add_job():
    """Formulář pro přidání nové zakázky."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM customers ORDER BY name")
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if request.method == "POST":
        job_number = request.form["job_number"]
        job_name = request.form["job_name"]
        description = request.form["description"]
        customer_id = request.form["customer_id"]
        status = request.form["status"]
        due_date = request.form["due_date"]
        price = request.form["price"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO jobs (job_number, job_name, description, customer_id, status, due_date, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (job_number, job_name, description, customer_id, status, due_date, price))
            conn.commit()
            return redirect(url_for("job_list"))
        except mysql.connector.Error as err:
            if err.errno == 1062: # 1062 je kód pro duplicate entry
                return "Zakázka s tímto číslem již existuje.", 400
            else:
                return f"Nastala chyba: {err}", 500
        finally:
            cursor.close()
            conn.close()
    
    return render_template("job_form.html", customers=customers)

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    """Zobrazí detail konkrétní zakázky."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.phone, customers.email
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = %s
    """, (job_id,))
    job = cursor.fetchone()
    
    cursor.execute("SELECT * FROM tasks WHERE job_id = %s ORDER BY due_date", (job_id,))
    tasks = cursor.fetchall()
    
    cursor.close()
    conn.close()
    if job is None:
        return "Zakázka nenalezena.", 404
    return render_template("job_detail.html", job=job, tasks=tasks)


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    """Formulář pro úpravu zakázky."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
    job = cursor.fetchone()
    cursor.execute("SELECT id, name FROM customers ORDER BY name")
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if job is None:
        return "Zakázka nenalezena.", 404
        
    if request.method == "POST":
        job_number = request.form["job_number"]
        job_name = request.form["job_name"]
        description = request.form["description"]
        customer_id = request.form["customer_id"]
        status = request.form["status"]
        due_date = request.form["due_date"]
        price = request.form["price"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET job_number = %s, job_name = %s, description = %s, customer_id = %s, status = %s, due_date = %s, price = %s
            WHERE id = %s
        """, (job_number, job_name, description, customer_id, status, due_date, price, job_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for("job_detail", job_id=job_id))
        
    return render_template("job_form.html", job=job, customers=customers)
    
@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def delete_job(job_id):
    """Smaže zakázku a všechny její úkoly."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE job_id = %s", (job_id,))
    cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("job_list"))


@app.route("/customers")
@login_required
def customer_list():
    """Zobrazí seznam všech zákazníků."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM customers ORDER BY name")
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("customer_list.html", customers=customers)

@app.route("/customers/add", methods=["GET", "POST"])
@login_required
def add_customer():
    """Formulář pro přidání nového zákazníka."""
    if request.method == "POST":
        name = request.form["name"]
        company = request.form["company"]
        address = request.form["address"]
        phone = request.form["phone"]
        email = request.form["email"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (name, company, address, phone, email)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, company, address, phone, email))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for("customer_list"))
        
    return render_template("customer_form.html")

@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    """API pro přidání nového úkolu k zakázce."""
    job_id = request.form["job_id"]
    task_name = request.form["task_name"]
    notes = request.form["notes"]
    due_date = request.form["due_date"]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (job_id, task_name, notes, due_date)
        VALUES (%s, %s, %s, %s)
    """, (job_id, task_name, notes, due_date))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id):
    """API pro přepnutí stavu úkolu (dokončený/nedokončený)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT is_completed FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    if task:
        new_status = 1 if task["is_completed"] == 0 else 0
        cursor.execute("UPDATE tasks SET is_completed = %s WHERE id = %s", (new_status, task_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "new_status": new_status})
    cursor.close()
    conn.close()
    return jsonify({"success": False}), 404


if __name__ == "__main__":
    app.run(debug=True)
