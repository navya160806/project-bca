from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# =====================
# MODEL
# =====================
class FeeRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100))
    student_class = db.Column(db.String(20))
    roll_no = db.Column(db.String(20))
    fee_category = db.Column(db.String(50))
    fee_amount = db.Column(db.Float)
    fee_status = db.Column(db.String(10))
    fee_date = db.Column(db.Date, default=datetime.utcnow)
    email = db.Column(db.String(100))
    last_reminder_sent = db.Column(db.DateTime, nullable=True)

# =====================
# LOGIN
# =====================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '1234':
            session['user'] = 'admin'
            return redirect(url_for('dashboard'))
        flash("Invalid credentials", "error")
    return render_template('login.html')

# =====================
# DASHBOARD
# =====================
@app.route('/dashboard')
def dashboard():
    total_collected = db.session.query(db.func.sum(FeeRecord.fee_amount))\
        .filter(FeeRecord.fee_status == 'Paid').scalar() or 0

    pending_amount = db.session.query(db.func.sum(FeeRecord.fee_amount))\
        .filter(FeeRecord.fee_status != 'Paid').scalar() or 0

    defaulters = db.session.query(FeeRecord.roll_no)\
        .filter(FeeRecord.fee_status != 'Paid').distinct().count()

    return render_template(
        'dashboard.html',
        total_collected=total_collected,
        pending_amount=pending_amount,
        defaulters=defaulters
    )

# =====================
# FEE ENTRY
# =====================
@app.route('/fee', methods=['GET', 'POST'])
def fee():
    if request.method == 'POST':
        categories = request.form.getlist('categories')

        for cat in categories:
            amount = float(request.form.get(cat))
            record = FeeRecord(
                student_name=request.form['student_name'],
                student_class=request.form['student_class'],
                roll_no=request.form['roll_no'],
                email=request.form['email'],
                fee_category=cat,
                fee_amount=amount,
                fee_status=request.form['fee_status']
            )
            db.session.add(record)

        db.session.commit()
        flash("Fee saved successfully", "success")
        return redirect(url_for('fee'))

    return render_template('fee.html')

# =====================
# FEE VIEW
# =====================
@app.route('/fee_view')
def fee_view():
    records = FeeRecord.query.order_by(FeeRecord.roll_no).all()
    return render_template('fee_view.html', records=records)

# =====================
# NOTIFICATION
# =====================
@app.route('/noti')
def noti():
    one_week_ago = datetime.utcnow() - timedelta(days=7)

    unpaid = FeeRecord.query.filter(
        FeeRecord.fee_status != 'Paid',
        (FeeRecord.last_reminder_sent == None) |
        (FeeRecord.last_reminder_sent < one_week_ago)
    ).all()

    return render_template('noti.html', records=unpaid)

@app.route('/send_reminder', methods=['POST'])
def send_reminder():
    roll_no = request.form['roll_no']
    records = FeeRecord.query.filter_by(roll_no=roll_no, fee_status='Unpaid').all()

    for r in records:
        r.last_reminder_sent = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True})

# =====================
# RECEIPT
# =====================
@app.route('/receipt/roll/<roll_no>')
def receipt(roll_no):
    records = FeeRecord.query.filter_by(roll_no=roll_no, fee_status='Paid').all()
    total = sum(r.fee_amount for r in records)
    return render_template('receipt.html', records=records, total=total)

# =====================
# INIT DB
# =====================
with app.app_context():
    db.create_all()

# =====================
# RUN
# =====================
if __name__ == '__main__':
    app.run(debug=True)
