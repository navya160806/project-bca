


from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import jsonify

import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# ================================
# MODELS
# ================================
from datetime import datetime, timedelta

class FeeRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100))
    student_class = db.Column(db.String(20))
    roll_no = db.Column(db.String(20))
    fee_category = db.Column(db.String(50))  # Semester, Hostel, etc.
    fee_amount = db.Column(db.Float)
    fee_status = db.Column(db.String(10))    # Paid / Unpaid
    fee_date = db.Column(db.Date, default=datetime.utcnow)
    email = db.Column(db.String(100))
    last_reminder_sent = db.Column(db.DateTime, nullable=True)  # <-- NEW

# ================================
# ROUTES
# ================================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '1234':
            session['user'] = 'admin'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    total_collected = db.session.query(db.func.sum(FeeRecord.fee_amount)).filter(FeeRecord.fee_status == 'Paid').scalar() or 0
    total_students_paid = db.session.query(FeeRecord.roll_no).filter(FeeRecord.fee_status == 'Paid').distinct().count()
    pending_fees = db.session.query(FeeRecord.fee_amount).filter(FeeRecord.fee_status != 'Paid').all()
    pending_amount = sum(f[0] for f in pending_fees) if pending_fees else 0
    defaulters = db.session.query(FeeRecord.roll_no).filter(FeeRecord.fee_status != 'Paid').distinct().count()

    # Chart 1: Payment status distribution
    payment_distribution = db.session.query(FeeRecord.fee_status, db.func.count(FeeRecord.id)).group_by(FeeRecord.fee_status).all()
    chart_labels = [row[0] for row in payment_distribution]
    chart_values = [row[1] for row in payment_distribution]

    # Chart 2: Category-wise collection
    category_data = db.session.query(FeeRecord.fee_category, db.func.sum(FeeRecord.fee_amount))\
        .filter(FeeRecord.fee_status == 'Paid').group_by(FeeRecord.fee_category).all()
    cat_labels = [row[0] for row in category_data]
    cat_values = [row[1] for row in category_data]

    return render_template(
        'dashboard.html',
        total_collected=total_collected,
        total_students_paid=total_students_paid,
        pending_amount=pending_amount,
        defaulters=defaulters,
        chart_labels=chart_labels,
        chart_values=chart_values,
        cat_labels=cat_labels,
        cat_values=cat_values
    )


@app.route('/fee', methods=['GET', 'POST'])
def fee():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_class = request.form['student_class']
        roll_no = request.form['roll_no']
        email = request.form['email']
        fee_status = request.form['fee_status']

        categories = request.form.getlist('categories')  # List of checked categories

        for category in categories:
            try:
                amount = float(request.form.get(category))
                if amount > 0:
                    record = FeeRecord(
                        student_name=student_name,
                        student_class=student_class,
                        roll_no=roll_no,
                        fee_category=category,
                        fee_amount=amount,
                        fee_status=fee_status,
                        email=email
                    )
                    db.session.add(record)
            except (ValueError, TypeError):
                continue  # Skip if invalid amount

        db.session.commit()
        flash("All selected fee records saved successfully!", "success")
        return redirect(url_for('fee'))

    return render_template('fee.html')


@app.route('/fee_view')
def fee_view():
    name = request.args.get('name', '').lower()
    min_amount = request.args.get('min', type=float)
    max_amount = request.args.get('max', type=float)
    status = request.args.get('status')

    query = db.session.query(FeeRecord).order_by(FeeRecord.fee_date.desc())

    # Apply filters
    if name:
        query = query.filter(FeeRecord.student_name.ilike(f'%{name}%'))
    if min_amount is not None:
        query = query.filter(FeeRecord.fee_amount >= min_amount)
    if max_amount is not None:
        query = query.filter(FeeRecord.fee_amount <= max_amount)
    if status:
        query = query.filter(FeeRecord.fee_status == status)

    all_records = query.all()

    # Group by roll_no
    grouped_data = {}
    for rec in all_records:
        key = rec.roll_no
        if key not in grouped_data:
            grouped_data[key] = {
                'student_name': rec.student_name,
                'student_class': rec.student_class,
                'roll_no': rec.roll_no,
                'email': rec.email,
                'fee_types': [],
                'total_amount': 0,
                'status': set(),
                'ids': []
            }
        grouped_data[key]['fee_types'].append(f"{rec.fee_category} (₹{rec.fee_amount})")
        grouped_data[key]['total_amount'] += rec.fee_amount
        grouped_data[key]['status'].add(rec.fee_status)
        grouped_data[key]['ids'].append(rec.id)

    return render_template('fee_view.html', records=list(grouped_data.values()))




