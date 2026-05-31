from pathlib import Path
import psycopg2
import psycopg2.extras
import random
from datetime import datetime, timedelta
import time

BASE_DIR = Path(__file__).resolve().parent.parent
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'benchmark',
    'user': 'postgres'
}

REGIONS = ['East', 'West', 'North', 'South', 'Central']
STATUSES = ['pending', 'paid', 'completed', 'cancelled', 'refunded']
CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Food', 'Books', 'Sports', 'Toys', 'Home']
LOG_LEVELS = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
ACTIONS = ['login', 'logout', 'purchase', 'update', 'delete', 'create', 'view', 'search']

FIRST_NAMES = ['James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda', 'David', 'Elizabeth', 'William', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica', 'Thomas', 'Sarah', 'Charles', 'Karen']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']

random.seed(42)

def get_conn():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(**DB_CONFIG)

def random_name():
    """Generate random English name"""
    return random.choice(FIRST_NAMES) + random.choice(LAST_NAMES)

def random_phone():
    """Generate random phone number"""
    prefixes = ['138', '139', '135', '136', '137', '150', '151', '152', '153', '155', '156', '157', '158', '159', '170', '176', '177', '178', '180', '181', '182', '183', '184', '185', '186', '187', '188', '189']
    return random.choice(prefixes) + ''.join([str(random.randint(0, 9)) for _ in range(8)])

def random_email(name):
    """Generate random email"""
    domains = ['gmail.com', '163.com', 'qq.com', '126.com', 'outlook.com', 'company.com']
    return f"{name.lower()}{random.randint(1, 999)}@{random.choice(domains)}"

def random_date(start_year=2020, end_year=2024):
    """Generate random date within given range (YYYY-MM-DD)"""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime('%Y-%m-%d')

def random_datetime(start_year=2023, end_year=2024):
    """Generate random timestamp within given range"""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31, 23, 59, 59)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return (start + timedelta(seconds=random_seconds)).strftime('%Y-%m-%d %H:%M:%S')


def skewed_status():
    """Skewed distribution: order status (90% completed, 5% paid, 4.2% refunded, rest cancelled/pending)"""
    r = random.random()
    if r < 0.90:   return 'completed'
    elif r < 0.95: return 'paid'
    elif r < 0.992: return 'refunded'
    elif r < 0.997: return 'cancelled'
    else:          return 'pending'


def skewed_vip():
    """Skewed distribution: VIP level (90% normal, 8% level 1, 1.8% level 2, 0.2% level 3)"""
    r = random.random()
    if r < 0.90: return 0
    elif r < 0.98: return 1
    elif r < 0.998: return 2
    else: return 3


def skewed_amount():
    """Skewed distribution: order amount (70% small 10-500, 20% medium 500-2000, 8% large 2000-5000, 2% very large 5000-50000)"""
    r = random.random()
    if r < 0.7:
        return round(random.uniform(10, 500), 2)
    elif r < 0.9:
        return round(random.uniform(500, 2000), 2)
    elif r < 0.98:
        return round(random.uniform(2000, 5000), 2)
    else:
        return round(random.uniform(5000, 50000), 2)


def skewed_quantity():
    """Skewed distribution: order item quantity (50% 1, 20% 2, 15% 3)"""
    r = random.random()
    if r < 0.5: return 1
    elif r < 0.7: return 2
    elif r < 0.85: return 3
    elif r < 0.95: return random.randint(4, 6)
    else: return random.randint(7, 20)


def skewed_region():
    """Skewed distribution: region (50% East, rest uniform)"""
    if random.random() < 0.5:
        return 'East'
    else:
        return random.choice(['West', 'North', 'South', 'Central'])


