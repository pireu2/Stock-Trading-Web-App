import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    stocks = db.execute(
        "SELECT * FROM stocks WHERE user_id = ? GROUP BY stock", session.get("user_id")
    )
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
    cash = cash[0]["cash"]
    total = 0

    for stock in stocks:
        price = lookup(stock["stock"])
        stock["price"] = price["price"]
        stock["total"] = stock["shares"] * stock["price"]
        total += stock["total"]
    total += cash
    return render_template("index.html", stocks=stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        share = request.form.get("shares")

        if not symbol:
            return apology("must provide stock sybol", 400)
        if not share:
            return apology("must provide share amount", 400)

        symbol = symbol.upper()
        stock_price = lookup(symbol)
        if not stock_price:
            return apology("stock not found", 400)

        try:
            share_value = int(share)
            if share_value < 0:
                raise ValueError
        except ValueError:
            return apology("share amount not number", 400)

        price = share_value * stock_price["price"]

        user_id = session.get("user_id")

        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        if user[0]["cash"] < price:
            return apology("insufficient funds", 400)

        new_balance = user[0]["cash"] - price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, user_id)

        existing = db.execute(
            "SELECT * FROM stocks WHERE user_id = ? AND stock = ?", user_id, symbol
        )
        if existing:
            db.execute(
                "UPDATE stocks SET shares = ? WHERE user_id = ? and stock = ?",
                existing[0]["shares"] + share_value,
                user_id,
                symbol,
            )
        else:
            db.execute(
                "INSERT INTO stocks (user_id,stock,shares) VALUES(?,?,?)",
                user_id,
                symbol,
                share_value,
            )

        date, time = str(datetime.datetime.now()).split()
        time = time.split(".")[0]
        db.execute(
            "INSERT INTO history (user_id, type, date, time, stock, shares, price, share_price) VALUES(?,?,?,?,?,?,?,?)",
            user_id,
            "BUY",
            date,
            time,
            symbol,
            share_value,
            price,
            stock_price["price"],
        )

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    history = db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        session.get("user_id"),
    )
    return render_template("history.html", stocks=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            shares = int(shares)
            if shares < 0:
                raise TypeError
        except (ValueError, TypeError):
            return apology("number of shares invalid", 400)
        price = lookup(symbol)
        price["price"] = price["price"] * float(shares)
        if not price:
            return apology("Stock not found", 400)
        return render_template("quoted.html", stock=price)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure password was submitted
        elif not confirm_password:
            return apology("must confirm password", 400)

        if password != confirm_password:
            return apology("passwords don't match", 400)

        if db.execute("SELECT * FROM users WHERE username = ?", username):
            return apology("username already taken", 400)

        hash = generate_password_hash(password)

        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username, hash)

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        share = request.form.get("shares")


        if not symbol:
            return apology("must provide stock sybol", 400)
        if not share:
            return apology("must provide share amount", 400)

        symbol = symbol.upper()
        stock_price = lookup(symbol)
        if not stock_price:
            return apology("stock not found", 400)

        try:
            share_value = int(share)
            if share_value < 0:
                raise ValueError
        except ValueError:
            return apology("share amount not number", 400)

        user_id = session.get("user_id")

        existing = db.execute(
            "SELECT * FROM stocks WHERE user_id = ? AND stock = ?", user_id, symbol
        )
        if not existing:
            return apology("you dont own that stock", 400)
        if existing[0]["shares"] < share_value:
            return apology("you dont own that many shares", 400)

        price = stock_price["price"] * share_value
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        new_balance = user[0]["cash"] + price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, user_id)

        if share_value == existing[0]["shares"]:
            db.execute(
                "DELETE FROM stocks WHERE user_id = ? and stock = ?", user_id, symbol
            )
        else:
            new_share = existing[0]["shares"] - share_value
            db.execute(
                "UPDATE stocks SET shares = ? WHERE user_id = ? and stock = ?",
                new_share,
                user_id,
                symbol,
            )

        date, time = str(datetime.datetime.now()).split()
        time = time.split(".")[0]
        db.execute(
            "INSERT INTO history (user_id, type, date, time, stock, shares, price, share_price) VALUES(?,?,?,?,?,?,?,?)",
            user_id,
            "SELL",
            date,
            time,
            symbol,
            share_value,
            price,
            stock_price["price"],
        )

        return redirect("/")

    else:
        return render_template("sell.html")


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not current_password:
            return apology("must provide current password", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Ensure password was submitted
        elif not confirm_password:
            return apology("must confirm password", 403)

        if password != confirm_password:
            return apology("passwords don't match", 403)

        user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
        if not check_password_hash(user[0]["hash"], current_password):
            return apology("current password invalid", 403)

        hash = generate_password_hash(password)

        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, user[0]["id"])

        return redirect("/login")

    else:
        return render_template("change.html")
