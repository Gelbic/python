# File: app.py

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, g
from functools import wraps
import datetime

app = Flask(__name__)
# Pro použití session je potřeba nastavit tajný klíč
app.secret_key = 'tajny-klic-pro-session'

# Heslo pro přístup do systému
PASSWORD = "admin"

# --- Správa databáze ---
def get_db_connection():
    """Vytvoří připojení k databázi SQLite."""
    conn = sqlite3.connect(os.path.join(app.root_path, "zakazky.db"))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Vytvoří databázové tabulky, pokud neexistují a přidá nové sloupce."""
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
    # Upravení sloupce hourly_rate
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            job_name TEXT NOT NULL,
            description TEXT,
            customer_id INTEGER,
            status TEXT NOT NULL,
            due_date TEXT,
            price REAL,
            hourly_rate REAL,
            deposit REAL,
            total_paid REAL,
            is_invoiced INTEGER DEFAULT 0,
            invoice_date TEXT,
            payment_status TEXT DEFAULT 'Nezaplaceno',
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

    # NOVÁ TABULKA: Pracovníci
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            email TEXT,
            phone TEXT
        );
    """)

    # NOVÁ TABULKA: Odpracované hodiny (propojení na zakázku a pracovníka)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hours_spent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            worker_id INTEGER,
            date_spent TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id),
            FOREIGN KEY (worker_id) REFERENCES workers (id)
        );
    """)

    # NOVÁ TABULKA: Další služby a náklady
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS additional_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            cost REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        );
    """)

    conn.commit()
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

# --- Hlavní stránka a zakázky ---
@app.route("/")
@login_required
def index():
    """Hlavní dashboard s přehledem aktivních zakázek."""
    conn = get_db_connection()
    jobs_count = conn.execute("SELECT COUNT(id) FROM jobs").fetchone()[0]
    customers_count = conn.execute("SELECT COUNT(id) FROM customers").fetchone()[0]
    
    jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY due_date ASC
        LIMIT 5
    """).fetchall()

    today = datetime.date.today()
    in_ten_days = today + datetime.timedelta(days=10)

    upcoming_jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE date(jobs.due_date) BETWEEN date(?) AND date(?) AND jobs.status NOT IN ('Dokončená', 'Fakturovaná')
        ORDER BY due_date ASC
    """, (today.isoformat(), in_ten_days.isoformat(),)).fetchall()

    monthly_jobs = conn.execute("""
        SELECT strftime('%Y-%m', due_date) AS month, COUNT(id) AS count
        FROM jobs
        GROUP BY month
        ORDER BY month DESC
    """).fetchall()

    # Opravený SQL dotaz pro výpočet tržeb
    monthly_revenue = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total_paid) AS total
        FROM jobs
        WHERE payment_status = 'Uhrazeno' AND total_paid IS NOT NULL
        GROUP BY month
        ORDER BY month DESC
    """).fetchall()
    
    conn.close()
    return render_template("index.html", jobs_count=jobs_count, customers_count=customers_count, jobs=jobs, upcoming_jobs=upcoming_jobs, monthly_jobs=monthly_jobs, monthly_revenue=monthly_revenue)

@app.route("/jobs")
@login_required
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
@login_required
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
        price = request.form.get("price")
        hourly_rate = request.form.get("hourly_rate")
        
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO jobs (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate))
            conn.commit()
            return redirect(url_for("job_list"))
        except sqlite3.IntegrityError:
            return "Zakázka s tímto číslem již existuje.", 400
        finally:
            conn.close()
    
    return render_template("job_form.html", customers=customers)

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    """Zobrazí detail konkrétní zakázky."""
    conn = get_db_connection()
    job = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.phone, customers.email, customers.address
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = ?
    """, (job_id,)).fetchone()
    tasks = conn.execute("SELECT * FROM tasks WHERE job_id = ? ORDER BY due_date", (job_id,)).fetchall()
    workers = conn.execute("SELECT * FROM workers ORDER BY name").fetchall()
    hours = conn.execute("""
        SELECT hours_spent.*, workers.name AS worker_name
        FROM hours_spent
        LEFT JOIN workers ON hours_spent.worker_id = workers.id
        WHERE hours_spent.job_id = ?
        ORDER BY date_spent DESC
    """, (job_id,)).fetchall()

    total_hours = sum(h['hours'] for h in hours)
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job_id,)).fetchall()
    
    conn.close()
    if job is None:
        return "Zakázka nenalezena.", 404
    return render_template("job_detail.html", job=job, tasks=tasks, workers=workers, hours=hours, total_hours=total_hours, additional_services=additional_services)


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
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
        price = request.form.get("price")
        hourly_rate = request.form.get("hourly_rate")
        
        conn = get_db_connection()
        conn.execute("""
            UPDATE jobs
            SET job_number = ?, job_name = ?, description = ?, customer_id = ?, status = ?, due_date = ?, price = ?, hourly_rate = ?
            WHERE id = ?
        """, (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate, job_id))
        conn.commit()
        conn.close()
        return redirect(url_for("job_detail", job_id=job_id))
        
    return render_template("job_form.html", job=job, customers=customers)
    
@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def delete_job(job_id):
    """Smaže zakázku a všechny její úkoly a odpracované hodiny."""
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM hours_spent WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM additional_services WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("job_list"))

