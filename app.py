# File: app.py

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, g, abort
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

    # Tabulka: Pracovníci
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            email TEXT,
            phone TEXT
        );
    """)

    # Tabulka: Odpracované hodiny
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

    # Tabulka: Další služby a náklady
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
    
<<<<<<< HEAD
    # Tabulka: Údaje o dodavateli
=======
    # NOVÁ TABULKA: Údaje o dodavateli
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            address TEXT,
            ico TEXT,
            dic TEXT,
            bank_account TEXT,
            bank_code TEXT,
            variable_symbol TEXT
        );
    """)

<<<<<<< HEAD
    # Tabulka: Faktury
=======
    # Upravení tabulky invoices
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER UNIQUE NOT NULL,
            invoice_number TEXT NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            payment_type TEXT NOT NULL,
            total_price REAL NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'Nezaplaceno',
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
    """Hlavní dashboard s přehledem."""
    conn = get_db_connection()
    jobs_count = conn.execute("SELECT COUNT(id) FROM jobs WHERE status NOT IN ('Dokončená', 'Fakturovaná')").fetchone()[0]
    customers_count = conn.execute("SELECT COUNT(id) FROM customers").fetchone()[0]
    unpaid_invoices_count = conn.execute("SELECT COUNT(id) FROM invoices WHERE payment_status = 'Nezaplaceno'").fetchone()[0]
    
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

    monthly_revenue = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total_paid) AS total
        FROM jobs
        WHERE payment_status = 'Uhrazeno' AND total_paid IS NOT NULL
        GROUP BY month
        ORDER BY month DESC
    """).fetchall()
    
    conn.close()
    return render_template("index.html", jobs_count=jobs_count, customers_count=customers_count, unpaid_invoices_count=unpaid_invoices_count, jobs=jobs, upcoming_jobs=upcoming_jobs, monthly_jobs=monthly_jobs, monthly_revenue=monthly_revenue)

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
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()

        customer_id = None
        customer_choice = request.form.get("customer_choice")

        # Zjistí, zda se vytváří nový zákazník, nebo se používá existující
        if customer_choice == 'new':
            new_customer_name = request.form.get("new_customer_name")
            if not new_customer_name:
                conn.close()
                return "Jméno nového zákazníka je povinné.", 400

            new_company = request.form.get("new_customer_company")
            new_address = request.form.get("new_customer_address")
            new_phone = request.form.get("new_customer_phone")
            new_email = request.form.get("new_customer_email")

            cursor.execute("""
                INSERT INTO customers (name, company, address, phone, email)
                VALUES (?, ?, ?, ?, ?)
            """, (new_customer_name, new_company, new_address, new_phone, new_email))
            customer_id = cursor.lastrowid
        
        elif customer_choice == 'existing':
            customer_id = request.form.get("customer_id")
            if not customer_id:
                conn.close()
                return "Musíte vybrat existujícího zákazníka, nebo nemáte žádné zákazníky založené.", 400
        
        else:
            # Tento stav by neměl nastat, pokud formulář funguje správně
            conn.close()
            return "Chybný výběr zákazníka.", 400


        # Následně vloží zakázku s určeným customer_id
        job_number = request.form["job_number"]
        job_name = request.form["job_name"]
        description = request.form["description"]
        status = request.form["status"]
        due_date = request.form["due_date"]
        price = request.form.get("price")
        hourly_rate = request.form.get("hourly_rate")
        
        try:
            cursor.execute("""
                INSERT INTO jobs (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate))
            conn.commit()
            return redirect(url_for("job_list"))
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return f"Zakázka s tímto číslem již existuje. Chyba: {e}", 400
        finally:
            conn.close()
    
    # Pro GET požadavek
    conn = get_db_connection()
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    conn.close()
    return render_template("job_form.html", customers=customers, job=None)

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
    
    if job is None:
        conn.close()
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
        
        conn.execute("""
            UPDATE jobs
            SET job_number = ?, job_name = ?, description = ?, customer_id = ?, status = ?, due_date = ?, price = ?, hourly_rate = ?
            WHERE id = ?
        """, (job_number, job_name, description, customer_id, status, due_date, price, hourly_rate, job_id))
        conn.commit()
        conn.close()
        return redirect(url_for("job_detail", job_id=job_id))
        
    conn.close()
    return render_template("job_form.html", job=job, customers=customers)
    
