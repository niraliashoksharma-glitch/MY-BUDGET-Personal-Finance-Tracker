from flask import Flask, render_template, request, redirect, session, url_for
from db import get_connection

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- INDEX ----------------
@app.route("/")
def index():
    return redirect(url_for("login"))

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["name"]
        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["name"] = user[1]
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        budget = float(request.form["budget"])

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, password, budget) VALUES (%s,%s,%s,%s) RETURNING id",
            (name, email, password, budget)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        session["user_id"] = user_id
        session["name"] = name
        return redirect(url_for("dashboard"))
    return render_template("signup.html")

# ---------------- DASHBOARD ----------------
# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_connection()
    cur = conn.cursor()

    # Get budget
    cur.execute("SELECT budget FROM users WHERE id=%s", (user_id,))
    budget = cur.fetchone()[0] or 0

    # Total Expenses
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=%s", (user_id,))
    total_expense = cur.fetchone()[0] or 0

    # Total Income
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM income WHERE user_id=%s", (user_id,))
    total_income = cur.fetchone()[0] or 0

    remaining = budget - total_expense

    # Monthly Expenses Line Chart (week numbers)
    cur.execute("""
        SELECT EXTRACT(WEEK FROM date) AS week, COALESCE(SUM(amount),0)
        FROM expenses
        WHERE user_id=%s
        GROUP BY week
        ORDER BY week
    """, (user_id,))
    monthly_data = cur.fetchall()
    months = [int(m[0]) for m in monthly_data] if monthly_data else []
    monthly_totals = [float(m[1]) for m in monthly_data] if monthly_data else []

    # Category-wise Expenses Pie Chart
    cur.execute("""
        SELECT category, COALESCE(SUM(amount),0)
        FROM expenses
        WHERE user_id=%s
        GROUP BY category
    """, (user_id,))
    category_data = cur.fetchall()
    categories = [c[0] for c in category_data] if category_data else []
    category_values = [float(c[1]) for c in category_data] if category_data else []

    cur.close()
    conn.close()

    return render_template("dashboard.html",
                           budget=budget,
                           total_expense=total_expense,
                           total_income=total_income,
                           remaining=remaining,
                           months=months,
                           monthly_totals=monthly_totals,
                           categories=categories,
                           category_values=category_values)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#---------------------PROFILE----------------
from werkzeug.security import generate_password_hash, check_password_hash

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/")

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        budget = request.form["budget"]
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        # Update name, email, budget
        cur.execute("""
            UPDATE users
            SET name=%s, email=%s, budget=%s
            WHERE id=%s
        """, (name, email, budget, session["user_id"]))

        # If password change requested
        if current_password and new_password:
            cur.execute("SELECT password FROM users WHERE id=%s",
                        (session["user_id"],))
            stored_password = cur.fetchone()[0]

            if check_password_hash(stored_password, current_password):
                hashed_new = generate_password_hash(new_password)
                cur.execute("UPDATE users SET password=%s WHERE id=%s",
                            (hashed_new, session["user_id"]))

        conn.commit()

    # Get updated user info
    cur.execute("SELECT * FROM users WHERE id=%s",
                (session["user_id"],))
    user = cur.fetchone()

    conn.close()

    return render_template("manage_profile.html", user={
        "id": user[0],
        "name": user[1],
        "email": user[2],
        "password": user[3],
        "budget": user[4]
    })
#-----------------INCOME ROUTE----------------
@app.route("/income", methods=["GET", "POST"])
def income():
    if "user_id" not in session:
        return redirect("/")

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        cur.execute("""
            INSERT INTO income (user_id, amount, category, date)
            VALUES (%s, %s, %s, %s)
        """, (session["user_id"], amount, category, date))

        conn.commit()

    # Fetch incomes
    cur.execute("""
        SELECT id,amount,category,date FROM income
        WHERE user_id=%s
        ORDER BY date DESC
    """, (session["user_id"],))
    incomes = cur.fetchall()

    # Total income
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM income
        WHERE user_id=%s
    """, (session["user_id"],))
    total_income = cur.fetchone()[0]

    # Monthly income
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM income
        WHERE user_id=%s
        AND DATE_TRUNC('month', date) = DATE_TRUNC('month', CURRENT_DATE)
    """, (session["user_id"],))
    monthly_income = cur.fetchone()[0]

    conn.close()

    return render_template("income.html",
                           incomes=incomes,
                           total_income=total_income,
                           monthly_income=monthly_income)

#----------------DELETE_INCOME ROUTE----------------
@app.route("/delete_income/<int:id>",methods=["POST"])
def delete_income(id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM income
        WHERE id=%s AND user_id=%s
    """, (id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/income")

#-----------------EXPENSE ROUTE----------------
@app.route("/expenses", methods=["GET", "POST"])
def expenses():
    if "user_id" not in session:
        return redirect("/")

    conn = get_connection()
    cur = conn.cursor()

    # Add Expense
    if request.method == "POST":
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        cur.execute("""
            INSERT INTO expenses (user_id, amount, category, date)
            VALUES (%s, %s, %s, %s)
        """, (session["user_id"], amount, category, date))

        conn.commit()

    # Fetch Expenses
    cur.execute("""
        SELECT id, amount, category, date
        FROM expenses
        WHERE user_id=%s
        ORDER BY date DESC
    """, (session["user_id"],))

    expenses = cur.fetchall()

    # Total Expense
    cur.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM expenses
        WHERE user_id=%s
    """, (session["user_id"],))

    total_expense = cur.fetchone()[0]

    conn.close()

    return render_template("expenses.html",
                           expenses=expenses,
                           total_expense=total_expense)
#----------------DELETE_EXPENSE ROUTE----------------
@app.route("/delete_expense/<int:id>", methods=["POST"])
def delete_expense(id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM expenses
        WHERE id=%s AND user_id=%s
    """, (id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/expenses")
# ---------------- REPORT ROUTE ----------------
from flask import render_template, request, redirect, session, send_file
from openpyxl import Workbook
import io
@app.route("/report", methods=["GET", "POST"])
def report():
    if "user_id" not in session:
        return redirect("/")

    expenses = []
    total = 0
    from_date = None
    to_date = None

    if request.method == "POST":
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT amount, category, date
            FROM expenses
            WHERE user_id = %s
            AND date BETWEEN %s AND %s
            ORDER BY date DESC
        """, (session["user_id"], from_date, to_date))

        expenses = cur.fetchall()
        conn.close()

        total = sum([row[0] for row in expenses])

    return render_template(
        "report.html",
        expenses=expenses,
        total=total,
        from_date=from_date,
        to_date=to_date
    )
#----------------EXCEL DOWNLOAD ROUTE----------------
@app.route("/download_report")
def download_report():
    if "user_id" not in session:
        return redirect("/")

    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id = %s
        AND date BETWEEN %s AND %s
        ORDER BY date DESC
    """, (session["user_id"], from_date, to_date))

    data = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Expense Report"

    ws.append(["Amount", "Category", "Date"])

    total = 0
    for row in data:
        ws.append(row)
        total += row[0]

    ws.append(["", "Total", total])

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="expense_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)