"""
Scaling up the benchmark database by 5x to get more meaningful performance differences.
Run: python scaleup_data.py
"""
import sys, os, time, random
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(__file__))
from app.db_pg import get_conn, get_schema_sql

SCALE = 5  # multiply current data sizes by this factor

# Helper functions copied from db_pg.py
REGIONS = ['East', 'West', 'North', 'South', 'Central', 'Northeast', 'Southwest', 'Northwest']
CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Books', 'Home', 'Sports', 'Beauty', 'Toys']
STATUSES = ['pending', 'processing', 'shipped', 'completed', 'cancelled', 'refunded']
ACTIONS = ['login', 'logout', 'search', 'view', 'purchase', 'review', 'update_profile', 'delete_account']
LOG_LEVELS = ['INFO', 'DEBUG', 'WARN', 'ERROR']

def random_name():
    first_names = ['John','Jane','Michael','Sarah','David','Emma','Robert','Lisa','William','Emily','James','Olivia','Daniel','Sophia','Matthew','Ava','Christopher','Isabella','Andrew','Mia','Ethan','Charlotte','Joseph','Amelia','Samuel','Harper','Benjamin','Evelyn','Ryan','Abigail','Nathan','Ella','Henry','Scarlett','Jack','Grace','Owen','Chloe','Lucas','Zoey','Alexander','Lily','Thomas','Aria','Noah','Caleb','Madelyn','Dylan','Riley','Logan','Nora','Sebastian','Hannah','Jackson','Layla','Aiden','Bella','Gabriel','Aurora','Julian','Savannah','Luke','Ellie','Levi','Maya','Isaiah','Oliver','Penelope','Mason','Addison','Jayden','Audrey','Wyatt','Brooklyn','Leo','Claire','Josiah','Skylar','Adrian','Anna','Cooper','Samantha','Eli','Stella','Hudson','Tyler','Natalie','Elijah','Leah','Aaron','Landon','Jonathan','Connor','Jose','Hunter','Dominic']
    last_names = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson','Thomas','Taylor','Moore','Jackson','Martin','Lee','Thompson','White','Harris','Clark','Lewis','Robinson','Walker','Young','Allen','King','Wright','Scott','Hill','Green','Adams','Baker','Nelson','Carter','Mitchell','Perez','Roberts','Turner','Phillips','Campbell','Parker','Evans','Edwards','Collins','Stewart','Sanchez','Morris','Rogers','Reed','Cook','Morgan','Bell','Murphy','Bailey','Rivera','Cooper','Richardson','Cox','Howard','Ward','Torres','Peterson','Gray','Ramirez','James','Watson','Brooks','Kelly','Sanders','Price','Bennett','Wood','Barnes','Ross','Henderson','Coleman','Jenkins','Perry','Powell','Long','Patterson','Hughes','Flores','Washington','Butler','Simmons','Foster','Gonzales','Bryant','Alexander','Russell','Griffin','Diaz','Hayes']
    return random.choice(first_names) + ' ' + random.choice(last_names)

def random_phone():
    prefixes = ['138','139','150','151','152','157','158','159','186','187','188','189']
    return random.choice(prefixes) + ''.join([str(random.randint(0,9)) for _ in range(8)])

def random_email(name):
    domains = ['qq.com', '163.com', 'gmail.com', 'outlook.com', 'yahoo.com', 'company.cn']
    return f"{name}.{random.randint(100,999)}@{random.choice(domains)}"

def random_date(start, end):
    return date(random.randint(start, end), random.randint(1,12), random.randint(1,28))

def random_datetime(start, end):
    return datetime(random.randint(start, end), random.randint(1,12), random.randint(1,28),
                    random.randint(0,23), random.randint(0,59), random.randint(0,59))

def skewed_region():
    dist = {'East': 0.3, 'West': 0.2, 'North': 0.15, 'South': 0.15, 'Central': 0.1, 
            'Northeast': 0.05, 'Southwest': 0.03, 'Northwest': 0.02}
    return random.choices(list(dist.keys()), weights=list(dist.values()))[0]

def skewed_vip():
    dist = {0: 0.5, 1: 0.2, 2: 0.12, 3: 0.08, 4: 0.06, 5: 0.04}
    return random.choices(list(dist.keys()), weights=list(dist.values()))[0]

def skewed_amount():
    r = random.random()
    if r < 0.4: return round(random.uniform(50, 500), 2)
    elif r < 0.7: return round(random.uniform(500, 2000), 2)
    elif r < 0.85: return round(random.uniform(2000, 5000), 2)
    elif r < 0.95: return round(random.uniform(5000, 10000), 2)
    else: return round(random.uniform(10000, 50000), 2)