@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def delete_job(job_id):
    """Smaže zakázku a všechna související data."""
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM hours_spent WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM additional_services WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM invoices WHERE job_id = ?", (job_id,))
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
    
<<<<<<< HEAD
@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    """Smaže zákazníka a všechny jeho související zakázky a data."""
    conn = get_db_connection()
    
    jobs = conn.execute("SELECT id FROM jobs WHERE customer_id = ?", (customer_id,)).fetchall()
    
=======
# NOVÁ ROUTA: Smazání zákazníka a jeho zakázek
@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    """Smaže zákazníka a všechny jeho související zakázky, úkoly, odpracované hodiny a faktury."""
    conn = get_db_connection()
    
    # 1. Najdi všechny zakázky daného zákazníka
    jobs = conn.execute("SELECT id FROM jobs WHERE customer_id = ?", (customer_id,)).fetchall()
    
    # 2. Smaž související data (úkoly, hodiny, služby, faktury) pro každou zakázku
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    for job in jobs:
        job_id = job['id']
        conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM hours_spent WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM additional_services WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM invoices WHERE job_id = ?", (job_id,))
    
<<<<<<< HEAD
    conn.execute("DELETE FROM jobs WHERE customer_id = ?", (customer_id,))
=======
    # 3. Smaž samotné zakázky
    conn.execute("DELETE FROM jobs WHERE customer_id = ?", (customer_id,))
    
    # 4. Smaž zákazníka
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for("customer_list"))
    
<<<<<<< HEAD
=======
# NOVÁ ROUTA: Historie zakázek pro zákazníka
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
@app.route("/customers/<int:customer_id>/history")
@login_required
def customer_history(customer_id):
    """Zobrazí historii zakázek pro konkrétního zákazníka."""
    conn = get_db_connection()
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
<<<<<<< HEAD
    
    if customer is None:
        conn.close()
        return "Zákazník nenalezen.", 404
        
    jobs = conn.execute("SELECT * FROM jobs WHERE customer_id = ? ORDER BY due_date DESC", (customer_id,)).fetchall()
    conn.close()
    
=======
    jobs = conn.execute("SELECT * FROM jobs WHERE customer_id = ? ORDER BY due_date DESC", (customer_id,)).fetchall()
    conn.close()
    
    if customer is None:
        return "Zákazník nenalezen.", 404
        
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    return render_template("customer_history.html", customer=customer, jobs=jobs)

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
    """API pro přepnutí stavu úkolu."""
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

<<<<<<< HEAD
@app.route("/workers/<int:worker_id>/delete", methods=["POST"])
@login_required
def delete_worker(worker_id):
    """Smaže pracovníka."""
    conn = get_db_connection()
    conn.execute("UPDATE hours_spent SET worker_id = NULL WHERE worker_id = ?", (worker_id,))
=======
# NOVÁ ROUTA: Smazání pracovníka
@app.route("/workers/<int:worker_id>/delete", methods=["POST"])
@login_required
def delete_worker(worker_id):
    """Smaže pracovníka a jeho přiřazení k odpracovaným hodinám."""
    conn = get_db_connection()
    # 1. Odstraň přiřazení pracovníka z odpracovaných hodin
    conn.execute("UPDATE hours_spent SET worker_id = NULL WHERE worker_id = ?", (worker_id,))
    # 2. Smaž samotného pracovníka
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("worker_list"))
    
<<<<<<< HEAD
@app.route("/workers/<int:worker_id>")
@login_required
def worker_detail(worker_id):
    """Zobrazí detail konkrétního pracovníka."""
