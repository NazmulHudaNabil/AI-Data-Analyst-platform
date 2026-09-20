import os
import csv
import psycopg2
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# Set default port if not provided in environment variables
if 'port' not in os.environ:
    os.environ['port'] = '5432'

# -------------------------- Configuration --------------------------

DB_CONFIG = {
    "host": os.environ['host'],
    "port": int(os.environ['port']),
    "database": os.environ['database'],
    "user": os.environ['user'],
    "password": os.environ['password'],
}

# Directory where our CSV files are stored
CSV_DIR = 'data'


# -------------------------- Database Functions --------------------------

def create_tables(cursor):
    """
    Creates all necessary tables for our database.
    We use IF NOT EXISTS to prevent errors if the tables already exist.
    """
    print("Creating tables...")
    
    # Optional: Drop tables first to ensure a clean slate when running this script.
    # CASCADE ensures that tables depending on these are also handled safely.
    cursor.execute("""
    DROP TABLE IF EXISTS public.order_details CASCADE;
    DROP TABLE IF EXISTS public.orders CASCADE;
    DROP TABLE IF EXISTS public.products CASCADE;
    DROP TABLE IF EXISTS public.employees CASCADE;
    DROP TABLE IF EXISTS public.customers CASCADE;
    DROP TABLE IF EXISTS public.categories CASCADE;
    """)
    
    # SQL query to create all tables with their relationships (Foreign Keys)
    create_table_sql = """
    CREATE SCHEMA IF NOT EXISTS public;

    -- =========================================================
    -- CATEGORIES
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.categories (
        categoryID INT PRIMARY KEY,
        categoryName VARCHAR(255) NOT NULL,
        description TEXT
    );

    -- =========================================================
    -- CUSTOMERS
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.customers (
        customerID VARCHAR(255) PRIMARY KEY,
        companyName VARCHAR(255) NOT NULL,
        contactName VARCHAR(255),
        contactTitle VARCHAR(255),
        city VARCHAR(100),
        country VARCHAR(100)
    );

    -- =========================================================
    -- EMPLOYEES
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.employees (
        employeeID INT PRIMARY KEY,
        employeeName VARCHAR(255) NOT NULL,
        title VARCHAR(255),
        city VARCHAR(100),
        country VARCHAR(100),
        reportsTo INT
    );

    -- =========================================================
    -- PRODUCTS
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.products (
        productID INT PRIMARY KEY,
        productName VARCHAR(255) NOT NULL,
        quantityPerUnit VARCHAR(255),
        unitPrice NUMERIC,
        discontinued INT,
        categoryID INT REFERENCES public.categories(categoryID)
    );

    -- =========================================================
    -- ORDERS
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.orders (
        orderID INT PRIMARY KEY,
        customerID VARCHAR(255) REFERENCES public.customers(customerID),
        employeeID INT REFERENCES public.employees(employeeID),
        orderDate DATE,
        requiredDate DATE,
        shippedDate DATE,
        shipperID INT,
        freight NUMERIC
    );

    -- =========================================================
    -- ORDER DETAILS
    -- =========================================================
    CREATE TABLE IF NOT EXISTS public.order_details (
        orderID INT REFERENCES public.orders(orderID),
        productID INT REFERENCES public.products(productID),
        unitPrice NUMERIC,
        quantity INT,
        discount NUMERIC,
        PRIMARY KEY (orderID, productID)
    );
    """
    
    # Execute the query
    cursor.execute(create_table_sql)
    print("Tables created successfully.")


def load_data_from_csv(cursor, table_name, csv_filename):
    """
    Reads a CSV file and inserts its data into the specified table.
    """
    file_path = os.path.join(CSV_DIR, csv_filename)
    
    # Check if the file exists before trying to open it
    if not os.path.exists(file_path):
        print(f"Warning: File '{file_path}' not found. Skipping table '{table_name}'.")
        return

    print(f"Loading data into '{table_name}' from '{csv_filename}'...")
    
    with open(file_path, mode='r', encoding='iso-8859-1') as file:
        reader = csv.reader(file)
        headers = next(reader)  # Read the first row (headers)
        
        # Prepare the SQL INSERT query dynamically based on the headers
        # Example: INSERT INTO public.categories (categoryID, categoryName) VALUES (%s, %s)
        columns = ', '.join(headers)
        placeholders = ', '.join(['%s'] * len(headers))
        insert_query = f"INSERT INTO public.{table_name} ({columns}) VALUES ({placeholders})"
        
        # Loop through the remaining rows and insert them one by one
        count = 0
        for row in reader:
            # Be careful: Sometimes CSVs have empty strings for missing data.
            # We convert empty strings ('') to None, which PostgreSQL treats as NULL.
            cleaned_row = [None if val == '' else val for val in row]
            
            cursor.execute(insert_query, cleaned_row)
            count += 1
            
        print(f"Successfully loaded {count} rows into '{table_name}'.")


# -------------------------- Main Execution --------------------------

def main():
    print("Starting database feed process...")
    
    conn = None
    try:
        # 1. Connect to the PostgreSQL database using our configuration
        conn = psycopg2.connect(**DB_CONFIG)
        
        # 2. Disable autocommit. This means changes won't be saved until we explicitly say conn.commit().
        # This is great for safety: if an error happens halfway, we don't get partial data!
        conn.autocommit = False 
        
        # 3. Create a cursor. A cursor is what we use to execute SQL queries.
        cursor = conn.cursor()
        print("Connected to the database successfully.")

        # 4. Create the tables
        create_tables(cursor)
        
        # 5. Load data from CSVs into the tables
        # Important: The order matters! We must load categories/customers/employees first, 
        # because products and orders depend on them (Foreign Keys).
        load_data_from_csv(cursor, "categories", "categories.csv")
        load_data_from_csv(cursor, "customers", "customers.csv")
        load_data_from_csv(cursor, "employees", "employees.csv")
        load_data_from_csv(cursor, "products", "products.csv")
        load_data_from_csv(cursor, "orders", "orders.csv")
        load_data_from_csv(cursor, "order_details", "order_details.csv")
        
        # 6. Commit the transaction to save all our changes permanently
        conn.commit()
        print("All data successfully committed to the database! 🎉")
        
    except Exception as e:
        # If any error occurs, rollback the changes so we don't end up with corrupted/partial data
        if conn:
            conn.rollback()
        print(f"An error occurred: {e}")
        print("Changes were rolled back.")
        
    finally:
        # 7. Always close the cursor and connection when done, even if an error happened
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

# This block ensures that main() is only called if this script is run directly
if __name__ == "__main__":
    main()