@app.route('/edit/<roll_no>', methods=['GET', 'POST'])
def edit_student(roll_no):
    records = FeeRecord.query.filter_by(roll_no=roll_no).all()
    if not records:
        flash("No records found for this student", "error")
        return redirect(url_for('fee_view'))

    if request.method == 'POST':
        for record in records:
            record.student_name = request.form['student_name']
            record.student_class = request.form['student_class']
            record.email = request.form['email']

            fee_amount = request.form.get(f'fee_amount_{record.id}')
            fee_status = request.form.get(f'fee_status_{record.id}')
            fee_category = request.form.get(f'fee_category_{record.id}')

            if fee_amount:
                record.fee_amount = float(fee_amount)
            if fee_status:
                record.fee_status = fee_status
            if fee_category:
                record.fee_category = fee_category

        db.session.commit()
        flash("Student fee records updated successfully!", "success")
        return redirect(url_for('fee_view'))

    student = {
        'student_name': records[0].student_name,
        'student_class': records[0].student_class,
        'roll_no': records[0].roll_no,
        'email': records[0].email
    }
    return render_template('edit_student.html', student=student, records=records)




@app.route('/delete_student/<roll_no>', methods=['POST'])
def delete_student(roll_no):
    FeeRecord.query.filter_by(roll_no=roll_no).delete()
    db.session.commit()
    flash("All records for the student deleted.", "success")
    return redirect(url_for('fee_view'))







@app.route('/noti')
def noti():
    from datetime import datetime, timedelta
    one_week_ago = datetime.utcnow() - timedelta(days=7)

    unpaid_records = db.session.query(FeeRecord).filter(
        FeeRecord.fee_status != 'Paid',
        (FeeRecord.last_reminder_sent == None) | (FeeRecord.last_reminder_sent < one_week_ago)
    ).all()

    defaulters = {}
    for rec in unpaid_records:
        key = rec.roll_no
        if key not in defaulters:
            defaulters[key] = {
                'student_name': rec.student_name,
                'email': rec.email,
                'roll_no': rec.roll_no,
                'categories': []
            }
        defaulters[key]['categories'].append(rec.fee_category)

    return render_template('noti.html', defaulters=list(defaulters.values()))


@app.route('/send_reminder', methods=['POST'])
def send_reminder():
    roll_no = request.form.get('roll_no')
    if not roll_no:
        return jsonify({'success': False, 'error': 'No roll_no received'}), 400

    now = datetime.utcnow()

    # Find unpaid records
    records = FeeRecord.query.filter_by(roll_no=roll_no, fee_status='Unpaid').all()
    if not records:
        return jsonify({'success': False, 'error': 'No unpaid records found'}), 404

    for record in records:
        record.last_reminder_sent = now

    db.session.commit()
    return jsonify({'success': True})



@app.route('/receipt/roll/<roll_no>')
def receipt_by_roll(roll_no):
    records = FeeRecord.query.filter_by(roll_no=roll_no, fee_status='Paid').all()
    if not records:
        return "No paid records found for this student.", 404

    total_amount = sum(rec.fee_amount for rec in records)

    student = {
        'student_name': records[0].student_name,
        'student_class': records[0].student_class,
        'roll_no': records[0].roll_no,
        'email': records[0].email
    }

    return render_template('receipt.html', records=records, total_amount=total_amount, student=student)









# ================================
# INIT DB IF NEEDED
# ================================
with app.app_context():
    db.create_all()

# ================================
# RUN APP
# ================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
