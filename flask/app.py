from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# ============================================
# MODELS
# ============================================
class FeeRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100))
    student_class = db.Column(db.String(20))
    roll_no = db.Column(db.String(20))
    fee_category = db.Column(db.String(50))
    fee_amount = db.Column(db.Float)
    fee_status = db.Column(db.String(10))
    email = db.Column(db.String(100))
    fee_date = db.Column(db.Date, default=datetime.utcnow)
    last_reminder_sent = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    payment_date = db.Column(db.Date, nullable=True)
    late_fee = db.Column(db.Float, default=0.0)

# ============================================
# LOGIN ROUTE
# ============================================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '1234':
            session['user'] = 'admin'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

# ============================================
# DASHBOARD
# ============================================
@app.route('/dashboard')
def dashboard():
    total_collected = db.session.query(db.func.sum(FeeRecord.fee_amount)).filter(FeeRecord.fee_status == 'Paid').scalar() or 0
    total_students_paid = db.session.query(FeeRecord.roll_no).filter(FeeRecord.fee_status == 'Paid').distinct().count()
    pending_fees = db.session.query(FeeRecord.fee_amount).filter(FeeRecord.fee_status != 'Paid').all()
    pending_amount = sum(f[0] for f in pending_fees) if pending_fees else 0
    defaulters = db.session.query(FeeRecord.roll_no).filter(FeeRecord.fee_status != 'Paid').distinct().count()

    payment_distribution = db.session.query(FeeRecord.fee_status, db.func.count(FeeRecord.id)).group_by(FeeRecord.fee_status).all()
    chart_labels = [row[0] for row in payment_distribution]
    chart_values = [row[1] for row in payment_distribution]

    category_data = db.session.query(FeeRecord.fee_category, db.func.sum(FeeRecord.fee_amount))\
        .filter(FeeRecord.fee_status == 'Paid').group_by(FeeRecord.fee_category).all()
    cat_labels = [row[0] for row in category_data]
    cat_values = [row[1] for row in category_data]

    return render_template('dashboard.html',
        total_collected=total_collected,
        total_students_paid=total_students_paid,
        pending_amount=pending_amount,
        defaulters=defaulters,
        chart_labels=chart_labels,
        chart_values=chart_values,
        cat_labels=cat_labels,
        cat_values=cat_values
    )

# ============================================
# FEE COLLECTION ROUTE (WITH LATE FEE LOGIC)
# ============================================
@app.route('/fee', methods=['GET', 'POST'])
def fee():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_class = request.form['student_class']
        roll_no = request.form['roll_no']
        email = request.form['email']
        fee_status = request.form['fee_status']
        due_date_str = request.form.get('due_date')
        payment_date_str = request.form.get('payment_date')

        # Parse dates
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else None

        categories = request.form.getlist('categories')

        for category in categories:
            try:
                base_amount = float(request.form.get(category))
                if base_amount > 0:
                    late_fee = 0
                    if payment_date and due_date and payment_date > due_date:
                        days_late = (payment_date - due_date).days
                        late_fee = days_late * 500
                        base_amount += late_fee

                    record = FeeRecord(
                        student_name=student_name,
                        student_class=student_class,
                        roll_no=roll_no,
                        fee_category=category,
                        fee_amount=base_amount,
                        fee_status=fee_status,
                        email=email,
                        due_date=due_date,
                        payment_date=payment_date,
                        late_fee=late_fee
                    )
                    db.session.add(record)
            except (ValueError, TypeError):
                continue

        db.session.commit()
        flash("Fee record saved successfully with any applicable late fee!", "success")
        return redirect(url_for('fee'))

    return render_template('fee.html')

# ============================================
# FEE VIEW ROUTE
# ============================================
@app.route('/fee_view')
def fee_view():
    name = request.args.get('name', '').lower()
    min_amount = request.args.get('min', type=float)
    max_amount = request.args.get('max', type=float)
    status = request.args.get('status')

    query = db.session.query(FeeRecord).order_by(FeeRecord.fee_date.desc())

    if name:
        query = query.filter(FeeRecord.student_name.ilike(f'%{name}%'))
    if min_amount is not None:
        query = query.filter(FeeRecord.fee_amount >= min_amount)
    if max_amount is not None:
        query = query.filter(FeeRecord.fee_amount <= max_amount)
    if status:
        query = query.filter(FeeRecord.fee_status == status)

    all_records = query.all()

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

# ============================================
# EDIT & DELETE
# ============================================
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

# ============================================
# INITIALIZE DATABASE
# ============================================
with app.app_context():
    db.create_all()

# ============================================
# RUN SERVER
# ============================================
if __name__ == '__main__':
    app.run(debug=True)