# --- Zákazníci ---
@app.route("/customers")
@login_required
def customer_list():
    """Zobrazí seznam všech zákazníků."""
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
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
        conn.execute("""
            INSERT INTO customers (name, company, address, phone, email)
            VALUES (?, ?, ?, ?, ?)
        """, (name, company, address, phone, email))
        conn.commit()
        conn.close()
        return redirect(url_for("customer_list"))
        
    return render_template("customer_form.html")

# --- Úkoly ---
@app.route("/tasks/add", methods=["POST"])
@login_required
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
@login_required
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

# --- Pracovníci ---
@app.route("/workers")
@login_required
def worker_list():
    """Zobrazí seznam všech pracovníků."""
    conn = get_db_connection()
    workers = conn.execute("SELECT * FROM workers ORDER BY name").fetchall()
    conn.close()
    return render_template("worker_list.html", workers=workers)

@app.route("/workers/add", methods=["GET", "POST"])
@login_required
def add_worker():
    """Formulář pro přidání nového pracovníka."""
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO workers (name, email, phone) VALUES (?, ?, ?)", (name, email, phone))
            conn.commit()
            return redirect(url_for("worker_list"))
        except sqlite3.IntegrityError:
            return "Pracovník s tímto jménem již existuje.", 400
        finally:
            conn.close()
    
    return render_template("worker_form.html")

# --- Odpracované hodiny ---
@app.route("/jobs/<int:job_id>/hours/add", methods=["POST"])
@login_required
def add_hours(job_id):
    """API pro přidání odpracovaných hodin k zakázce."""
    worker_id = request.form.get("worker_id")
    date_spent = request.form["date_spent"]
    hours = request.form["hours"]
    description = request.form.get("description")
    
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO hours_spent (job_id, worker_id, date_spent, hours, description)
        VALUES (?, ?, ?, ?, ?)
    """, (job_id, worker_id, date_spent, hours, description))
    conn.commit()
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))

# --- Další služby ---
@app.route("/jobs/<int:job_id>/services/add", methods=["POST"])
@login_required
def add_service(job_id):
    """API pro přidání dalších služeb a nákladů k zakázce."""
    service_name = request.form["service_name"]
    cost = request.form["cost"]
    notes = request.form.get("notes")

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO additional_services (job_id, service_name, cost, notes)
        VALUES (?, ?, ?, ?)
    """, (job_id, service_name, cost, notes))
    conn.commit()
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))

# --- Fakturace ---
@app.route("/invoices")
@login_required
def invoice_list():
    """Zobrazí seznam všech vygenerovaných faktur."""
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT jobs.id, jobs.job_number, jobs.job_name, jobs.invoice_date, jobs.payment_status, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.status = 'Fakturovaná'
        ORDER BY jobs.invoice_date DESC
    """).fetchall()
    conn.close()
    return render_template("invoice_list.html", invoices=invoices)

@app.route("/jobs/<int:job_id>/invoice")
@login_required
def generate_invoice(job_id):
    """Generuje a zobrazí jednoduchou fakturu."""
    conn = get_db_connection()
    
    job = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.address, customers.phone, customers.email
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = ?
    """, (job_id,)).fetchone()
    
    hours = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job_id,)).fetchone()['total_hours'] or 0
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job_id,)).fetchall()
    
    total_services_cost = sum(s['cost'] for s in additional_services)
    total_price_hourly = float(hours) * float(job['hourly_rate']) if job['hourly_rate'] else 0
    total_price_fixed = float(job['price']) if job['price'] else 0
    
    total_price = total_price_hourly + total_price_fixed + total_services_cost

    # Nastaví stav zakázky jako fakturovaná a datum, pokud ještě nebylo fakturováno
    if job['status'] != 'Fakturovaná':
        conn.execute("UPDATE jobs SET status = 'Fakturovaná', invoice_date = ? WHERE id = ?", (datetime.date.today().isoformat(), job_id))
        conn.commit()
    
    conn.close()
    if job is None:
        return "Zakázka nenalezena.", 404
        
    return render_template("invoice.html", job=job, hours=hours, total_price=total_price, now_date=datetime.date.today().isoformat(), additional_services=additional_services)


# Routa pro nastavení stavu zakázky jako uhrazené
@app.route("/invoices/<int:job_id>/set_paid", methods=["POST"])
@login_required
def set_invoice_paid(job_id):
    conn = get_db_connection()
    
    job = conn.execute("SELECT price, hourly_rate FROM jobs WHERE id = ?", (job_id,)).fetchone()
    hours = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job_id,)).fetchone()['total_hours'] or 0
    additional_services_cost = conn.execute("SELECT SUM(cost) AS total_cost FROM additional_services WHERE job_id = ?", (job_id,)).fetchone()['total_cost'] or 0
    
    total_price_hourly = float(hours) * float(job['hourly_rate']) if job['hourly_rate'] else 0
    total_price_fixed = float(job['price']) if job['price'] else 0
    total_price = total_price_hourly + total_price_fixed + additional_services_cost
    
    conn.execute("UPDATE jobs SET payment_status = 'Uhrazeno', total_paid = ? WHERE id = ?", (total_price, job_id))
    conn.commit()
    conn.close()
    return redirect(url_for("invoice_list"))

@app.route("/jobs/<int:job_id>/status-done", methods=["POST"])
@login_required
def set_job_status_done(job_id):
    """Mění stav zakázky na 'Dokončená'."""
    conn = get_db_connection()
    conn.execute("UPDATE jobs SET status = 'Dokončená' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))


if __name__ == "__main__":
    app.run(debug=True)
