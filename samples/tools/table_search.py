
import csv
import os
from typing import Optional, List, Dict
from enum import Enum


from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------
# ------------------------------------- DB/Table Sea --------------------------------------
# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------


# Define search fields enum for better validation
class ProductSearchField(str, Enum):
    PRODUCT_ID = "product_id"
    SKU = "sku"
    NAME = "name"
    CATEGORY = "category"
    SUPPLIER = "supplier"
    REGION = "region"

@tool(
    name="search_product",
    description="""
        Search for products in the catalog using various search criteria.
        
        This function searches through the product catalog CSV and returns matching products.
        You can search by:
        - product_id: Exact match on product ID (e.g., "PRD-51111")
        - sku: Exact match on SKU (e.g., "TGM-MSE-001")
        - name: Partial match on product name (e.g., "mouse", "keyboard")
        - category: Exact match on category (e.g., "Peripherals", "Audio")
        - supplier: Partial match on supplier name (e.g., "Williams", "Smith")
        - region: Exact match on region (e.g., "APAC", "EMEA", "NA", "LATAM")
        
        Search is case-insensitive. Returns all matching products with complete details.
        
        Each product record contains:
        - product_id: Unique product identifier
        - sku: Stock keeping unit code
        - name: Product name
        - category: Product category
        - price: Product price in dollars
        - stock_qty: Current stock quantity
        - reorder_level: Reorder threshold
        - supplier: Supplier name
        - region: Geographic region
        - release_date: Product release date
        - profit_margin: Profit margin (decimal)
        
        Returns matching products as a list of dictionaries or an error message.
        """
)
def search_product(by: str, key: str) -> dict:
    """
    Search for products in the catalog by various criteria.
    
    Args:
        by (str): The field to search by. Options: "product_id", "sku", "name", "category", "supplier", "region"
        key (str): The search term/value to look for
    
    Returns:
        dict: A dictionary containing either:
            - Success: {'status': 200, 'products': List[dict], 'count': int}
            - Error: {'status': int, 'error': str, 'message': str, 'outward': str}
    
    Example:
        >>> search_product(by="category", key="Peripherals")
        {'status': 200, 'products': [...], 'count': 5}
        
        >>> search_product(by="name", key="mouse")
        {'status': 200, 'products': [...], 'count': 2}
    """
    try:
        # Validate search field
        by_lower = by.lower().strip()
        key_lower = key.lower().strip()
        
        if not key:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": "Search key cannot be empty.",
                "outward": "Please provide a search term to look for products."
            }
        
        valid_fields = [field.value for field in ProductSearchField]
        if by_lower not in valid_fields:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": f"Invalid search field: '{by}'. Valid fields are: {', '.join(valid_fields)}",
                "outward": f"'{by}' is not a valid search field. Please use one of: {', '.join(valid_fields)}"
            }
        
        # Get the absolute path of the current script file
        script_path = os.path.abspath(__file__)

        # Get the directory containing the script
        script_directory = os.path.dirname(script_path)
        csv_path = os.path.join(script_directory, 'products.csv')
        
        if not os.path.exists(csv_path):
            return {
                "status": 500,
                "error": "File Not Found",
                "message": f"Products CSV file not found at {csv_path}",
                "outward": "Unable to access product catalog. Please contact support."
            }
        
        # Read CSV and search
        matching_products = []
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                # Get the field value to compare
                field_value = row.get(by_lower, '').lower().strip()
                
                # Perform search based on field type
                match_found = False
                
                if by_lower in ['product_id', 'sku', 'category', 'region']:
                    # Exact match (case-insensitive)
                    match_found = field_value == key_lower
                elif by_lower in ['name', 'supplier']:
                    # Partial match (case-insensitive)
                    match_found = key_lower in field_value
                
                if match_found:
                    matching_products.append(row)
        
        if not matching_products:
            return {
                "status": 404,
                "error": "Not Found",
                "message": f"No products found matching {by}='{key}'",
                "outward": f"We couldn't find any products matching '{key}' in the {by} field."
            }
        
        return {
            "status": 200,
            "products": matching_products,
            "count": len(matching_products)
        }
    
    except FileNotFoundError:
        return {
            "status": 500,
            "error": "File Not Found",
            "message": f"Products CSV file not found",
            "outward": "Unable to access product catalog. Please contact support."
        }
    except Exception as e:
        return {
            "status": 500,
            "error": "Internal Server Error",
            "message": f"Unexpected error: {str(e)}",
            "outward": "An unexpected error occurred. Please contact support if this continues."
        }



# Define search fields enum for bills
class BillSearchField(str, Enum):
    BILL_ID = "bill_id"
    CUSTOMER_ID = "customer_id"
    CUSTOMER_NAME = "customer_name"
    EMAIL = "email"
    BILL_MONTH = "bill_month"
    PAYMENT_METHOD = "payment_method"

