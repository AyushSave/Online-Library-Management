from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import sqlite3
import os
import shutil
import tempfile

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static"), filename)

# WSGI Middleware to fix URL path when routed via Vercel rewrites
class VercelPathFixer:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        raw_uri = (
            environ.get("HTTP_X_MATCHED_PATH") or
            environ.get("RAW_URI") or
            environ.get("REQUEST_URI") or
            ""
        )
        if raw_uri:
            path = raw_uri.split("?")[0]
            if path and path not in ("/api/index", "/api/index.py"):
                environ["PATH_INFO"] = path
        if environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixer(app.wsgi_app)

# Database path (handles local dev and Vercel serverless temporary writable storage)
if os.environ.get("VERCEL"):
    DB_PATH = os.path.join(tempfile.gettempdir(), "library.db")
else:
    DB_PATH = os.path.join(BASE_DIR, "library.db")


# -----------------------------------
# DATABASE CONNECTION
# -----------------------------------

def init_db():
    # In Vercel serverless environments, only /tmp is writable
    if os.environ.get("VERCEL"):
        bundled_db = os.path.join(BASE_DIR, "library.db")
        if os.path.exists(bundled_db) and not os.path.exists(DB_PATH):
            shutil.copy2(bundled_db, DB_PATH)
    if not os.path.exists(DB_PATH):
        create_database()


def get_db_connection():
    if not os.path.exists(DB_PATH):
        init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# -----------------------------------
# CREATE DATABASE AND TABLES
# -----------------------------------

def create_database():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Students Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            course TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)

    # Books Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT,
            quantity INTEGER NOT NULL
        )
    """)

    # Issued Books Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issued_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            fine INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Issued',

            FOREIGN KEY (student_id)
            REFERENCES students(id),

            FOREIGN KEY (book_id)
            REFERENCES books(id)
        )
    """)

    conn.commit()
    conn.close()

# Ensure database and tables are ready upon load
init_db()


# -----------------------------------
# HOME PAGE
# -----------------------------------

@app.route("/")
@app.route("/api/index")
@app.route("/api/index.py")
def home():

    conn = get_db_connection()

    student_count = conn.execute(
        "SELECT COUNT(*) AS total FROM students"
    ).fetchone()["total"]

    book_count = conn.execute(
        "SELECT COUNT(*) AS total FROM books"
    ).fetchone()["total"]

    issued_count = conn.execute(
        "SELECT COUNT(*) AS total FROM issued_books WHERE status = 'Issued'"
    ).fetchone()["total"]

    conn.close()

    return render_template(
        "index.html",
        student_count=student_count,
        book_count=book_count,
        issued_count=issued_count
    )


# -----------------------------------
# ADD STUDENT
# -----------------------------------

@app.route("/add_student", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":

        name = request.form["name"]
        roll_no = request.form["roll_no"]
        course = request.form["course"]
        email = request.form["email"]
        phone = request.form["phone"]

        conn = get_db_connection()

        try:

            conn.execute("""
                INSERT INTO students
                (name, roll_no, course, email, phone)
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                roll_no,
                course,
                email,
                phone
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return """
            <h2>Roll Number already exists!</h2>
            <a href="/add_student">Go Back</a>
            """

        conn.close()

        return redirect(url_for("students"))

    return render_template("add_student.html")


# -----------------------------------
# STUDENTS PAGE
# -----------------------------------

@app.route("/students")
def students():

    conn = get_db_connection()

    students_data = conn.execute("""
        SELECT * FROM students
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=students_data
    )


# -----------------------------------
# DELETE STUDENT
# -----------------------------------

@app.route("/delete_student/<int:id>")
def delete_student(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM students WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("students"))


# -----------------------------------
# ADD BOOK
# -----------------------------------

@app.route("/add_book", methods=["GET", "POST"])
def add_book():

    if request.method == "POST":

        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        quantity = request.form["quantity"]

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO books
            (title, author, category, quantity)
            VALUES (?, ?, ?, ?)
        """, (
            title,
            author,
            category,
            quantity
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("books"))

    return render_template("add_book.html")


# -----------------------------------
# BOOKS PAGE
# -----------------------------------

@app.route("/books")
def books():

    conn = get_db_connection()

    books_data = conn.execute("""
        SELECT * FROM books
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "books.html",
        books=books_data
    )


# -----------------------------------
# DELETE BOOK
# -----------------------------------

@app.route("/delete_book/<int:id>")
def delete_book(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM books WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("books"))


# -----------------------------------
# ISSUE BOOK
# -----------------------------------

@app.route("/issue_book", methods=["GET", "POST"])
def issue_book():

    conn = get_db_connection()

    # Get students
    students_data = conn.execute("""
        SELECT * FROM students
        ORDER BY name
    """).fetchall()

    # Get books having quantity greater than 0
    books_data = conn.execute("""
        SELECT * FROM books
        WHERE quantity > 0
        ORDER BY title
    """).fetchall()

    if request.method == "POST":

        student_id = request.form["student_id"]
        book_id = request.form["book_id"]
        issue_date = request.form["issue_date"]
        due_date = request.form["due_date"]

        # Check book quantity
        book = conn.execute("""
            SELECT quantity
            FROM books
            WHERE id = ?
        """, (book_id,)).fetchone()

        if book is None or book["quantity"] <= 0:

            conn.close()

            return """
            <h2>Book is not available!</h2>
            <a href="/issue_book">Go Back</a>
            """

        # Insert issue record
        conn.execute("""
            INSERT INTO issued_books
            (student_id, book_id, issue_date, due_date)
            VALUES (?, ?, ?, ?)
        """, (
            student_id,
            book_id,
            issue_date,
            due_date
        ))

        # Decrease book quantity
        conn.execute("""
            UPDATE books
            SET quantity = quantity - 1
            WHERE id = ?
        """, (book_id,))

        conn.commit()
        conn.close()

        return redirect(url_for("issued_books"))

    conn.close()

    return render_template(
        "issue_book.html",
        students=students_data,
        books=books_data
    )


# -----------------------------------
# ISSUED BOOKS PAGE
# -----------------------------------

@app.route("/issued_books")
def issued_books():

    conn = get_db_connection()

    issued_data = conn.execute("""
        SELECT
            issued_books.id,
            students.name AS student_name,
            students.roll_no,
            books.title AS book_title,
            issued_books.issue_date,
            issued_books.due_date,
            issued_books.return_date,
            issued_books.fine,
            issued_books.status

        FROM issued_books

        JOIN students
        ON issued_books.student_id = students.id

        JOIN books
        ON issued_books.book_id = books.id

        ORDER BY issued_books.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "issued_books.html",
        issued_books=issued_data
    )


# -----------------------------------
# RUN APPLICATION
# -----------------------------------

if __name__ == "__main__":

    create_database()

    app.run(debug=True)