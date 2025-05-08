#!/usr/bin/env python3
"""ReliefAssist – Flask MVP (v1) with Authentication & Role-based access

Roles & Access:
- Public: dashboard, disasters, resources
- Volunteer: register/login, view `/my-tasks`
- Donor: register/login, view `/my-donations`
- Manager: CRUD on disasters, resources, tasks, volunteers, donors
- Admin: all permissions
"""
from __future__ import annotations
from pathlib import Path
import os
from datetime import date
from typing import List, Dict, Optional, Tuple, Callable

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (
    LoginManager, UserMixin, login_user, current_user,
    login_required, logout_user
)
from werkzeug.security import check_password_hash, generate_password_hash
import mysql.connector
from mysql.connector import Error as MySQLError

# --------------------------------------------------------------------
# Config & DB
# --------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", 3306)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PW", ""),
    database=os.getenv("MYSQL_DB", "reliefassist_db"),
    autocommit=True,
)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "change-me")

# --------------------------------------------------------------------
# Flask-Login setup
# --------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------
def query(sql: str, params: tuple = ()) -> List[Dict]:
    cur = DB.cursor(dictionary=True)
    cur.execute(sql, params)
    res = cur.fetchall()
    cur.close()
    return res

def execute(sql: str, params: tuple = ()) -> None:
    cur = DB.cursor()
    cur.execute(sql, params)
    cur.close()

# --------------------------------------------------------------------
# Helper lists (for managers)
# --------------------------------------------------------------------
def centers() -> List[Tuple[int, str]]:
    return [(r["center_id"], r["name"]) for r in query("SELECT center_id, name FROM ReliefCenter ORDER BY name")]

def resources_master() -> List[Tuple[int, str]]:
    return [(r["resource_id"], r["resource_type"]) for r in query("SELECT resource_id, resource_type FROM Resource ORDER BY resource_type")]

def disasters_master() -> List[Tuple[int, str]]:
    return [(d["disaster_id"], d["name"]) for d in query("SELECT disaster_id, name FROM Disaster ORDER BY name")]

def volunteers_master() -> List[Tuple[int, str]]:
    return [
        (v["volunteer_id"], f"{v['first_name']} {v['last_name']}")
        for v in query("SELECT volunteer_id, first_name, last_name FROM Volunteer ORDER BY last_name")
    ]

def donors_master() -> List[Tuple[int, str]]:
    return [
        (d["donor_id"], f"{d['first_name']} {d['last_name']}")
        for d in query("SELECT donor_id, first_name, last_name FROM Donor ORDER BY last_name")
    ]

# --------------------------------------------------------------------
# User model & role decorator
# --------------------------------------------------------------------
class User(UserMixin):
    def __init__(self, row: Dict):
        self.id = row["user_id"]
        self.email = row["email"]
        self.role = row["role"]

@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    rows = query("SELECT * FROM users WHERE user_id=%s", (int(user_id),))
    return User(rows[0]) if rows else None

def role_required(*allowed_roles: str) -> Callable:
    def wrapper(fn):
        @login_required
        def inner(*args, **kwargs):
            if current_user.role not in allowed_roles and current_user.role != 'admin':
                abort(403)
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return wrapper