def get_schema_sql():
    """Return table creation SQL (9 tables + 15 indexes) with DROP prefix"""
    return '''
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS logs CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS banned_customers CASCADE;

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    budget REAL,
    location TEXT
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    region TEXT,
    vip_level INTEGER DEFAULT 0,
    created_at DATE,
    total_amount REAL DEFAULT 0
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    amount REAL,
    status TEXT,
    order_date DATE,
    shipping_address TEXT,
    payment_method TEXT
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    price REAL,
    stock INTEGER DEFAULT 0,
    supplier_id INTEGER,
    created_at DATE
);

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    dept_id INTEGER REFERENCES departments(id),
    salary REAL,
    hire_date DATE,
    email TEXT,
    manager_id INTEGER
);

CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    action TEXT,
    timestamp TIMESTAMP,
    level TEXT,
    details TEXT
);

CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    contact TEXT,
    phone TEXT,
    region TEXT,
    rating REAL
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER,
    unit_price REAL
);

CREATE TABLE banned_customers (
    customer_id INTEGER PRIMARY KEY REFERENCES customers(id),
    reason TEXT,
    banned_at DATE
);

CREATE INDEX idx_customers_region ON customers(region);
CREATE INDEX idx_customers_vip_level ON customers(vip_level);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_region_vip ON customers(region, vip_level);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_status_amount ON orders(status, amount);

CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_supplier_id ON products(supplier_id);

CREATE INDEX idx_employees_dept_id ON employees(dept_id);
CREATE INDEX idx_employees_salary ON employees(salary);

CREATE INDEX idx_logs_user_id ON logs(user_id);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);
CREATE INDEX idx_logs_level ON logs(level);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
'''


def generate_data():
    """Generate 1x benchmark data (~1.48M rows)

    Data volume: departments 50, suppliers 500, customers 50000,
            products 20000, employees 10000, orders 200000,
            order_items ~1200000, logs 100000, banned_customers 2500
    """
    print("Generating test data...")
    
    print("  Generating department data (50)...")
    departments = []
    for i in range(1, 51):
        departments.append((
            f"Dept{random.choice(['R&D', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations', 'Support', 'Logistics'])}-{i}",
            random.randint(100000, 5000000),
            random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia'])
        ))
    
    print("  Generating supplier data (500)...")
    suppliers = []
    for i in range(1, 501):
        suppliers.append((
            f"Supplier{i}-{random.choice(['Tech', 'Industrial', 'Trading', 'Group'])}",
            random_name(),
            random_phone(),
            random.choice(REGIONS),
            round(random.uniform(3.0, 5.0), 1)
        ))
    
    print("  Generating customer data (50000)...")
    customers = []
    for i in range(1, 50001):
        name = random_name()
        customers.append((
            name,
            random_email(name),
            random_phone(),
            skewed_region(),
            skewed_vip(),
            random_date(2020, 2024),
            round(random.uniform(0, 50000), 2)
        ))
    
    print("  Generating product data (20000)...")
    products = []
    for i in range(1, 20001):
        products.append((
            f"Product{i}-{random.choice(['ModelA', 'ModelB', 'ModelC', 'Standard', 'Pro', 'Flagship'])}",
            random.choice(CATEGORIES),
            round(random.uniform(9.9, 9999.9), 2),
            random.randint(0, 1000),
            random.randint(1, 500),
            random_date(2022, 2024)
        ))
    
    print("  Generating employee data (10000)...")
    employees = []
    for i in range(1, 10001):
        name = random_name()
        manager_id = random.randint(1, 10000) if random.random() > 0.3 else None
        employees.append((
            name,
            random.randint(1, 50),
            round(random.uniform(5000, 50000), 2),
            random_date(2015, 2024),
            f"emp{i}@company.com",
            manager_id
        ))
    
    print("  Generating order data (200000)...")
    orders = []
    for order_id in range(1, 200001):
        customer_id = random.randint(1, 50000)
        orders.append((
            customer_id,
            skewed_amount(),
            skewed_status(),
            random_date(2023, 2024),
            f"Address-{random.randint(1, 9999)}-{random.choice(['Street', 'Road', 'Lane'])}",
            random.choice(['Alipay', 'WeChat', 'CreditCard', 'BankTransfer'])
        ))
    
    print("  Generating order item data (~1200000, 3~8 items per order)...")
    order_items = []
    for order_id in range(1, 200001):
        num_items = random.randint(3, 8)
        for _ in range(num_items):
            product_id = random.randint(1, 20000)
            quantity = skewed_quantity()
            unit_price = random.uniform(10, 1000)
            order_items.append((
                order_id,
                product_id,
                quantity,
                round(unit_price, 2)
            ))
    
    print("  Generating log data (100000)...")
    logs = []
    for i in range(1, 100001):
        logs.append((
            random.randint(1, 50000),
            random.choice(ACTIONS),
            random_datetime(2023, 2024),
            random.choice(LOG_LEVELS),
            f"Detail-{i}-{random.choice(['Success', 'Failed', 'Warning'])}"
        ))
    
    print("  Generating banned customer data (2500)...")
    banned_ids = random.sample(range(1, 50001), min(2500, 50000))
    banned_customers = [(cid, random.choice(['Fraud', 'Violation', 'Debt', 'FakeTransaction', 'ExcessiveComplaints']), random_date(2023, 2024)) for cid in banned_ids]
    
    print("Data generation complete!")
    return {
        'departments': departments,
        'suppliers': suppliers,
        'customers': customers,
        'products': products,
        'employees': employees,
        'orders': orders,
        'order_items': order_items,
        'logs': logs,
        'banned_customers': banned_customers
    }


