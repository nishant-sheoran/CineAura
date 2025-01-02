from flask import Flask, render_template, request, url_for, flash, redirect, session, jsonify
import sqlite3
import random
import datetime
import string
import json

app = Flask(__name__)
app.secret_key = 'this_is_my_secret_key'

# Database setup
def init_db():
    with sqlite3.connect('booking.db') as conn:
        cursor = conn.cursor()
        # Create bookings table
        cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            theater TEXT,
                            movie TEXT,
                            screen TEXT,
                            food_items TEXT,
                            total_price REAL,
                            booking_time DATETIME,
                            seat_number INTEGER,
                            booking_id TEXT,
                            canceled INTEGER DEFAULT 0
                          )''')
        # Create waiting list table
        cursor.execute('''CREATE TABLE IF NOT EXISTS waiting_list (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            theater TEXT,
                            movie TEXT,
                            screen TEXT,
                            user_data TEXT,
                            join_time DATETIME
                          )''')
        # Create seat availability table
        cursor.execute('''CREATE TABLE IF NOT EXISTS seats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            theater TEXT,
                            screen TEXT,
                            total_seats INTEGER,
                            booked_seats INTEGER
                          )''')
        # Initialize seat data if not already present
        cursor.execute('SELECT COUNT(*) FROM seats')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''INSERT INTO seats (theater, screen, total_seats, booked_seats) VALUES (?, ?, ?, ?)''', [
                ('pvr-mumbai', 'gold', 2, 0),
                ('pvr-mumbai', 'max', 5, 0),
                ('pvr-mumbai', 'general', 10, 0),
                ('inox-delhi', 'gold', 2, 0),
                ('inox-delhi', 'max', 5, 0),
                ('inox-delhi', 'general', 10, 0),
                ('cinepolis-bangalore', 'gold', 2, 0),
                ('cinepolis-bangalore', 'max', 5, 0),
                ('cinepolis-bangalore', 'general', 10, 0)
            ])
        conn.commit()

init_db()

# Basic route
@app.route("/", methods=["GET"])
def home():
    with sqlite3.connect('booking.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE canceled = 0')
        rows = cursor.fetchall()
        bookings = [
            {
                "id": row[0],
                "theater": row[1],
                "movie": row[2],
                "screen": row[3],
                "food_items": row[4],
                "total_price": row[5],
                "booking_time": row[6],
                "seat_number": row[7],
                "booking_id": row[8]
            }
            for row in rows
        ]
    return render_template('index.html', bookings=bookings)

# Booking tickets
@app.route("/book_tickets", methods=['GET', 'POST'])
def book_tickets():
    with open('theater_data.json', 'r') as f:
        data = json.load(f)
    
    theaters = data["theaters"]
    movies = data["movies"]
    screens = data["screens"]
    
    if request.method == "POST":
        theater = request.form.get("theater")
        movie = request.form.get("movie")
        screen = request.form.get("screen")

        session['theater'] = theater
        session['movie'] = movie
        session['screen'] = screen

        # Check seat availability
        with sqlite3.connect('booking.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_seats, booked_seats FROM seats WHERE theater = ? AND screen = ?', (theater, screen))
            seat_data = cursor.fetchone()
            if not seat_data or seat_data[1] >= seat_data[0]:
                flash('No seats available. You can join the waiting list.')
                return redirect(url_for('join_waiting_list'))

        return redirect(url_for("select_beverages"))

    return render_template("bookTickets.html", theaters=theaters, movies=movies, screens=screens)


# Select beverages
@app.route("/select_beverages", methods=['GET', 'POST'])
def select_beverages():
    if request.method == 'POST':
        food_items = request.form.getlist('foodandbeverages')
        session['food_items'] = ','.join(food_items)  # Store as comma-separated string
        return redirect(url_for("confirm_booking"))

    return render_template("selectBeverages.html")

# Confirm booking
@app.route("/confirm_booking", methods=['GET', 'POST'])
def confirm_booking():
    theater = session.get('theater', 'Not Selected')
    movie = session.get('movie', 'Not Selected')
    screen = session.get('screen', 'Not Selected')
    food_items = session.get('food_items', '').split(',')

    if request.method == 'POST':
        return redirect(url_for("payment"))

    return render_template('confirmBooking.html',
                           theater=theater,
                           movie=movie,
                           screen=screen,
                           food_items=food_items)