=======
# NOVÁ ROUTA: Detail pracovníka
@app.route("/workers/<int:worker_id>")
@login_required
def worker_detail(worker_id):
    """Zobrazí detail konkrétního pracovníka a jeho přiřazené zakázky."""
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn = get_db_connection()
    worker = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    
    if worker is None:
        conn.close()
        return "Pracovník nenalezen.", 404
        
    jobs = conn.execute("""
        SELECT jobs.*, SUM(hours_spent.hours) AS total_hours
        FROM hours_spent
        LEFT JOIN jobs ON hours_spent.job_id = jobs.id
        WHERE hours_spent.worker_id = ?
        GROUP BY jobs.id
<<<<<<< HEAD
        ORDER BY jobs.due_date DESC
=======
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    """, (worker_id,)).fetchall()
    
    conn.close()
    return render_template("worker_detail.html", worker=worker, jobs=jobs)

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
<<<<<<< HEAD
        SELECT 
            invoices.*, 
            jobs.job_name, 
            customers.name AS customer_name
=======
        SELECT invoices.*, jobs.job_number, jobs.job_name, jobs.invoice_date, jobs.payment_status, customers.name AS customer_name
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
        FROM invoices
        LEFT JOIN jobs ON invoices.job_id = jobs.id
        LEFT JOIN customers ON jobs.customer_id = customers.id
        ORDER BY invoices.invoice_date DESC
    """).fetchall()
    conn.close()
    return render_template("invoice_list.html", invoices=invoices)

<<<<<<< HEAD
=======
# NOVÁ ROUTA: Odstranění faktury
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
@app.route("/invoices/<int:invoice_id>/delete", methods=["POST"])
@login_required
def delete_invoice(invoice_id):
    """Smaže fakturu."""
<<<<<<< HEAD
=======
    conn = get_db_connection()
    conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("invoice_list"))

@app.route("/jobs/<int:job_id>/generate-invoice-form")
@login_required
def generate_invoice_form(job_id):
    """Zobrazí formulář pro vygenerování faktury."""
    return render_template("invoice_form.html", job_id=job_id)

@app.route("/jobs/<int:job_id>/create-invoice", methods=["POST"])
@login_required
def create_invoice(job_id):
    """Uloží fakturu do databáze a přesměruje na její náhled."""
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn = get_db_connection()
    conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("invoice_list"))

@app.route("/jobs/<int:job_id>/create-invoice", methods=["POST"])
@login_required
def create_invoice(job_id):
    """Vytvoří fakturu v databázi."""
    conn = get_db_connection()
    
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        conn.close()
        return "Zakázka nenalezena.", 404

    hours_data = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job_id,)).fetchone()
    hours = hours_data['total_hours'] if hours_data['total_hours'] is not None else 0
    
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job_id,)).fetchall()
    
    total_services_cost = sum(s['cost'] for s in additional_services)
    total_price_hourly = float(hours) * float(job['hourly_rate']) if job['hourly_rate'] else 0
    total_price_fixed = float(job['price']) if job['price'] else 0
    total_price = total_price_hourly + total_price_fixed + total_services_cost
    
    invoice_number = request.form["invoice_number"]
    payment_type = request.form["payment_type"]
    invoice_date = datetime.date.today().isoformat()
    due_date = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (job_id, invoice_number, invoice_date, due_date, payment_type, total_price, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, invoice_number, invoice_date, due_date, payment_type, total_price, "Nezaplaceno"))
        
        conn.execute("UPDATE jobs SET status = 'Fakturovaná' WHERE id = ?", (job_id,))
        conn.commit()
        
        invoice_id = cursor.lastrowid
        conn.close()
        return redirect(url_for('view_invoice', invoice_id=invoice_id))
    except sqlite3.IntegrityError:
        conn.close()
        return "Faktura pro tuto zakázku již existuje.", 400


@app.route("/invoices/<int:invoice_id>/view")
@login_required
def view_invoice(invoice_id):
    """Zobrazí náhled faktury."""
    conn = get_db_connection()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    
    if invoice is None:
        conn.close()
        return "Faktura nenalezena.", 404
    
<<<<<<< HEAD
    job = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.address, customers.phone, customers.email
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = ?
    """, (invoice['job_id'],)).fetchone()

    hours_data = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job['id'],)).fetchone()
    hours = hours_data['total_hours'] if hours_data['total_hours'] is not None else 0
    
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job['id'],)).fetchall()
    
    supplier = conn.execute("SELECT * FROM supplier_info LIMIT 1").fetchone()