# --------------------------------------------------------------------
# Auth & Registration
# --------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].lower()
        pw = request.form["password"]
        role = request.form.get("role", "volunteer")
        if query("SELECT 1 FROM users WHERE email=%s", (email,)):
            flash("Email already registered", "warning")
            return redirect(url_for("register"))
        pw_hash = generate_password_hash(pw)
        execute("INSERT INTO users (email,pw_hash,role) VALUES (%s,%s,%s)", (email, pw_hash, role))
        flash("Registration successful; please log in", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower()
        pw = request.form["password"]
        rows = query("SELECT * FROM users WHERE email=%s", (email,))
        if rows and check_password_hash(rows[0]["pw_hash"], pw):
            login_user(User(rows[0]))
            flash("Logged in", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("dashboard"))


# --------------------------------------------------------------------
# Public routes
# --------------------------------------------------------------------
@app.route("/", methods=["GET"])
def dashboard():
    rows = query("SELECT disaster_id, name, location, start_date, status FROM Disaster ORDER BY start_date DESC LIMIT 10")
    return render_template("dashboard.html", disasters=rows)

@app.route("/disasters")
def disasters():
    rows = query("SELECT * FROM Disaster ORDER BY disaster_id DESC")
    return render_template("disasters.html", disasters=rows)

@app.route("/resources")
def resources_list():
    rows = query(
        "SELECT cr.center_resource_id, rc.name AS center, r.resource_type, cr.quantity_on_hand, rc.capacity, rc.current_load "
        "FROM CenterResource cr JOIN ReliefCenter rc ON rc.center_id=cr.center_id JOIN Resource r ON r.resource_id=cr.resource_id"
    )
    return render_template("resources.html", resources=rows)

# --------------------------------------------------------------------
# Tasks (manager)
# --------------------------------------------------------------------
@app.route("/tasks")
@role_required("manager")
def tasks():
    rows = query(
        "SELECT t.task_id, t.description, t.status, t.due_date, d.name AS disaster, rc.name AS center, COUNT(ta.assignment_id) AS volunteers "
        "FROM Task t LEFT JOIN Disaster d ON d.disaster_id=t.disaster_id "
        "LEFT JOIN ReliefCenter rc ON rc.center_id=t.center_id "
        "LEFT JOIN TaskAssignment ta ON ta.task_id=t.task_id "
        "GROUP BY t.task_id ORDER BY t.due_date IS NULL, t.due_date"
    )
    return render_template("tasks.html", tasks=rows)

@app.route("/task/new", methods=["GET","POST"])
@app.route("/task/<int:task_id>/edit", methods=["GET","POST"])
@role_required("manager")
def task_form(task_id: int | None = None):
    """
    Create a new Task or update an existing one. Also maintains
    TaskAssignment rows for the volunteer multi‑select.
    """
    # -------- fetch (for EDIT) ------------------------------------
    record   = None
    assigned = []          # volunteer_id list pre‑selected in the form
    if task_id is not None:
        res = query(
            "SELECT * FROM Task WHERE task_id = %s",
            (task_id,),
        )
        if res:
            record = res[0]
            assigned = [
                r["volunteer_id"]
                for r in query(
                    "SELECT volunteer_id FROM TaskAssignment WHERE task_id = %s",
                    (task_id,),
                )
            ]
        else:
            abort(404)

    # -------- save (POST) ----------------------------------------
    if request.method == "POST":
        f = request.form
        data = (
            int(f["disaster_id"]),
            int(f["center_id"]) if f.get("center_id") else None,
            f["description"].strip(),
            f.get("due_date") or None,
            f["status"],
        )

        if record:  # UPDATE
            execute(
                "UPDATE Task SET disaster_id = %s, center_id = %s, description = %s, "
                "due_date = %s, status = %s WHERE task_id = %s",
                (*data, task_id),
            )
            execute("DELETE FROM TaskAssignment WHERE task_id = %s", (task_id,))
            flash("Task updated", "success")
        else:       # INSERT
            execute(
                "INSERT INTO Task (disaster_id, center_id, description, due_date, status) "
                "VALUES (%s, %s, %s, %s, %s)",
                data,
            )
            task_id = DB.insert_id()           # grab the new PK
            flash("Task created", "success")

        # (re‑)insert volunteer assignments
        for vid in f.getlist("volunteers"):
            execute(
                "INSERT INTO TaskAssignment (task_id, volunteer_id) VALUES (%s, %s)",
                (task_id, int(vid)),
            )

        return redirect(url_for("tasks"))

    # -------- render form (GET) ----------------------------------
    return render_template(
        "task_form.html",
        task        = record,             # template expects “task”
        disasters   = disasters_master(), # helpers you already have
        centers     = centers(),
        volunteers  = volunteers_master(),
        assigned    = assigned,
        today       = date.today(),
    )
# --------------------------------------------------------------------
# Volunteer portal
# --------------------------------------------------------------------
@app.route("/my-tasks")
@role_required("volunteer")
def my_tasks():
    rows = query(
        "SELECT t.task_id, t.description, t.due_date, t.status, d.name AS disaster, rc.name AS center "
        "FROM TaskAssignment ta JOIN Task t ON t.task_id=ta.task_id "
        "LEFT JOIN Disaster d ON d.disaster_id=t.disaster_id "
        "LEFT JOIN ReliefCenter rc ON rc.center_id=t.center_id "
        "WHERE ta.volunteer_id=%s", (current_user.id,)
    )
    return render_template("volunteer_tasks.html", volunteer={"vname":current_user.email}, tasks=rows)

# --------------------------------------------------------------------
# Donor portal
# --------------------------------------------------------------------
@app.route("/my-donations")
@role_required("donor")
def my_donations():
    rows = query(
        "SELECT n.donation_id, n.donation_type, n.amount, n.donation_date, COALESCE(SUM(da.amount_used),0) AS used_cash, COALESCE(SUM(da.quantity),0) AS allocated_qty "
        "FROM Donation n LEFT JOIN DonationAllocation da ON da.donation_id=n.donation_id "
        "WHERE n.donor_id=%s GROUP BY n.donation_id", (current_user.id,)
    )
    return render_template("donor_detail.html", donor={"donor":current_user.email}, donations=rows)

# --------------------------------------------------------------------
# Admin portal
# --------------------------------------------------------------------
@app.route("/admin")
@role_required("admin")
def admin_panel():
    # existing overall stats
    stats = {
        "disasters": query("SELECT COUNT(*) AS cnt FROM Disaster")[0]["cnt"],
        "resources": query("SELECT COUNT(*) AS cnt FROM Resource")[0]["cnt"],
        "tasks":     query("SELECT COUNT(*) AS cnt FROM Task")[0]["cnt"],
        "volunteers":query("SELECT COUNT(*) AS cnt FROM Volunteer")[0]["cnt"],
        "donors":    query("SELECT COUNT(*) AS cnt FROM Donor")[0]["cnt"],
        "users":     query("SELECT COUNT(*) AS cnt FROM users")[0]["cnt"],
    }

    # new: role breakdown
    role_counts = query("""
        SELECT role, COUNT(*) AS cnt 
        FROM users 
        GROUP BY role
    """)
    # flatten into dict, e.g. { 'admin':1, 'manager':2, ... }
    for row in role_counts:
        stats[row["role"] + "_users"] = row["cnt"]

    return render_template("admin.html", stats=stats)


@app.route("/user/<int:user_id>/remove", methods=["POST"])
@role_required("admin")
def remove_user(user_id):
    execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    flash("User removed","success")
    return redirect(url_for("users_list"))

@app.route("/user/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def change_user_role(user_id):
    new_role = request.form["new_role"]
    execute("UPDATE users SET role=%s WHERE user_id=%s", (new_role, user_id))
    flash("User role updated","success")
    return redirect(url_for("users_list"))


# --------------------------------------------------------------------
# Manager CRUD routes
# --------------------------------------------------------------------
@app.route("/disaster/new", endpoint="disaster_form", methods=["GET","POST"])
@app.route("/disaster/<int:disaster_id>/edit", endpoint="disaster_form", methods=["GET","POST"])
@role_required("manager")
def disaster_form(disaster_id: int | None = None):
    # (implementation omitted)
    return redirect(url_for("disasters"))

@app.route("/users")
@role_required("admin")
def users_list():
    rows = query("SELECT user_id, email, role FROM users ORDER BY email")
    return render_template("users.html", users=rows)


@app.route("/resource/new", endpoint="resource_form", methods=["GET","POST"])
@role_required("manager")
def resource_form(cr_id: int | None = None):
    """
    Create a new CenterResource row or update an existing one.
    """
    # -------- fetch (for EDIT) ------------------------------------
    record = None
    if cr_id is not None:
        rows = query(
            "SELECT center_resource_id, center_id, resource_id, quantity_on_hand "
            "FROM CenterResource WHERE center_resource_id = %s",
            (cr_id,),
        )
        if not rows:
            abort(404)
        record = rows[0]

    # -------- save (POST) ----------------------------------------
    if request.method == "POST":
        center_id        = request.form["center_id"]
        resource_id      = request.form["resource_id"]
        quantity_on_hand = request.form.get("quantity_on_hand", 0)

        if record:  # UPDATE
            execute(
                "UPDATE CenterResource "
                "SET center_id = %s, resource_id = %s, quantity_on_hand = %s "
                "WHERE center_resource_id = %s",
                (center_id, resource_id, quantity_on_hand, cr_id),
            )
            flash("Resource entry updated", "success")
        else:       # INSERT
            execute(
                "INSERT INTO CenterResource (center_id, resource_id, quantity_on_hand) "
                "VALUES (%s, %s, %s)",
                (center_id, resource_id, quantity_on_hand),
            )
            flash("Resource entry created", "success")

        return redirect(url_for("resources_list"))

    # -------- render form (GET) ----------------------------------
    return render_template(
        "resource_form.html",
        record    = record,             # **rename in template if still “rec”**
        centers   = centers(),          # helper you already have
        resources = resources_master(), # helper you already have
    )

@app.route("/volunteers")
@role_required("manager")
def volunteers():
    rows = query("SELECT volunteer_id, first_name, last_name, phone, skills FROM Volunteer ORDER BY last_name")
    return render_template("volunteers.html", volunteers=rows)

@app.route("/volunteer/<int:vol_id>")
@role_required("manager")
def volunteer_tasks_manager(vol_id: int):
    # (implementation omitted)
    return redirect(url_for("volunteers"))

@app.route("/donors")
@role_required("manager")
def donors():
    rows = query(
        "SELECT d.donor_id, CONCAT(d.first_name,' ',d.last_name) AS donor, d.phone, "
        "COUNT(n.donation_id) AS gifts, COALESCE(SUM(n.amount),0) AS cash_total "
        "FROM Donor d LEFT JOIN Donation n ON n.donor_id=d.donor_id GROUP BY d.donor_id ORDER BY donor"
    )
    return render_template("donors.html", donors=rows)

@app.route("/donor/<int:donor_id>")
@role_required("manager")
def donor_detail_manager(donor_id: int):
    # (implementation omitted)
    return redirect(url_for("donors"))

# --------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render_template("layout.html", content="<h2>403 – Forbidden</h2>"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("layout.html", content="<h2>404 – Page Not Found</h2>"), 404

# --------------------------------------------------------------------
# End of file
# --------------------------------------------------------------------
