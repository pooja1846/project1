import os, json
import cgi
from flask import Flask, session, redirect, render_template, request, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from helpers import login_required
from werkzeug.security import check_password_hash, generate_password_hash
import requests
from datetime import datetime
from flask import Flask, session, redirect, url_for, request
from markupsafe import escape

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def home():
        return render_template("login.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    session.clear()
    #if the users submit the form (POST REQUEST)
    if request.method=="POST":
        name = request.form.get("name")

        #if 'name' entry kept blank, error message will be displayed
        if not request.form.get("name"):
            return render_template("error.html", message="Please enter your name")

        #if 'password' entry kept blank, error message will be displayed
        elif not request.form.get("password"):
            return render_template("error.html", message="Please enter password")

        #find username in the database
        rows = db.execute("SELECT * FROM users WHERE name = :name",
                                {"name": name})

        #fetch one result
        result = rows.fetchone()
        # Ensure username exists and password is correct
        if result == None or not check_password_hash(result[4], request.form.get("password")):
            return render_template("error.html", message="Invalid Name and/or password")

        # Remember which user has logged in, then return search box.
        session["user_id"] = result[0]
        session["user_name"] = result[1]

        return render_template("search.html")
    else:
        #if user is new to ,proceed to signup page
        return render_template("signup.html")

@app.route("/signup", methods=["POST", "GET"])
def signup():

    session.clear()
    #if the users submit the form (POST REQUEST)
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        hashedPassword = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)

        userCheck = db.execute("SELECT * FROM users WHERE name = :name",
                          {"name":request.form.get("name")}).fetchone()

        # Check if username already exist
        if userCheck:
            return render_template("error.html", message="username already exist")

        #if 'name' entry kept blank, error message will be displayed

        if not request.form.get("name"):
            return render_template("error.html", message="Please enter your name")

        #if 'password' entry kept blank, error message will be displayed
        elif not request.form.get("password"):
            return render_template("error.html", message="Please set password")

        #if 'mobilel' entry kept blank, error message will be displayed
        elif not request.form.get("mobile"):
            return render_template("error.html", message="Please enter your mobile number")

        #if 'email' entry kept blank, error message will be displayed
        elif not request.form.get("email"):
            return render_template("error.html", message="Please enter your email-id")

        #insert data into database
        db.execute("INSERT INTO users (name, email, mobile, password) VALUES (:name, :email, :mobile, :password)",{"name": name, "email": email, "mobile": mobile,"password": hashedPassword})

        #save changes
        db.commit()

        #take user to search page
        return render_template("success.html", message="You've successfully created your account.")
    else:
        #if user is already a member, proceed to login page
        return redirect("/login")

@app.route("/logout")
def logout():
    """ Log user out """

    # Forget any user ID
    session.clear()
    return render_template("login.html")

@app.route("/search", methods=["GET"])
def search():

    """Logged-in user will use the SEARCH BOX to find the book"""

    #if no arguement is passed in the search box, error message will be displayed.
    if not request.args.get("book"):
        return render_template("error.html", message="Please enter details of the book.")

    #arguements taken from the search box.
    query = "%" + request.args.get("book") + "%"
    query=query.title()
    #rows selected that match the given arguement.
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn LIKE :query OR title LIKE :query OR author LIKE :query LIMIT 9",{"query": query})

    #if no matches are found, error message will be displayed.
    if rows.rowcount == 0:
        return render_template("error.html", message="Sorry! No matches.")

    #gather all the desired information, then return results.
    books = rows.fetchall()
    return render_template("results.html", books=books)

@app.route("/book/<isbn>", methods=['GET','POST'])
@login_required
def book(isbn):
    """ Save user review and load same page with reviews updated."""

    if request.method == "POST":

        # Save current user info
        currentUser = session["user_id"]

        # Fetch form data
        rating = request.form.get("rating")
        comment = request.form.get("comment")

        # Search book_id by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        # Save id into variable
        bookId = row.fetchone() # (id,)
        bookId = bookId[0]

        # Check for user submission (ONLY 1 review/user allowed per book)
        row2 = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})

        # A review already exists
        if row2.rowcount == 1:
            return render_template("error.html",message="You have already submitted a review for this book.")

        # Convert to save into DB
        rating = int(rating)

        db.execute("INSERT INTO reviews (user_id, book_id, comment, rating) VALUES \
                    (:user_id, :book_id, :comment, :rating)",
                    {"user_id": currentUser,
                    "book_id": bookId,
                    "comment": comment,
                    "rating": rating})

        # Commit transactions to DB and close the connection
        db.commit()

        return render_template("success.html", message= "You have successfully added your review. Please go back to your book's page or click HOME.")


    # Take the book ISBN and redirect to his page (GET)
    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn = :isbn",
                        {"isbn": isbn})

        bookInfo = row.fetchall()

        """ GOODREADS reviews """

        # Read API key from env variable
        key = os.getenv("GOODREADS_KEY")

        # Query the api with key and ISBN as parameters
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})

        # Convert the response to JSON
        response = query.json()

        # "Clean" the JSON before passing it to the bookInfo list
        response = response['books'][0]

        # Append it as the second element on the list. [1]
        bookInfo.append(response)

        """ Users reviews """

         # Search book_id by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn})

        # Save id into variable
        book = row.fetchone() # (id,)
        book = book[0]

        # Fetch book reviews
        # Date formatting (https://www.postgresql.org/docs/9.1/functions-formatting.html)
        results = db.execute("SELECT users.name, comment, rating FROM users INNER JOIN reviews ON users.id = reviews.user_id WHERE book_id = :book", {"book": book})

        reviews = results.fetchall()

        return render_template("book.html", bookInfo=bookInfo, reviews=reviews)
