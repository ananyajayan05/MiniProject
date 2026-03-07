from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Route for Home Page
@app.route('/')
def index():
    return render_template('index.html')

# Route for Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # 1. Get data from form
        username = request.form.get('username')
        password = request.form.get('password')
        # 2. Save to Database (Logic goes here)
        print(f"New User: {username}") 
        return redirect(url_for('login'))
    return render_template('signup.html')

# Route for Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Validate user credentials here
        return redirect(url_for('index'))
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)