# Join waiting list
@app.route("/join_waiting_list", methods=['GET', 'POST'])
def join_waiting_list():
    if request.method == 'POST':
        user_data = request.form.get('user_data')  # Placeholder for user details
        with sqlite3.connect('booking.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO waiting_list (theater, movie, screen, user_data, join_time)
                              VALUES (?, ?, ?, ?, ?)''',
                           (session['theater'], session['movie'], session['screen'], user_data, datetime.datetime.now()))
            conn.commit()
        flash('You have been added to the waiting list.')
        return redirect(url_for('home'))

    return render_template('waitingList.html')

# Payment
@app.route("/payment", methods=['GET', 'POST'])
def payment():
    theater = session.get('theater', 'Not Selected')
    movie = session.get('movie', 'Not Selected')
    screen = session.get('screen', 'Not Selected')
    food_items = session.get('food_items', '').split(',')

    total_amount = 0
    discount = 0
    final_price = 0

    if screen == 'gold':
        if 'Popcorn' in food_items:
            total_amount += 250
        if 'Sandwich' in food_items:
            total_amount += 100
        discount = 0.1 * total_amount
        total_amount -= discount
        final_price = total_amount + 400

    elif screen == 'max':
        if 'Popcorn' in food_items:
            total_amount += 250
        if 'Sandwich' in food_items:
            total_amount += 100
        discount = 0.05 * total_amount
        total_amount -= discount
        final_price = total_amount + 300

    elif screen == 'general':
        if 'Popcorn' in food_items:
            total_amount += 450
        if 'Sandwich' in food_items:
            total_amount += 300
        final_price = total_amount

    else:
        return jsonify({"error": "Invalid screen type selected."}), 400

    if request.method == 'POST':
        # Allocate a seat and save booking to database
        booking_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        with sqlite3.connect('booking.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT booked_seats FROM seats WHERE theater = ? AND screen = ?', (theater, screen))
            booked_seats = cursor.fetchone()[0]
            seat_number = booked_seats + 1

            cursor.execute('''UPDATE seats SET booked_seats = booked_seats + 1 WHERE theater = ? AND screen = ?''',
                           (theater, screen))

            cursor.execute('''INSERT INTO bookings (theater, movie, screen, food_items, total_price, booking_time, seat_number, booking_id)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                           (theater, movie, screen, session['food_items'], final_price, datetime.datetime.now(), seat_number, booking_id))
            conn.commit()

        return redirect(url_for('finalBookTickets', booking_id=booking_id))

    return render_template('payment.html', final_price=final_price)

# Cancel booking
@app.route("/cancel_booking/<booking_id>", methods=['POST'])
def cancel_booking(booking_id):
    with sqlite3.connect('booking.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT booking_time, screen, theater FROM bookings WHERE booking_id = ? AND canceled = 0', (booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash('Booking not found or already canceled.')
            return redirect(url_for('home'))

        booking_time = datetime.datetime.strptime(booking[0], '%Y-%m-%d %H:%M:%S')
        screen = booking[1]
        theater = booking[2]

        if (datetime.datetime.now() - booking_time).total_seconds() > 30 * 60:
            flash('Cannot cancel booking less than 30 minutes before the movie.')
            return redirect(url_for('home'))

        cursor.execute('UPDATE bookings SET canceled = 1 WHERE booking_id = ?', (booking_id,))
        cursor.execute('UPDATE seats SET booked_seats = booked_seats - 1 WHERE theater = ? AND screen = ?', (theater, screen))
        conn.commit()

    flash('Booking canceled successfully.')
    return redirect(url_for('home'))

# Book Tickets - FINAL
@app.route('/finalBookTickets', methods=['GET', 'POST'])
def finalBookTickets():
    booking_id = request.args.get('booking_id')
    return render_template('finalBookTickets.html', booking_id=booking_id)

# API route to fetch bookings
@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    with sqlite3.connect('booking.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE canceled = 0')
        rows = cursor.fetchall()
        bookings = [
            {
                "id": row[0],
                "theater": row[1],
                "movie": row[2],
                "screen": row[3],
                "food_items": row[4],
                "total_price": row[5],
                "booking_time": row[6],
                "seat_number": row[7],
                "booking_id": row[8]
            }
            for row in rows
        ]
    return jsonify(bookings)

if __name__ == "__main__":
    app.run(debug=True)