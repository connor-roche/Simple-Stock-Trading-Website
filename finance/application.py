from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    #get symbol and number of stocks from the portfolio
    stocks = db.execute("SELECT shares, symbol FROM portfolio WHERE id = :id", id=session["user_id"])
    
    #get user initial cash
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    grand_total = cash[0]["cash"]
    
    #get info for html table
    for stock in stocks:
        symbol = stock["symbol"]
        shares = stock["shares"]
        stock = lookup(symbol)
        total_value = shares * stock["price"]
        grand_total += total_value
        #update portfolio with real time prices
        db.execute("UPDATE portfolio SET price=:price, total=:total WHERE id=:id AND symbol=:symbol", price=usd(stock["price"]), total=usd(total_value), id=session["user_id"], symbol=symbol)
        
    #get realtime portfolio to load into html
    real_portfolio = db.execute("SELECT * FROM portfolio where id=:id", id=session["user_id"])
    
    #render template
    return render_template("index.html", stocks=real_portfolio, cash=usd(cash[0]["cash"]), grandtotal=usd(grand_total))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    if request.method == "POST":
        
        #define commonly used variables
        stock = lookup(request.form.get("symbol"))
        stock_number = int(request.form.get("shares"))
    
        #check symbol
        if not stock:
            return apology("Invalid ticker symbol. Please re-enter")
        
        #check number of shares    
        if stock_number < 0:
            return apology("Please enter a positive number of shares")
        
        #get the users amount of money    
        user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        
        #check if enough
        if not user_cash or float(user_cash[0]["cash"]) < stock["price"] * stock_number:
            return apology("Not enough money to buy")
            
        #update the user history
        db.execute("INSERT INTO history (id, action, symbol, shares, price) VALUES(:id, :action, :symbol, :shares, :price)", id=session["user_id"], action="buy", symbol=stock["symbol"], shares=stock_number, price=usd(stock["price"]))
        
        #update user table
        db.execute("UPDATE users SET cash = cash - :stocks WHERE id = :id", id=session["user_id"], stocks=stock["price"] * float(stock_number))
        
        #select user shares of the stock being bought
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=stock["symbol"])
        
        #check if the user is adding it into the portfolio for the first time or adding more of an already had stock
        if not user_shares:
            db.execute ("INSERT INTO portfolio (id, name, symbol, price, shares, total) VALUES(:id, :name, :symbol, :price, :shares, :total)", id=session["user_id"], name=stock["name"], symbol=stock["symbol"], price=usd(stock["price"]), shares=stock_number, total=usd(stock["price"] * stock_number))
        
        else:
            db.execute("UPDATE portfolio SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=user_shares[0]["shares"] + stock_number, id=session["user_id"], symbol=stock["symbol"])
            
        #back to homapage
        return redirect(url_for("index"))
        
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    #gather info for the table
    histories = db.execute("SELECT * FROM history WHERE id = :id", id=session["user_id"])
    
    #disaply info on the table
    return render_template("history.html", histories=histories)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    #get the quote and return it as a rendered page
    if request.method == "POST":
        price = lookup(request.form.get("symbol"))
        
        if not price:
            return apology("Invalid ticker symbol. Please re-enter")
    
        return render_template("quoted.html", stock=price)
    #if not then return to quote page
    else:
        return render_template("quote.html")
        
@app.route("/register", methods=["GET", "POST"])
def register():
    #input name = "name"     request.form.get("name")
    #pwd_context.encrypt
    
    if request.method == "POST":
        
        #check for username
        if not request.form.get("username"):
            return apology("Please enter a valid username")
        
        #check for first password
        elif not request.form.get("password"):
            return apology("Please enter a valid password")
            
        #check for second passowrd
        elif not request.form.get("password_confirm"):
            return apology("Please enter a valid password")
        
        #check that both passwords match
        elif request.form.get("password") != request.form.get("password_confirm"):
            return apology("Please make sure both passwords match")
        
        #store user    
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=pwd_context.encrypt(request.form.get("password")))
        
        if not result:
            return apology("Username already exists")
        
        #remember the user
        session["user_id"] = result
        
        #after register go to home page
        return redirect(url_for("index"))
        
    else:
        return render_template("register.html")
        
        
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    
    if request.method == "POST":
        
        #define commonly used variables
        stock = lookup(request.form.get("symbol"))
        stock_number = int(request.form.get("shares"))
    
        #check symbol
        if not stock:
            return apology("Invalid ticker symbol. Please re-enter")
        
        #check number of shares    
        if stock_number < 0:
            return apology("Please enter a positive number of shares")
        
        #select user shares of the stock being bought
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=stock["symbol"])
        
        if not user_shares or int(user_shares[0]["shares"]) < stock_number:
            return apology("You do not have that many shares")
        
        #update the user's portfolio: if all tocks then delete otherwise just decrement
        if user_shares[0]["shares"] - stock_number == 0:
            db.execute("DELTE FROM portfolio WHERE id = :id AND symbol = :symbol", id=session["user_id"], symbol=stock["symbol"])
        else:
            db.execute("UPDATE portfolio SET shares = :shares WHERE id = :id AND symbol = :symbol", shares=int(user_shares[0]["shares"]) - stock_number, id=session["user_id"], symbol=stock["symbol"])
        
        #update the user's cash
        db.execute("UPDATE users SET cash = cash + :profit WHERE id = :id", profit=float(stock_number) * stock["price"], id=session["user_id"])
        
        #update the user's history
        db.execute("INSERT INTO history (id, action, symbol, shares, price) VALUES(:id, :action, :symbol, :shares, :price)", id=session["user_id"], action="sell", symbol=stock["symbol"], shares=stock_number, price=usd(stock["price"]))
        
        #back to homapage
        return redirect(url_for("index"))
        
    else:
        return render_template("sell.html")
        
@app.route("/getmoney", methods=["GET", "POST"])
@login_required
def getmoney():
#allows the user to add money to the account
    
    if request.method == "POST":
        amount = request.form.get("getmoney")
    
        #check to make sure correect responce
        if int(amount) < 0:
            return apology("Please enter a positive integer")
            
        if int(amount) > 50000:
            return apology("I'm not made of money...")
            
        db.execute("UPDATE users SET cash = cash + :procure WHERE id = :id", procure = int(amount), id=session["user_id"])
        
        return redirect(url_for("index"))
        
    else:
        return render_template("getmoney.html")