def init_benchmark_db():
    """Initialize PostgreSQL benchmark database

    Skip if departments table already has data, otherwise create tables and indexes and insert 1x data.
    Total data volume is approximately 1.48 million rows. Returns total row count after ANALYZE.
    """
    import os
    conn = get_conn()
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM departments")
        dept_count = cur.fetchone()[0]

    if dept_count > 0:
        print("Database already exists, skipping data generation.")
        conn.close()
        return

    print("Creating database tables and indexes...")
    with conn.cursor() as cur:
        cur.execute(get_schema_sql())

    data = generate_data()
    
    print("Inserting department data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO departments (name, budget, location) VALUES (%s, %s, %s)",
            data['departments']
        )
    
    print("Inserting supplier data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO suppliers (name, contact, phone, region, rating) VALUES (%s, %s, %s, %s, %s)",
            data['suppliers']
        )
    
    print("Inserting customer data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO customers (name, email, phone, region, vip_level, created_at, total_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            data['customers']
        )
    
    print("Inserting product data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO products (name, category, price, stock, supplier_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            data['products']
        )
    
    print("Inserting employee data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO employees (name, dept_id, salary, hire_date, email, manager_id) VALUES (%s, %s, %s, %s, %s, %s)",
            data['employees']
        )
    
    print("Inserting order data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO orders (customer_id, amount, status, order_date, shipping_address, payment_method) VALUES (%s, %s, %s, %s, %s, %s)",
            data['orders']
        )
    
    print("Inserting order item data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            data['order_items']
        )
    
    print("Inserting log data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO logs (user_id, action, timestamp, level, details) VALUES (%s, %s, %s, %s, %s)",
            data['logs']
        )
    
    print("Inserting banned customer data...")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO banned_customers (customer_id, reason, banned_at) VALUES (%s, %s, %s)",
            data['banned_customers']
        )
    
    print("Collecting database statistics...")
    with conn.cursor() as cur:
        cur.execute("ANALYZE;")
    
    conn.commit()
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM customers) +
                (SELECT COUNT(*) FROM orders) +
                (SELECT COUNT(*) FROM products) +
                (SELECT COUNT(*) FROM employees) +
                (SELECT COUNT(*) FROM departments) +
                (SELECT COUNT(*) FROM logs) +
                (SELECT COUNT(*) FROM suppliers) +
                (SELECT COUNT(*) FROM order_items) +
                (SELECT COUNT(*) FROM banned_customers) as total
        """)
        total = cur.fetchone()[0]
    
    conn.close()
    
    print(f"\nDatabase initialization complete!")
    print(f"Database: benchmark (PostgreSQL)")
    print(f"Total data volume: {total:,} rows")
    return total


def get_table_counts():
    """Query row counts for each table, return {table_name: row_count} dict"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 'customers' as tbl, COUNT(*) as cnt FROM customers
            UNION ALL SELECT 'orders', COUNT(*) FROM orders
            UNION ALL SELECT 'products', COUNT(*) FROM products
            UNION ALL SELECT 'employees', COUNT(*) FROM employees
            UNION ALL SELECT 'departments', COUNT(*) FROM departments
            UNION ALL SELECT 'logs', COUNT(*) FROM logs
            UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
            UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
            UNION ALL SELECT 'banned_customers', COUNT(*) FROM banned_customers
        """)
        results = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in results}


def get_distributions():
    """Print distribution statistics for order status, VIP levels, amounts, etc."""
    conn = get_conn()
    with conn.cursor() as cur:
        print("\n=== Data Distribution Statistics ===")
        
        print("\nOrder Status Distribution:")
        cur.execute("""
            SELECT status, COUNT(*), 
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders), 2) as pct
            FROM orders GROUP BY status ORDER BY COUNT(*) DESC
        """)
        for row in cur.fetchall():
            print(f"  {row[0]:12}: {row[1]:>8,} ({row[2]:>6}%)")
        
        print("\nCustomer VIP Level Distribution:")
        cur.execute("""
            SELECT vip_level, COUNT(*),
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM customers), 2) as pct
            FROM customers GROUP BY vip_level ORDER BY vip_level
        """)
        for row in cur.fetchall():
            print(f"  VIP {row[0]}: {row[1]:>8,} ({row[2]:>6}%)")
        
        print("\nOrder Amount Distribution:")
        cur.execute("""
            SELECT CASE
                WHEN amount < 500 THEN 'Small (<500)'
                WHEN amount < 2000 THEN 'Medium (500-2000)'
                WHEN amount < 5000 THEN 'Large (2000-5000)'
                ELSE 'Very large (>=5000)'
            END as range, COUNT(*),
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders), 2) as pct
            FROM orders GROUP BY 1 ORDER BY MIN(amount)
        """)
        for row in cur.fetchall():
            print(f"  {row[0]:20}: {row[1]:>8,} ({row[2]:>6}%)")
        
        print("\nOrder Item Quantity Statistics:")
        cur.execute("""
            SELECT COUNT(*) as total_items, 
                   COUNT(DISTINCT order_id) as total_orders,
                   ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT order_id), 2) as avg_per_order
            FROM order_items
        """)
        row = cur.fetchone()
        print(f"  Total items: {row[0]:,}")
        print(f"  Total orders: {row[1]:,}")
        print(f"  Avg items per order: {row[2]}")
        
    conn.close()


def explain_analyze(query):
    """Execute EXPLAIN (ANALYZE, BUFFERS) and return execution plan text"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {query}")
        result = cur.fetchall()
    conn.close()
    return '\n'.join([row[0] for row in result])