@tool(
    name="search_bill",
    description="""
        Search for bills in the billing system using various search criteria.
        
        This function searches through the bills CSV and returns matching bill records.
        You can search by:
        - bill_id: Exact match on bill ID (e.g., "BIL-41473")
        - customer_id: Exact match on customer ID (e.g., "CUS-00001")
        - customer_name: Partial match on customer name (e.g., "Jane", "Doe")
        - email: Partial match on email (e.g., "jane.doe", "@company.com")
        - bill_month: Exact match on billing month (e.g., "2025-12")
        - bill_amount: Total bill amount in dollars

        - payment_method: Exact match on payment method (e.g., "Credit Card", "ACH", "Wire Transfer", "Check")
        
        Search is case-insensitive. Returns all matching bills with complete details.
        
        Each bill record contains:
        - bill_id: Unique bill identifier
        - customer_id: Customer identifier
        - customer_name: Customer full name
        - email: Customer email address
        - bill_month: Billing month (YYYY-MM format)
        - bill_amount: Total bill amount in dollars
        - payment_method: How the bill was paid
        - paid_date: Date the bill was paid
        
        Returns matching bills as a list of dictionaries or an error message.
        """
)
def search_bill(by: str, key: str) -> dict:
    """
    Search for bills by various criteria.
    
    Args:
        by (str): The field to search by. Options: "bill_id", "customer_id", "customer_name", "email", "bill_month", "payment_method"
        key (str): The search term/value to look for
    
    Returns:
        dict: A dictionary containing either:
            - Success: {'status': 200, 'bills': List[dict], 'count': int}
            - Error: {'status': int, 'error': str, 'message': str, 'outward': str}
    
    Example:
        >>> search_bill(by="customer_name", key="Jane Doe")
        {'status': 200, 'bills': [...], 'count': 5}
        
        >>> search_bill(by="payment_method", key="ACH")
        {'status': 200, 'bills': [...], 'count': 25}
        
        >>> search_bill(by="bill_month", key="2025-12")
        {'status': 200, 'bills': [...], 'count': 20}
    """
    try:
        # Validate search field
        by_lower = by.lower().strip()
        key_lower = key.lower().strip()
        
        if not key:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": "Search key cannot be empty.",
                "outward": "Please provide a search term to look for bills."
            }
        
        valid_fields = [field.value for field in BillSearchField]
        if by_lower not in valid_fields:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": f"Invalid search field: '{by}'. Valid fields are: {', '.join(valid_fields)}",
                "outward": f"'{by}' is not a valid search field. Please use one of: {', '.join(valid_fields)}"
            }
        
        script_path = os.path.abspath(__file__)

        # Get the directory containing the script
        script_directory = os.path.dirname(script_path)
        csv_path = os.path.join(script_directory, 'bills.csv')
        
        if not os.path.exists(csv_path):
            return {
                "status": 500,
                "error": "File Not Found",
                "message": f"Bills CSV file not found at {csv_path}",
                "outward": "Unable to access billing records. Please contact support."
            }
        
        # Read CSV and search
        matching_bills = []
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                # Get the field value to compare
                field_value = row.get(by_lower, '').lower().strip()
                
                # Perform search based on field type
                match_found = False
                
                if by_lower in ['bill_id', 'customer_id', 'bill_month', 'payment_method']:
                    # Exact match (case-insensitive)
                    match_found = field_value == key_lower
                elif by_lower in ['customer_name', 'email']:
                    # Partial match (case-insensitive)
                    match_found = key_lower in field_value
                
                if match_found:
                    matching_bills.append(row)
        
        if not matching_bills:
            return {
                "status": 404,
                "error": "Not Found",
                "message": f"No bills found matching {by}='{key}'",
                "outward": f"We couldn't find any bills matching '{key}' in the {by} field."
            }
        
        return {
            "status": 200,
            "bills": matching_bills,
            "count": len(matching_bills)
        }
    
    except FileNotFoundError:
        return {
            "status": 500,
            "error": "File Not Found",
            "message": f"Bills CSV file not found",
            "outward": "Unable to access billing records. Please contact support."
        }
    except Exception as e:
        return {
            "status": 500,
            "error": "Internal Server Error",
            "message": f"Unexpected error: {str(e)}",
            "outward": "An unexpected error occurred. Please contact support if this continues."
        }
    

# Define search fields enum for employees
class EmployeeSearchField(str, Enum):
    EMPLOYEE_ID = "employee_id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    MANAGER_ID = "manager_id"
    DEPARTMENT = "department"
    REGION = "region"