=======
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    
    hours = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job_id,)).fetchone()['total_hours'] or 0
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job_id,)).fetchall()
    
    total_services_cost = sum(s['cost'] for s in additional_services)
    total_price_hourly = float(hours) * float(job['hourly_rate']) if job['hourly_rate'] else 0
    total_price_fixed = float(job['price']) if job['price'] else 0
    total_price = total_price_hourly + total_price_fixed + total_services_cost
    
    invoice_number = request.form["invoice_number"]
    payment_type = request.form["payment_type"]
    invoice_date = datetime.date.today().isoformat()
    due_date = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()

    conn.execute("""
        INSERT INTO invoices (job_id, invoice_number, invoice_date, due_date, payment_type, total_price, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (job_id, invoice_number, invoice_date, due_date, payment_type, total_price, "Nezaplaceno"))
    
    conn.execute("UPDATE jobs SET status = 'Fakturovaná' WHERE id = ?", (job_id,))
    conn.commit()
    
    invoice_id = conn.execute("SELECT id FROM invoices WHERE job_id = ?", (job_id,)).fetchone()['id']
    conn.close()
    
    return redirect(url_for('view_invoice', invoice_id=invoice_id))

@app.route("/invoices/<int:invoice_id>/view")
@login_required
def view_invoice(invoice_id):
    """Zobrazí fakturu."""
    conn = get_db_connection()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    
    if invoice is None:
        conn.close()
        return "Faktura nenalezena.", 404
    
    job = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name, customers.company, customers.address, customers.phone, customers.email
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.id = ?
    """, (invoice['job_id'],)).fetchone()

    hours = conn.execute("SELECT SUM(hours) AS total_hours FROM hours_spent WHERE job_id = ?", (job['id'],)).fetchone()['total_hours'] or 0
    additional_services = conn.execute("SELECT * FROM additional_services WHERE job_id = ?", (job['id'],)).fetchall()
    
    total_price = invoice['total_price']
    supplier = conn.execute("SELECT * FROM supplier_info WHERE id = 1").fetchone()
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    
    conn.close()
    if job is None:
        return "Související zakázka nenalezena.", 404
        
<<<<<<< HEAD
    return render_template("invoice.html", job=job, hours=hours, invoice=invoice, additional_services=additional_services, supplier=supplier)


@app.route("/invoices/<int:invoice_id>/set_paid", methods=["POST"])
@login_required
def set_invoice_paid(invoice_id):
    """Označí fakturu jako uhrazenou."""
=======
    return render_template("invoice.html", job=job, hours=hours, total_price=total_price, invoice=invoice, additional_services=additional_services, supplier=supplier)