def compare_plans(original_sql, rewritten_sql, verbose=True):
    """Compare EXPLAIN ANALYZE execution plans of original and rewritten SQL"""
    print("\n" + "=" * 80)
    print("Execution Plan Comparison")
    print("=" * 80)
    
    print("\n[Original SQL]")
    print(original_sql)
    print("\nExecution Plan:")
    print(explain_analyze(original_sql))
    
    print("\n" + "-" * 80)
    print("\n[Optimized SQL]")
    print(rewritten_sql)
    print("\nExecution Plan:")
    print(explain_analyze(rewritten_sql))


def time_query(query, iterations=10):
    """Execute SQL multiple times and return median time (ms), using IQR to remove outliers"""
    times = []
    for _ in range(iterations):
        conn = get_conn()
        with conn.cursor() as cur:
            start = time.perf_counter()
            cur.execute(query)
            cur.fetchall()
            end = time.perf_counter()
        conn.close()
        times.append((end - start) * 1000)
    times.sort()
    return sum(times[1:-1]) / (len(times) - 2) if len(times) > 2 else sum(times) / len(times)


def compare_queries(original, rewritten):
    """A/B comparison: execute each twice and average, return (original_time, rewritten_time)"""
    t_orig = time_query(original)
    t_rew = time_query(rewritten)
    t_rew2 = time_query(rewritten)
    t_orig2 = time_query(original)
    final_orig = (t_orig + t_orig2) / 2
    final_rew = (t_rew + t_rew2) / 2
    return final_orig, final_rew
