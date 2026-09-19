from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Customer, Bicycle, RepairJob, InventoryItem, Sale, Payment, Staff, Supplier, Notification
from datetime import datetime, date
from sqlalchemy import func, desc
import os
import csv
from io import StringIO, BytesIO

def create_app():
    app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
    app.config.from_object('config.Config')
    
    db.init_app(app)
    bcrypt = Bcrypt(app)
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Auth routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            user = User.query.filter_by(email=email).first()
            if user and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('Invalid credentials')
        return render_template('login.html')
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            if User.query.filter_by(email=email).first():
                flash('Email already exists')
                return redirect(url_for('register'))
            user = User(name=name, email=email, password=bcrypt.generate_password_hash(password).decode('utf-8'))
            db.session.add(user)
            db.session.commit()
            flash('Registration successful')
            return redirect(url_for('login'))
        return render_template('register.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))
    
    # Dashboard
    @app.route('/')
    @login_required
    def dashboard():
        today = date.today()
        repairs_today = RepairJob.query.filter(RepairJob.created_at >= today).count()
        pending_repairs = RepairJob.query.filter(RepairJob.status != 'Completed').count()
        low_stock = InventoryItem.query.filter(InventoryItem.quantity < InventoryItem.min_quantity).count()
        customers = Customer.query.count()
        bicycles = Bicycle.query.count()
        recent_repairs = RepairJob.query.order_by(desc(RepairJob.created_at)).limit(5).all()
        sales_today = db.session.query(func.sum(Sale.total)).filter(Sale.created_at >= today).scalar() or 0
        
        return render_template('dashboard.html', 
                             repairs_today=repairs_today,
                             pending_repairs=pending_repairs,
                             low_stock=low_stock,
                             customers=customers,
                             bicycles=bicycles,
                             recent_repairs=recent_repairs,
                             sales_today=sales_today)
    
    # Customers
    @app.route('/customers')
    @login_required
    def customers():
        search = request.args.get('search', '')
        query = Customer.query
        if search:
            query = query.filter(Customer.name.contains(search) | Customer.phone.contains(search))
        customers = query.all()
        return render_template('customers/list.html', customers=customers, search=search)
    
    @app.route('/customers/add', methods=['GET', 'POST'])
    @login_required
    def add_customer():
        if request.method == 'POST':
            customer = Customer(
                name=request.form.get('name'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                notes=request.form.get('notes')
            )
            db.session.add(customer)
            db.session.commit()
            flash('Customer added successfully')
            return redirect(url_for('customers'))
        return render_template('customers/form.html')
    
    @app.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_customer(id):
        customer = Customer.query.get_or_404(id)
        if request.method == 'POST':
            customer.name = request.form.get('name')
            customer.phone = request.form.get('phone')
            customer.email = request.form.get('email')
            customer.address = request.form.get('address')
            customer.notes = request.form.get('notes')
            db.session.commit()
            flash('Customer updated')
            return redirect(url_for('customers'))
        return render_template('customers/form.html', customer=customer)
    
    @app.route('/customers/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_customer(id):
        customer = Customer.query.get_or_404(id)
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted')
        return redirect(url_for('customers'))
    
    # Bicycles
    @app.route('/bicycles')
    @login_required
    def bicycles():
        bicycles = Bicycle.query.all()
        return render_template('bicycles/list.html', bicycles=bicycles)
    
    @app.route('/bicycles/add', methods=['GET', 'POST'])
    @login_required
    def add_bicycle():
        if request.method == 'POST':
            bicycle = Bicycle(
                customer_id=request.form.get('customer_id'),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                serial_number=request.form.get('serial_number'),
                color=request.form.get('color'),
                notes=request.form.get('notes')
            )
            db.session.add(bicycle)
            db.session.commit()
            flash('Bicycle added')
            return redirect(url_for('bicycles'))
        customers = Customer.query.all()
        return render_template('bicycles/form.html', customers=customers)
    
    @app.route('/bicycles/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_bicycle(id):
        bicycle = Bicycle.query.get_or_404(id)
        if request.method == 'POST':
            bicycle.customer_id = request.form.get('customer_id')
            bicycle.brand = request.form.get('brand')
            bicycle.model = request.form.get('model')
            bicycle.serial_number = request.form.get('serial_number')
            bicycle.color = request.form.get('color')
            bicycle.notes = request.form.get('notes')
            db.session.commit()
            flash('Bicycle updated')
            return redirect(url_for('bicycles'))
        customers = Customer.query.all()
        return render_template('bicycles/form.html', bicycle=bicycle, customers=customers)
    
    @app.route('/bicycles/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_bicycle(id):
        bicycle = Bicycle.query.get_or_404(id)
        db.session.delete(bicycle)
        db.session.commit()
        flash('Bicycle deleted')
        return redirect(url_for('bicycles'))
    
    # Repair Jobs
    @app.route('/repairs')
    @login_required
    def repairs():
        status = request.args.get('status', '')
        query = RepairJob.query
        if status:
            query = query.filter_by(status=status)
        repairs = query.order_by(desc(RepairJob.created_at)).all()
        return render_template('repairs/list.html', repairs=repairs, status=status)
    
    @app.route('/repairs/add', methods=['GET', 'POST'])
    @login_required
    def add_repair():
        if request.method == 'POST':
            job = RepairJob(
                customer_id=request.form.get('customer_id'),
                bicycle_id=request.form.get('bicycle_id'),
                description=request.form.get('description'),
                issue=request.form.get('issue'),
                cost=float(request.form.get('cost', 0)),
                status=request.form.get('status', 'Pending'),
                priority=request.form.get('priority', 'Medium'),
                assigned_to=request.form.get('assigned_to'),
                notes=request.form.get('notes')
            )
            db.session.add(job)
            db.session.commit()
            flash('Repair job created')
            return redirect(url_for('repairs'))
        customers = Customer.query.all()
        bicycles = Bicycle.query.all()
        staff = Staff.query.all()
        return render_template('repairs/form.html', customers=customers, bicycles=bicycles, staff=staff)
    
    @app.route('/repairs/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_repair(id):
        job = RepairJob.query.get_or_404(id)
        if request.method == 'POST':
            job.customer_id = request.form.get('customer_id')
            job.bicycle_id = request.form.get('bicycle_id')
            job.description = request.form.get('description')
            job.issue = request.form.get('issue')
            job.cost = float(request.form.get('cost', 0))
            job.status = request.form.get('status', 'Pending')
            job.priority = request.form.get('priority', 'Medium')
            job.assigned_to = request.form.get('assigned_to')
            job.notes = request.form.get('notes')
            if job.status == 'Completed' and not job.completed_at:
                job.completed_at = datetime.utcnow()
            db.session.commit()
            flash('Repair job updated')
            return redirect(url_for('repairs'))
        customers = Customer.query.all()
        bicycles = Bicycle.query.all()
        staff = Staff.query.all()
        return render_template('repairs/form.html', job=job, customers=customers, bicycles=bicycles, staff=staff)
    
    @app.route('/repairs/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_repair(id):
        job = RepairJob.query.get_or_404(id)
        db.session.delete(job)
        db.session.commit()
        flash('Repair job deleted')
        return redirect(url_for('repairs'))
    
    # Inventory
    @app.route('/inventory')
    @login_required
    def inventory():
        search = request.args.get('search', '')
        query = InventoryItem.query
        if search:
            query = query.filter(InventoryItem.name.contains(search) | InventoryItem.category.contains(search))
        items = query.all()
        return render_template('inventory/list.html', items=items, search=search)
    
    @app.route('/inventory/add', methods=['GET', 'POST'])
    @login_required
    def add_inventory():
        if request.method == 'POST':
            item = InventoryItem(
                name=request.form.get('name'),
                category=request.form.get('category'),
                quantity=int(request.form.get('quantity', 0)),
                min_quantity=int(request.form.get('min_quantity', 5)),
                unit_price=float(request.form.get('unit_price', 0)),
                supplier_id=request.form.get('supplier_id'),
                notes=request.form.get('notes')
            )
            db.session.add(item)
            db.session.commit()
            flash('Item added')
            return redirect(url_for('inventory'))
        suppliers = Supplier.query.all()
        return render_template('inventory/form.html', suppliers=suppliers)
    
    @app.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_inventory(id):
        item = InventoryItem.query.get_or_404(id)
        if request.method == 'POST':
            item.name = request.form.get('name')
            item.category = request.form.get('category')
            item.quantity = int(request.form.get('quantity', 0))
            item.min_quantity = int(request.form.get('min_quantity', 5))
            item.unit_price = float(request.form.get('unit_price', 0))
            item.supplier_id = request.form.get('supplier_id')
            item.notes = request.form.get('notes')
            db.session.commit()
            flash('Item updated')
            return redirect(url_for('inventory'))
        suppliers = Supplier.query.all()
        return render_template('inventory/form.html', item=item, suppliers=suppliers)
    
    @app.route('/inventory/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_inventory(id):
        item = InventoryItem.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted')
        return redirect(url_for('inventory'))
    
    # Sales
    @app.route('/sales')
    @login_required
    def sales():
        sales = Sale.query.order_by(desc(Sale.created_at)).all()
        return render_template('sales/list.html', sales=sales)
    
    @app.route('/sales/add', methods=['GET', 'POST'])
    @login_required
    def add_sale():
        if request.method == 'POST':
            sale = Sale(
                customer_id=request.form.get('customer_id'),
                total=float(request.form.get('total', 0)),
                payment_method=request.form.get('payment_method', 'Cash'),
                status=request.form.get('status', 'Pending'),
                notes=request.form.get('notes')
            )
            db.session.add(sale)
            db.session.flush()
            
            # Add payment
            payment = Payment(
                sale_id=sale.id,
                amount=sale.total,
                method=sale.payment_method,
                status='Completed' if sale.status == 'Completed' else 'Pending'
            )
            db.session.add(payment)
            
            # Reduce inventory if applicable
            if sale.status == 'Completed':
                items = request.form.getlist('items[]')
                quantities = request.form.getlist('quantities[]')
                for item_id, qty in zip(items, quantities):
                    if item_id and qty:
                        inv_item = InventoryItem.query.get(int(item_id))
                        if inv_item:
                            inv_item.quantity -= int(qty)
            
            db.session.commit()
            flash('Sale recorded')
            return redirect(url_for('sales'))
        customers = Customer.query.all()
        items = InventoryItem.query.filter(InventoryItem.quantity > 0).all()
        return render_template('sales/form.html', customers=customers, items=items)
    
    @app.route('/sales/<int:id>')
    @login_required
    def view_sale(id):
        sale = Sale.query.get_or_404(id)
        return render_template('sales/view.html', sale=sale)
    
    # Staff
    @app.route('/staff')
    @login_required
    def staff():
        staff = Staff.query.all()
        return render_template('staff/list.html', staff=staff)
    
    @app.route('/staff/add', methods=['GET', 'POST'])
    @login_required
    def add_staff():
        if request.method == 'POST':
            member = Staff(
                name=request.form.get('name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                role=request.form.get('role'),
                salary=float(request.form.get('salary', 0)),
                hire_date=datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else None,
                notes=request.form.get('notes')
            )
            db.session.add(member)
            db.session.commit()
            flash('Staff added')
            return redirect(url_for('staff'))
        return render_template('staff/form.html')
    
    @app.route('/staff/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_staff(id):
        member = Staff.query.get_or_404(id)
        if request.method == 'POST':
            member.name = request.form.get('name')
            member.email = request.form.get('email')
            member.phone = request.form.get('phone')
            member.role = request.form.get('role')
            member.salary = float(request.form.get('salary', 0))
            member.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else None
            member.notes = request.form.get('notes')
            db.session.commit()
            flash('Staff updated')
            return redirect(url_for('staff'))
        return render_template('staff/form.html', staff=member)
    
    @app.route('/staff/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_staff(id):
        member = Staff.query.get_or_404(id)
        db.session.delete(member)
        db.session.commit()
        flash('Staff deleted')
        return redirect(url_for('staff'))
    
    # Suppliers
    @app.route('/suppliers')
    @login_required
    def suppliers():
        suppliers = Supplier.query.all()
        return render_template('suppliers/list.html', suppliers=suppliers)
    
    @app.route('/suppliers/add', methods=['GET', 'POST'])
    @login_required
    def add_supplier():
        if request.method == 'POST':
            supplier = Supplier(
                name=request.form.get('name'),
                contact_person=request.form.get('contact_person'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                address=request.form.get('address'),
                notes=request.form.get('notes')
            )
            db.session.add(supplier)
            db.session.commit()
            flash('Supplier added')
            return redirect(url_for('suppliers'))
        return render_template('suppliers/form.html')
    
    @app.route('/suppliers/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_supplier(id):
        supplier = Supplier.query.get_or_404(id)
        if request.method == 'POST':
            supplier.name = request.form.get('name')
            supplier.contact_person = request.form.get('contact_person')
            supplier.email = request.form.get('email')
            supplier.phone = request.form.get('phone')
            supplier.address = request.form.get('address')
            supplier.notes = request.form.get('notes')
            db.session.commit()
            flash('Supplier updated')
            return redirect(url_for('suppliers'))
        return render_template('suppliers/form.html', supplier=supplier)
    
    @app.route('/suppliers/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_supplier(id):
        supplier = Supplier.query.get_or_404(id)
        db.session.delete(supplier)
        db.session.commit()
        flash('Supplier deleted')
        return redirect(url_for('suppliers'))
    
    # Reports
    @app.route('/reports')
    @login_required
    def reports():
        period = request.args.get('period', 'month')
        today = date.today()
        if period == 'day':
            start_date = today
        elif period == 'week':
            start_date = today - timedelta(days=7)
        else:
            start_date = today - timedelta(days=30)
        
        sales_data = db.session.query(func.sum(Sale.total)).filter(Sale.created_at >= start_date).scalar() or 0
        repairs_data = RepairJob.query.filter(RepairJob.created_at >= start_date).count()
        customers_data = Customer.query.filter(Customer.created_at >= start_date).count()
        
        return render_template('reports/index.html', 
                             sales_data=sales_data,
                             repairs_data=repairs_data,
                             customers_data=customers_data,
                             period=period)
    
    @app.route('/reports/export/csv')
    @login_required
    def export_sales_csv():
        sales = Sale.query.all()
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'Customer', 'Total', 'Payment Method', 'Status', 'Date'])
        for sale in sales:
            writer.writerow([sale.id, sale.customer.name if sale.customer else 'N/A', sale.total, sale.payment_method, sale.status, sale.created_at])
        output = BytesIO()
        output.write(si.getvalue().encode())
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f'sales_{today()}.csv')
    
    # Notifications
    @app.route('/notifications')
    @login_required
    def notifications():
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(desc(Notification.created_at)).all()
        return render_template('notifications/list.html', notifications=notifications)
    
    @app.route('/api/notifications/unread')
    @login_required
    def unread_notifications():
        count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        return jsonify({'count': count})
    
    from datetime import timedelta
    
    return app