def skewed_status():
    r = random.random()
    if r < 0.4: return 'completed'
    elif r < 0.6: return 'pending'
    elif r < 0.75: return 'processing'
    elif r < 0.85: return 'shipped'
    elif r < 0.95: return 'cancelled'
    else: return 'refunded'

def skewed_quantity():
    r = random.random()
    if r < 0.3: return 1
    elif r < 0.6: return 2
    elif r < 0.8: return 3
    elif r < 0.9: return 4
    elif r < 0.95: return 5
    elif r < 0.98: return 6
    elif r < 0.99: return 7
    else: return 8

def batch_insert(cur, sql, rows, batch_size=1000, label=""):
    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i:i+batch_size]
        cur.executemany(sql, batch)
        if i % (batch_size * 10) == 0:
            print(f"  {label}: {min(i+batch_size, total)}/{total}", flush=True)

def main():
    s = SCALE
    
    print(f"Scaling database by {s}x...")
    print(f"Target: ~{1.5 * s} million rows total")
    print()
    
    conn = get_conn()
    conn.autocommit = False
    
    print("Dropping existing tables...")
    with conn.cursor() as cur:
        cur.execute(get_schema_sql())
    conn.commit()
    
    # --- Departments (fixed 50) ---
    print("Generating departments (50)...")
    departments = []
    for i in range(1, 51):
        departments.append((
            f"Dept-{random.choice(['R&D','Sales','Marketing','HR','Finance','Operations','Support','Logistics'])}-{i}",
            random.randint(100000, 5000000),
            random.choice(['Beijing','Shanghai','Guangzhou','Shenzhen','Hangzhou','Chengdu'])
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO departments (name, budget, location) VALUES (%s, %s, %s)",
            departments
        )
    conn.commit()
    print(f"  departments: {len(departments)} rows")
    
    # --- Suppliers (fixed 500) ---
    print("Generating suppliers (500)...")
    suppliers = []
    for i in range(1, 501):
        suppliers.append((
            f"Supplier-{i}-{random.choice(['Tech','Industry','Trading','Group'])}",
            random_name(), random_phone(),
            random.choice(REGIONS),
            round(random.uniform(3.0, 5.0), 1)
        ))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO suppliers (name, contact, phone, region, rating) VALUES (%s, %s, %s, %s, %s)",
            suppliers
        )
    conn.commit()
    print(f"  suppliers: {len(suppliers)} rows")
    
    # --- Customers (50k * s) ---
    n_customers = 50000 * s
    print(f"Generating customers ({n_customers})...")
    customers = []
    for i in range(1, n_customers + 1):
        name = random_name()
        customers.append((
            name, random_email(name), random_phone(),
            skewed_region(), skewed_vip(),
            random_date(2020, 2024),
            round(random.uniform(0, 50000), 2)
        ))
    with conn.cursor() as cur:
        batch_insert(cur,
            "INSERT INTO customers (name, email, phone, region, vip_level, created_at, total_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            customers, label="customers"
        )
    conn.commit()
    customers = None
    print(f"  customers: {n_customers} rows")
    
    # --- Products (20k * s) ---
    n_products = 20000 * s
    print(f"Generating products ({n_products})...")
    products = []
    for i in range(1, n_products + 1):
        products.append((
            f"Product-{i}-{random.choice(['Model-A','Model-B','Model-C','Standard','Pro','Flagship'])}",
            random.choice(CATEGORIES),
            round(random.uniform(9.9, 9999.9), 2),
            random.randint(0, 1000),
            random.randint(1, 500),
            random_date(2022, 2024)
        ))
    with conn.cursor() as cur:
        batch_insert(cur,
            "INSERT INTO products (name, category, price, stock, supplier_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            products, label="products"
        )
    conn.commit()
    products = None
    print(f"  products: {n_products} rows")
    
    # --- Employees (10k * s) ---
    n_employees = 10000 * s
    print(f"Generating employees ({n_employees})...")
    employees = []
    for i in range(1, n_employees + 1):
        name = random_name()
        manager_id = random.randint(1, n_employees) if random.random() > 0.3 else None
        employees.append((
            name, random.randint(1, 50),
            round(random.uniform(5000, 50000), 2),
            random_date(2015, 2024),
            f"emp{i}@company.com", manager_id
        ))
    with conn.cursor() as cur:
        batch_insert(cur,
            "INSERT INTO employees (name, dept_id, salary, hire_date, email, manager_id) VALUES (%s, %s, %s, %s, %s, %s)",
            employees, label="employees"
        )
    conn.commit()
    employees = None
    print(f"  employees: {n_employees} rows")
    
    # --- Orders (200k * s) ---
    n_orders = 200000 * s
    print(f"Generating orders ({n_orders})...")
    orders = []
    for order_id in range(1, n_orders + 1):
        orders.append((
            random.randint(1, n_customers),
            skewed_amount(), skewed_status(),
            random_date(2023, 2024),
            f"Addr-{random.randint(1,9999)}-{random.choice(['St','Rd','Ln'])}",
            random.choice(['Alipay','WeChat','CreditCard','BankTransfer'])
        ))
    with conn.cursor() as cur:
        batch_insert(cur,
            "INSERT INTO orders (customer_id, amount, status, order_date, shipping_address, payment_method) VALUES (%s, %s, %s, %s, %s, %s)",
            orders, label="orders"
        )
    conn.commit()
    orders = None
    print(f"  orders: {n_orders} rows")
    
    # --- Order items - streamed in batches to avoid memory blow ---
    n_items_est = n_orders * 5
    print(f"Generating order_items (~{n_items_est})...")
    with conn.cursor() as cur:
        total_inserted = 0
        batch = []
        for order_id in range(1, n_orders + 1):
            num_items = random.randint(3, 8)
            for _ in range(num_items):
                batch.append((
                    order_id,
                    random.randint(1, n_products),
                    skewed_quantity(),
                    round(random.uniform(10, 1000), 2)
                ))
            if len(batch) >= 5000:
                cur.executemany(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    batch
                )
                total_inserted += len(batch)
                batch = []
                if total_inserted % 100000 == 0:
                    print(f"  order_items: {total_inserted} rows", flush=True)
                    conn.commit()
        if batch:
            cur.executemany(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                batch
            )
            total_inserted += len(batch)
        conn.commit()
    print(f"  order_items: {total_inserted} rows")
    
    # --- Logs (100k * s) ---
    n_logs = 100000 * s
    print(f"Generating logs ({n_logs})...")
    logs = []
    for i in range(1, n_logs + 1):
        logs.append((
            random.randint(1, n_customers),
            random.choice(ACTIONS),
            random_datetime(2023, 2024),
            random.choice(LOG_LEVELS),
            f"Action-{i}-{random.choice(['Success','Failed','Warning'])}"
        ))
    with conn.cursor() as cur:
        batch_insert(cur,
            "INSERT INTO logs (user_id, action, timestamp, level, details) VALUES (%s, %s, %s, %s, %s)",
            logs, label="logs"
        )
    conn.commit()
    logs = None
    print(f"  logs: {n_logs} rows")
    
    # --- Banned customers (2.5k * s) ---
    n_banned = min(2500 * s, n_customers)
    print(f"Generating banned_customers ({n_banned})...")
    banned_ids = random.sample(range(1, n_customers + 1), min(n_banned, n_customers))
    banned = [(cid, random.choice(['Fraud','Violation','Arrears','Fake Transaction','Excessive Complaints']), random_date(2023, 2024)) for cid in banned_ids]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO banned_customers (customer_id, reason, banned_at) VALUES (%s, %s, %s)",
            banned
        )
    conn.commit()
    print(f"  banned_customers: {len(banned)} rows")
    
    # --- ANALYZE ---
    print("\nCollecting statistics...")
    with conn.cursor() as cur:
        cur.execute("ANALYZE;")
    conn.commit()
    
    # --- Summary ---
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, (SELECT COUNT(*) FROM pg_class WHERE relname = table_name)
            FROM (VALUES 
                ('departments'),('suppliers'),('customers'),('products'),
                ('employees'),('orders'),('order_items'),('logs'),('banned_customers')
            ) AS t(table_name)
        """)
        cur.execute("""
            SELECT 'customers' as t, COUNT(*) FROM customers
            UNION ALL SELECT 'orders', COUNT(*) FROM orders
            UNION ALL SELECT 'products', COUNT(*) FROM products
            UNION ALL SELECT 'employees', COUNT(*) FROM employees
            UNION ALL SELECT 'departments', COUNT(*) FROM departments
            UNION ALL SELECT 'logs', COUNT(*) FROM logs
            UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
            UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
            UNION ALL SELECT 'banned_customers', COUNT(*) FROM banned_customers
        """)
        counts = {r[0]: r[1] for r in cur.fetchall()}
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("Database scale-up complete!")
    total = sum(counts.values())
    for t, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {t:20} {c:>12,}")
    print(f"  {'TOTAL':20} {total:>12,}")
    print(f"Scale factor: {s}x")
    print("=" * 50)

if __name__ == "__main__":
    main()