@tool(
    name="search_employee",
    description="""
        Search for employees in the company directory using various search criteria.
        
        This function searches through the employee CSV and returns matching employee records.
        You can search by:
        - employee_id: Exact match on employee ID (e.g., "1001", "1025")
        - first_name: Partial match on first name (e.g., "John", "Jane")
        - last_name: Partial match on last name (e.g., "Doe", "Smith")
        - email: Partial match on email (e.g., "jane.doe", "@company.com")
        - manager_id: Exact match to find all direct reports (e.g., "1001", "1002")
        - department: Exact match on department (e.g., "Engineering", "HR", "Sales", "IT", "Finance", "Operations", "Executive")
        - region: Exact match on region (e.g., "North", "South", "West")
        
        Search is case-insensitive. Returns all matching employees with complete details.
        
        Each employee record contains:
        - employee_id: Unique employee identifier
        - first_name: Employee first name
        - last_name: Employee last name
        - email: Employee email address
        - dob: Date of birth
        - ssn: Social security number
        - manager_id: Manager's employee ID (empty for executives)
        - department: Department name
        - salary: Annual salary in dollars
        - onboard_month: Month employee was hired (YYYY-MM format)
        - pto_remaining: Remaining PTO days
        - region: Geographic region
        
        Returns matching employees as a list of dictionaries or an error message.
        """
)
def search_employee(by: str, key: str) -> dict:
    """
    Search for employees by various criteria.
    
    Args:
        by (str): The field to search by. Options: "employee_id", "first_name", "last_name", "email", "manager_id", "department", "region"
        key (str): The search term/value to look for
    
    Returns:
        dict: A dictionary containing either:
            - Success: {'status': 200, 'employees': List[dict], 'count': int}
            - Error: {'status': int, 'error': str, 'message': str, 'outward': str}
    
    Example:
        >>> search_employee(by="department", key="Engineering")
        {'status': 200, 'employees': [...], 'count': 8}
        
        >>> search_employee(by="manager_id", key="1001")
        {'status': 200, 'employees': [...], 'count': 6}
        
        >>> search_employee(by="first_name", key="John")
        {'status': 200, 'employees': [...], 'count': 2}
        
        >>> search_employee(by="region", key="North")
        {'status': 200, 'employees': [...], 'count': 15}
    """
    try:
        # Validate search field
        by_lower = by.lower().strip()
        key_lower = key.lower().strip()
        
        if not key:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": "Search key cannot be empty.",
                "outward": "Please provide a search term to look for employees."
            }
        
        valid_fields = [field.value for field in EmployeeSearchField]
        if by_lower not in valid_fields:
            return {
                "status": 400,
                "error": "Bad Request",
                "message": f"Invalid search field: '{by}'. Valid fields are: {', '.join(valid_fields)}",
                "outward": f"'{by}' is not a valid search field. Please use one of: {', '.join(valid_fields)}"
            }
        script_path = os.path.abspath(__file__)

        # Get the directory containing the script
        script_directory = os.path.dirname(script_path)
        csv_path = os.path.join(script_directory, 'employees.csv')
        
        if not os.path.exists(csv_path):
            return {
                "status": 500,
                "error": "File Not Found",
                "message": f"Employees CSV file not found at {csv_path}",
                "outward": "Unable to access employee directory. Please contact support."
            }
        
        # Read CSV and search
        matching_employees = []
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                # Get the field value to compare
                field_value = row.get(by_lower, '').lower().strip()
                
                # Perform search based on field type
                match_found = False
                
                if by_lower in ['employee_id', 'manager_id', 'department', 'region']:
                    # Exact match (case-insensitive)
                    match_found = field_value == key_lower
                elif by_lower in ['first_name', 'last_name', 'email']:
                    # Partial match (case-insensitive)
                    match_found = key_lower in field_value
                
                if match_found:
                    matching_employees.append(row)
        
        if not matching_employees:
            return {
                "status": 404,
                "error": "Not Found",
                "message": f"No employees found matching {by}='{key}'",
                "outward": f"We couldn't find any employees matching '{key}' in the {by} field."
            }
        
        return {
            "status": 200,
            "employees": matching_employees,
            "count": len(matching_employees)
        }
    
    except FileNotFoundError:
        return {
            "status": 500,
            "error": "File Not Found",
            "message": f"Employees CSV file not found",
            "outward": "Unable to access employee directory. Please contact support."
        }
    except Exception as e:
        return {
            "status": 500,
            "error": "Internal Server Error",
            "message": f"Unexpected error: {str(e)}",
            "outward": "An unexpected error occurred. Please contact support if this continues."
        }
    
# orchestrate tools import -f tools/table_search.py \
# -k python \
# -r tools/requirements.txt \
# -p ./tools 


