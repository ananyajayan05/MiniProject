import pandas as pd
import sqlite3
import atexit
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from medicines import medicines  # keep your medicines JSON
import pytesseract
from PIL import Image
import os
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
app = Flask(__name__)
app.secret_key = "medinsta_secret"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# --- SQLite setup ---
conn = sqlite3.connect("medinsta.db", check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS pharmacies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    pincode TEXT,
    phone TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    medicine TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS pharmacy_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_name TEXT,
    email TEXT UNIQUE,
    password TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS pharmacy_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacy_email TEXT,
    medicine TEXT,
    quantity INTEGER
)
""")
conn.commit()

# --- Load CSV pharmacies into DB if empty ---
df = pd.read_csv("pharmacies_kannur.csv")
for _, row in df.iterrows():
    c.execute("SELECT * FROM pharmacies WHERE name=? AND pincode=?", (row['name'], str(row['pincode'])))
    if not c.fetchone():
        c.execute(
            "INSERT INTO pharmacies (name, pincode, phone) VALUES (?, ?, ?)",
            (row['name'], str(row['pincode']), row.get('phone', 'N/A'))
        )
conn.commit()

# ---------------- HOME ----------------
@app.route('/')
def home():
    user_name = session.get("user")
    return render_template("index.html", user_name=user_name)

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']   # DO NOT HASH HERE

        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()

        if user and check_password_hash(user[2], password):
            session["user"] = email
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        try:
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="Email already exists")
    return render_template("signup.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ---------------- ADMIN SIGNUP ----------------
@app.route("/admin-signup", methods=["GET","POST"])
def admin_signup():

    if request.method == "POST":

        try:
            email = request.form["email"]
            password = generate_password_hash(request.form["password"])

            c.execute(
                "INSERT INTO admins (email,password) VALUES (?,?)",
                (email,password)
            )

            conn.commit()

            return redirect("/admin-login")

        except sqlite3.IntegrityError:
            return render_template("admin_signup.html", error="Admin already exists")

    return render_template("admin_signup.html")


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin-login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        c.execute("SELECT * FROM admins WHERE email=?", (email,))
        admin = c.fetchone()

        if admin and check_password_hash(admin[2], password):

            session["admin"] = email
            return redirect("/admin-dashboard")

        else:
            return render_template("admin_login.html", error="Invalid admin login")

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin-dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin-login")

    c.execute("SELECT email FROM users")
    users = c.fetchall()

    c.execute("SELECT pharmacy_name,email FROM pharmacy_users")
    pharmacies = c.fetchall()

    return render_template("admin_dashboard.html", users=users, pharmacies=pharmacies)

# ---------------- SEARCH PAGE ----------------
@app.route('/search')
def search_page():
    query = request.args.get('query','').lower()
    results = [m for m in medicines if query in m['name'].lower()]
    return render_template("search_results.html", medicines=results, query=query)

# ---------------- SEARCH API (AJAX) ----------------
@app.route('/api/search')
def search():
    query = request.args.get('query','').lower()
    results = [m for m in medicines if query in m['name'].lower()]
    return jsonify(results)

# ---------------- CATEGORY API ----------------
@app.route('/api/category/<condition>')
def category(condition):
    results = [m for m in medicines if condition.lower() in m['generic'].lower()]
    return jsonify(results)

# ---------------- CONDITION PAGE ----------------
@app.route('/condition/<condition>')
def condition_page(condition):
    query_pincode = request.args.get("pincode")
    results = [m for m in medicines if condition.lower() in m['generic'].lower()]

    # Add pharmacy info for selected pincode
    if query_pincode:
        c.execute("SELECT * FROM pharmacies WHERE pincode=?", (query_pincode,))
        nearby_pharmacies = c.fetchall()
        for m in results:
            m["pharmacy"] = nearby_pharmacies[0][1] if nearby_pharmacies else "N/A"
            m["price"] = 100  # placeholder price
    return render_template("condition.html", medicines=results, condition=condition)

# ---------------- PHARMACY SEARCH BY PINCODE ----------------
@app.route("/pharmacy-search")
def pharmacy_search():
    pincode = request.args.get("pincode")
    if not pincode:
        return jsonify([])
    c.execute("SELECT * FROM pharmacies WHERE pincode=?", (pincode,))
    rows = c.fetchall()
    results = [{"id": r[0], "name": r[1], "pincode": r[2], "phone": r[3]} for r in rows]
    return jsonify(results)

# ---------------- PHARMACY PAGE ---------------

# ---------------- RESTOCK ALERT ----------------
@app.route("/api/alerts", methods=["POST"])
def alerts():
    data = request.json
    email = data.get("email")
    medicine = data.get("medicine")

    c.execute("INSERT INTO alerts (email, medicine) VALUES (?, ?)", (email, medicine))
    conn.commit()

    return jsonify({"message":"Alert registered successfully"})

 # ---------------- STOCK RESULTS PAGE ----------------
@app.route('/stock-results')
def stock_results():

    query = request.args.get('query', '').lower()
    pincode = request.args.get('pincode')

    if not query or not pincode:
        return redirect(url_for("home"))

    # Find medicines matching query
    results = [m for m in medicines if query in m['name'].lower()]

    # CHECK PHARMACY STOCK
    c.execute(
    "SELECT pharmacy_email, quantity FROM pharmacy_stock WHERE medicine LIKE ?",
    ('%'+query+'%',)
    )

    stock_info = c.fetchall()

    for m in results:
        if stock_info:
            m["stock"] = stock_info[0][1]
            m["pharmacy_email"] = stock_info[0][0]
        else:
            m["stock"] = "Out of stock"

    return render_template("search_results.html", medicines=results)
@app.route("/stock")
def stock():
    return render_template("stock.html")

@app.route("/generic")
def generic():
    return render_template("generic.html")

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

@app.route("/offers")
def offers():
    return render_template("offers.html")
@app.route("/api/autocomplete")
def autocomplete():
    query = request.args.get("query","").lower()

    suggestions = [
        m["name"] for m in medicines 
        if query in m["name"].lower()
    ][:10]

    return jsonify(suggestions)
@app.route("/pharmacies")
def pharmacies_page():

    pincode = request.args.get("pincode")

    if not pincode:
        return "Pincode not provided"

    c.execute("SELECT * FROM pharmacies WHERE pincode=?", (pincode,))
    rows = c.fetchall()

    pharmacies = []

    for r in rows:
        pharmacies.append({
            "name": r[1],
            "pincode": r[2],
            "phone": r[3]
        })

    return render_template("pharmacy_results.html", pharmacies=pharmacies)
@atexit.register
def close_db():
    conn.close()
# ---------Pharmacy Register-----------
@app.route("/pharmacy-register", methods=["GET", "POST"])
def pharmacy_register():

    if request.method == "POST":
        name = request.form["pharmacy_name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            c.execute(
                "INSERT INTO pharmacy_users (pharmacy_name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
            return redirect("/pharmacy-login")

        except sqlite3.IntegrityError:
            return "Pharmacy already exists"

    return render_template("pharmacy_register.html")

#-----------Pharmacy Login------------
@app.route("/pharmacy-login", methods=["GET", "POST"])
def pharmacy_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        c.execute("SELECT * FROM pharmacy_users WHERE email=?", (email,))
        user = c.fetchone()

        if user and check_password_hash(user[3], password):
            session["pharmacy"] = email
            return redirect("/pharmacy-dashboard")

        else:
            return "Invalid login"

    return render_template("pharmacy_login.html")

#------------Pharmacy dashboard-------------
@app.route("/pharmacy-dashboard")
def pharmacy_dashboard():

    if "pharmacy" not in session:
        return redirect("/pharmacy-login")

    return "Welcome Pharmacy Dashboard"


@app.route("/upload-prescription", methods=["POST"])
def upload_prescription():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty file"})

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # OCR
    image = Image.open(filepath).convert("L")

    text = pytesseract.image_to_string(
        image,
        config="--oem 3 --psm 6"
    )

    print("OCR TEXT:\n", text)   # DEBUG

    # Match medicines
    results = []
    text_lower = text.lower()

    for m in medicines:
        pattern = re.escape(m["name"].lower())
        if re.search(pattern, text_lower):
            results.append(m)

    return jsonify({
        "text": text,
        "medicines": results
    })
# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(debug=True)