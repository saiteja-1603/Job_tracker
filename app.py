from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection


app = Flask(__name__)

# Secret key for sessions and flash messages
app.secret_key = "change-this-secret-key"


# ============================================================
# CONSTANTS
# ============================================================

STATUSES = [
    "Applied",
    "Under Review",
    "Shortlisted",
    "Interview",
    "Selected",
    "Rejected",
    "Withdrawn"
]

JOB_TYPES = [
    "Full Time",
    "Part Time",
    "Internship",
    "Contract"
]


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return render_template("register.html")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check whether email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                flash("An account with this email already exists.", "warning")
                return render_template("register.html")

            # Hash password
            hashed_password = generate_password_hash(password)

            # Insert user
            cursor.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (%s, %s, %s)
                """,
                (name, email, hashed_password)
            )

            connection.commit()

            flash("Registration successful. Please login.", "success")

            return redirect(url_for("login"))

        except Exception as e:

            if connection:
                connection.rollback()

            print("Registration error:", e)

            flash("Something went wrong. Please try again.", "danger")

            return render_template("register.html")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, name, email, password
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user and check_password_hash(user["password"], password):

                # Store only necessary information in session
                session.clear()

                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                session["user_email"] = user["email"]

                flash("Login successful.", "success")

                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")

        except Exception as e:

            print("Login error:", e)

            flash("Something went wrong. Please try again.", "danger")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Total applications
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM applications
            WHERE user_id = %s
            """,
            (user_id,)
        )

        total_applications = cursor.fetchone()["total"]

        # Count applications by status
        status_counts = {}

        for status in STATUSES:

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM applications
                WHERE user_id = %s
                AND status = %s
                """,
                (user_id, status)
            )

            status_counts[status] = cursor.fetchone()["total"]

        # Recent applications
        cursor.execute(
            """
            SELECT
                id,
                company_name,
                job_role,
                job_type,
                location,
                application_date,
                status
            FROM applications
            WHERE user_id = %s
            ORDER BY application_date DESC, id DESC
            LIMIT 5
            """,
            (user_id,)
        )

        recent_applications = cursor.fetchall()

        return render_template(
            "dashboard.html",
            total_applications=total_applications,
            status_counts=status_counts,
            recent_applications=recent_applications
        )

    except Exception as e:

        print("Dashboard error:", e)

        flash("Unable to load dashboard.", "danger")

        return redirect(url_for("login"))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# VIEW APPLICATIONS
# ============================================================

@app.route("/applications")
def applications():

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                id,
                company_name,
                job_role,
                job_type,
                location,
                application_date,
                job_url,
                status,
                notes,
                created_at
            FROM applications
            WHERE user_id = %s
        """

        params = [user_id]

        # Search
        if search:

            query += """
                AND (
                    company_name LIKE %s
                    OR job_role LIKE %s
                    OR location LIKE %s
                )
            """

            search_value = f"%{search}%"

            params.extend([
                search_value,
                search_value,
                search_value
            ])

        # Filter
        if status and status in STATUSES:

            query += " AND status = %s"

            params.append(status)

        query += """
            ORDER BY application_date DESC, id DESC
        """

        cursor.execute(query, tuple(params))

        applications_list = cursor.fetchall()

        return render_template(
            "applications.html",
            applications=applications_list,
            statuses=STATUSES,
            search=search,
            selected_status=status
        )

    except Exception as e:

        print("Applications error:", e)

        flash("Unable to load applications.", "danger")

        return redirect(url_for("dashboard"))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ADD APPLICATION
# ============================================================