# Routa pro nastavení stavu zakázky jako uhrazené
@app.route("/invoices/<int:invoice_id>/set_paid", methods=["POST"])
@login_required
def set_invoice_paid(invoice_id):
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn = get_db_connection()
    
    invoice = conn.execute("SELECT job_id, total_price FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        conn.close()
        return "Faktura nenalezena.", 404

    job_id = invoice['job_id']
    total_price = invoice['total_price']
    
    conn.execute("UPDATE invoices SET payment_status = 'Uhrazeno' WHERE id = ?", (invoice_id,))
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

<<<<<<< HEAD
# --- Nastavení ---
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Stránka pro nastavení údajů dodavatele."""
    conn = get_db_connection()
    supplier = conn.execute("SELECT * FROM supplier_info LIMIT 1").fetchone()
=======
# Routa pro stránku nastavení
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db_connection()
    supplier = conn.execute("SELECT * FROM supplier_info WHERE id = 1").fetchone()
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    
    if request.method == "POST":
        company_name = request.form["company_name"]
        address = request.form["address"]
        ico = request.form["ico"]
        dic = request.form["dic"]
        bank_account = request.form["bank_account"]
        bank_code = request.form["bank_code"]
        variable_symbol = request.form["variable_symbol"]
        
        if supplier:
            conn.execute("""
<<<<<<< HEAD
                UPDATE supplier_info SET company_name = ?, address = ?, ico = ?, dic = ?, bank_account = ?, bank_code = ?, variable_symbol = ?
=======
                UPDATE supplier_info
                SET company_name = ?, address = ?, ico = ?, dic = ?, bank_account = ?, bank_code = ?, variable_symbol = ?
                WHERE id = 1
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
            """, (company_name, address, ico, dic, bank_account, bank_code, variable_symbol))
        else:
            conn.execute("""
                INSERT INTO supplier_info (company_name, address, ico, dic, bank_account, bank_code, variable_symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (company_name, address, ico, dic, bank_account, bank_code, variable_symbol))
        conn.commit()
        conn.close()
        return redirect(url_for("settings"))
        
    conn.close()
    return render_template("settings.html", supplier=supplier)

<<<<<<< HEAD
# --- Filtrované pohledy ---
@app.route("/jobs/active")
@login_required
def active_jobs_list():
    """Zobrazí seznam aktivních zakázek."""
=======
# NOVÁ ROUTA pro zobrazení aktivních zakázek
@app.route("/jobs/active")
@login_required
def active_jobs_list():
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn = get_db_connection()
    jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE jobs.status NOT IN ('Dokončená', 'Fakturovaná')
        ORDER BY due_date ASC
    """).fetchall()
    conn.close()
    return render_template("job_list.html", jobs=jobs, title="Aktivní zakázky")

<<<<<<< HEAD
@app.route("/jobs/upcoming")
@login_required
def upcoming_jobs_list():
    """Zobrazí seznam zakázek před termínem."""
=======
# NOVÁ ROUTA pro zobrazení blížících se zakázek
@app.route("/jobs/upcoming")
@login_required
def upcoming_jobs_list():
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
    conn = get_db_connection()
    today = datetime.date.today()
    in_ten_days = today + datetime.timedelta(days=10)
    jobs = conn.execute("""
        SELECT jobs.*, customers.name AS customer_name
        FROM jobs
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE date(jobs.due_date) BETWEEN date(?) AND date(?) AND jobs.status NOT IN ('Dokončená', 'Fakturovaná')
        ORDER BY due_date ASC
    """, (today.isoformat(), in_ten_days.isoformat(),)).fetchall()
    conn.close()
    return render_template("job_list.html", jobs=jobs, title="Zakázky před termínem")

<<<<<<< HEAD
@app.route("/invoices/unpaid")
@login_required
def unpaid_invoices_list():
    """Zobrazí seznam neuhrazených faktur."""
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT 
            invoices.*, 
            jobs.job_name, 
            customers.name AS customer_name
=======

# NOVÁ ROUTA pro zobrazení neuhrazených faktur
@app.route("/invoices/unpaid")
@login_required
def unpaid_invoices_list():
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT invoices.*, jobs.job_number, jobs.job_name, jobs.invoice_date, jobs.payment_status, customers.name AS customer_name
>>>>>>> 53b87cff878a958c3473b9e52886b76ca79a3956
        FROM invoices
        LEFT JOIN jobs ON invoices.job_id = jobs.id
        LEFT JOIN customers ON jobs.customer_id = customers.id
        WHERE invoices.payment_status = 'Nezaplaceno'
        ORDER BY invoices.invoice_date DESC
    """).fetchall()
    conn.close()
    return render_template("invoice_list.html", invoices=invoices, title="Neuhrazené faktury")


if __name__ == "__main__":
    app.run(debug=True)