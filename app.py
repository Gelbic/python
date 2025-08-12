# File: app.py

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
import datetime

app = Flask(__name__)
DB_PATH = "zakazky.db"

# --- Správa databáze ---
def get_db_connection():
    """Vytvoří připojení k databázi SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Vytvoří databázové tabulky, pokud neexistují."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabulka pro zákazníky
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            address TEXT,
            phone TEXT,
            email TEXT
        );
    """)
    
    # Tabulka pro zakázky
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            job_name TEXT NOT NULL,
            description TEXT,
            customer_id INTEGER,
            status TEXT NOT NULL,
            due_date TEXT,
            price_type TEXT,
            price REAL,
            deposit REAL,
            total_paid REAL,
            is_invoiced INTEGER DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        );
    """)

    # Tabulka pro úkoly
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            task_name TEXT NOT NULL,
            notes TEXT,
            due_date TEXT,
            is_completed INTEGER DEFAULT 0,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        );
    """)

    conn.commit()
    conn.close()

# Spuštění inicializace databáze
init_db()


# --- Routy pro aplikaci ---

@app.route("/")
def index():
    """Hlavní dashboard s přehledem aktivních zakázek."""
    conn = get_db_connection()
    jobs_count = conn.execute("SELECT COUNT(id) FROM jobs").fetchone()[0]
    customers_count = conn.execute("SELECT COUNT(id) FROM customers").fetchone()[0]
    
    # Načtení zakázek s daty zákazníka
    jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY due_date ASC
        LIMIT 5
    """).fetchall()

    # Nová část: Zakázky před termínem (do 10 dnů)
    today = datetime.date.today()
    in_ten_days = today + datetime.timedelta(days=10)

    upcoming_jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE date(jobs.due_date) BETWEEN date(?) AND date(?)
        ORDER BY due_date ASC
    """, (today.isoformat(), in_ten_days.isoformat(),)).fetchall()
    
    conn.close()
    return render_template("index.html", jobs_count=jobs_count, customers_count=customers_count, jobs=jobs, upcoming_jobs=upcoming_jobs)

@app.route("/jobs")
def job_list():
    """Zobrazí seznam všech zakázek."""
    conn = get_db_connection()
    jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY due_date ASC
    """).fetchall()
    conn.close()
    return render_template("job_list.html", jobs=jobs)

@app.route("/jobs/add", methods=["GET", "POST"])
def add_job():
    """Formulář pro přidání nové zakázky."""
    conn = get_db_connection()
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
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
        try:
            conn.execute("""
                INSERT INTO jobs (job_number, job_name, description, customer_id, status, due_date, price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_number, job_name, description, customer_id, status, due_date, price))
            conn.commit()
            return redirect(url_for("job_list"))
        except sqlite3.IntegrityError:
            return "Zakázka s tímto číslem již existuje.", 400
        finally:
            conn.close()
    
    return render_template("job_form.html", customers=customers)

@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    """Zobrazí detail konkrétní zakázky."""
    conn = get_db_connection()
    job = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.phone, customers.email
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = ?
    """, (job_id,)).fetchone()
    tasks = conn.execute("SELECT * FROM tasks WHERE job_id = ? ORDER BY due_date", (job_id,)).fetchall()
    conn.close()
    if job is None:
        return "Zakázka nenalezena.", 404
    return render_template("job_detail.html", job=job, tasks=tasks)


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    """Formulář pro úpravu zakázky."""
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
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
        conn.execute("""
            UPDATE jobs
            SET job_number = ?, job_name = ?, description = ?, customer_id = ?, status = ?, due_date = ?, price = ?
            WHERE id = ?
        """, (job_number, job_name, description, customer_id, status, due_date, price, job_id))
        conn.commit()
        conn.close()
        return redirect(url_for("job_detail", job_id=job_id))
        
    return render_template("job_form.html", job=job, customers=customers)
    
@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    """Smaže zakázku a všechny její úkoly."""
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("job_list"))


@app.route("/customers")
def customer_list():
    """Zobrazí seznam všech zákazníků."""
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    conn.close()
    return render_template("customer_list.html", customers=customers)

@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():
    """Formulář pro přidání nového zákazníka."""
    if request.method == "POST":
        name = request.form["name"]
        company = request.form["company"]
        address = request.form["address"]
        phone = request.form["phone"]
        email = request.form["email"]
        
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO customers (name, company, address, phone, email)
            VALUES (?, ?, ?, ?, ?)
        """, (name, company, address, phone, email))
        conn.commit()
        conn.close()
        return redirect(url_for("customer_list"))
        
    return render_template("customer_form.html")

@app.route("/tasks/add", methods=["POST"])
def add_task():
    """API pro přidání nového úkolu k zakázce."""
    job_id = request.form["job_id"]
    task_name = request.form["task_name"]
    notes = request.form["notes"]
    due_date = request.form["due_date"]
    
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO tasks (job_id, task_name, notes, due_date)
        VALUES (?, ?, ?, ?)
    """, (job_id, task_name, notes, due_date))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    """API pro přepnutí stavu úkolu (dokončený/nedokončený)."""
    conn = get_db_connection()
    task = conn.execute("SELECT is_completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task:
        new_status = 1 if task["is_completed"] == 0 else 0
        conn.execute("UPDATE tasks SET is_completed = ? WHERE id = ?", (new_status, task_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "new_status": new_status})
    conn.close()
    return jsonify({"success": False}), 404


if __name__ == "__main__":
    app.run(debug=True)