@app.route("/add-application", methods=["GET", "POST"])
def add_application():

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":

        company_name = request.form.get("company_name", "").strip()
        job_role = request.form.get("job_role", "").strip()
        job_type = request.form.get("job_type", "").strip()
        location = request.form.get("location", "").strip()
        application_date = request.form.get("application_date", "").strip()
        job_url = request.form.get("job_url", "").strip()
        status = request.form.get("status", "Applied").strip()
        notes = request.form.get("notes", "").strip()

        # Required fields
        if not company_name or not job_role or not application_date:
            flash(
                "Company name, job role and application date are required.",
                "danger"
            )

            return render_template(
                "add_application.html",
                statuses=STATUSES,
                job_types=JOB_TYPES
            )

        # Validate status
        if status not in STATUSES:
            status = "Applied"

        # Validate job type
        if job_type and job_type not in JOB_TYPES:
            job_type = ""

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO applications
                (
                    user_id,
                    company_name,
                    job_role,
                    job_type,
                    location,
                    application_date,
                    job_url,
                    status,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    company_name,
                    job_role,
                    job_type,
                    location,
                    application_date,
                    job_url,
                    status,
                    notes
                )
            )

            connection.commit()

            flash("Application added successfully.", "success")

            return redirect(url_for("applications"))

        except Exception as e:

            if connection:
                connection.rollback()

            print("Add application error:", e)

            flash("Unable to add application.", "danger")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template(
        "add_application.html",
        statuses=STATUSES,
        job_types=JOB_TYPES
    )


# ============================================================
# EDIT APPLICATION
# ============================================================

@app.route("/edit-application/<int:application_id>", methods=["GET", "POST"])
def edit_application(application_id):

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get application belonging to logged-in user
        cursor.execute(
            """
            SELECT *
            FROM applications
            WHERE id = %s
            AND user_id = %s
            """,
            (application_id, user_id)
        )

        application = cursor.fetchone()

        if not application:

            flash("Application not found.", "danger")

            return redirect(url_for("applications"))

        # Update
        if request.method == "POST":

            company_name = request.form.get(
                "company_name", ""
            ).strip()

            job_role = request.form.get(
                "job_role", ""
            ).strip()

            job_type = request.form.get(
                "job_type", ""
            ).strip()

            location = request.form.get(
                "location", ""
            ).strip()

            application_date = request.form.get(
                "application_date", ""
            ).strip()

            job_url = request.form.get(
                "job_url", ""
            ).strip()

            status = request.form.get(
                "status", "Applied"
            ).strip()

            notes = request.form.get(
                "notes", ""
            ).strip()

            if not company_name or not job_role or not application_date:

                flash(
                    "Company name, job role and application date are required.",
                    "danger"
                )

                application.update({
                    "company_name": company_name,
                    "job_role": job_role,
                    "job_type": job_type,
                    "location": location,
                    "application_date": application_date,
                    "job_url": job_url,
                    "status": status,
                    "notes": notes
                })

                return render_template(
                    "edit_application.html",
                    application=application,
                    statuses=STATUSES,
                    job_types=JOB_TYPES
                )

            if status not in STATUSES:
                status = "Applied"

            if job_type and job_type not in JOB_TYPES:
                job_type = ""

            cursor.execute(
                """
                UPDATE applications
                SET
                    company_name = %s,
                    job_role = %s,
                    job_type = %s,
                    location = %s,
                    application_date = %s,
                    job_url = %s,
                    status = %s,
                    notes = %s
                WHERE id = %s
                AND user_id = %s
                """,
                (
                    company_name,
                    job_role,
                    job_type,
                    location,
                    application_date,
                    job_url,
                    status,
                    notes,
                    application_id,
                    user_id
                )
            )

            connection.commit()

            flash("Application updated successfully.", "success")

            return redirect(url_for("applications"))

        return render_template(
            "edit_application.html",
            application=application,
            statuses=STATUSES,
            job_types=JOB_TYPES
        )

    except Exception as e:

        if connection:
            connection.rollback()

        print("Edit application error:", e)

        flash("Unable to update application.", "danger")

        return redirect(url_for("applications"))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE APPLICATION
# ============================================================

@app.route(
    "/delete-application/<int:application_id>",
    methods=["POST"]
)
def delete_application(application_id):

    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM applications
            WHERE id = %s
            AND user_id = %s
            """,
            (
                application_id,
                session["user_id"]
            )
        )

        connection.commit()

        if cursor.rowcount == 0:

            flash("Application not found.", "danger")

        else:

            flash(
                "Application deleted successfully.",
                "success"
            )

    except Exception as e:

        if connection:
            connection.rollback()

        print("Delete application error:", e)

        flash(
            "Unable to delete application.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("applications"))


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)