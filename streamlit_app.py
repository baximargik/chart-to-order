import streamlit as st
import pandas as pd
import time
import logging
import datetime
import json
import io
import hashlib
import os
import base64
import hmac
from kiteconnect import KiteConnect
import numpy as np

# Setup environment variables to store secrets in production
# For local development, we'll use session state and a simple file-based user system

# Configure page settings
st.set_page_config(
    page_title="Zerodha Trading Tool",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('zerodha_trading_tool')

# User database simple file-based system (in production, use a real database)
USER_DB_FILE = "users.json"

# Initialize session variables
def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'admin' not in st.session_state:
        st.session_state.admin = False
    if 'stocks_df' not in st.session_state:
        st.session_state.stocks_df = None
    if 'selected_stocks' not in st.session_state:
        st.session_state.selected_stocks = None
    if 'kite' not in st.session_state:
        st.session_state.kite = None
    if 'api_authenticated' not in st.session_state:
        st.session_state.api_authenticated = False
    if 'account_balance' not in st.session_state:
        st.session_state.account_balance = None
    if 'orders_result' not in st.session_state:
        st.session_state.orders_result = None
    if 'available_instruments' not in st.session_state:
        st.session_state.available_instruments = None

init_session_state()

# Create a simple database file if it doesn't exist
def initialize_user_db():
    if not os.path.exists(USER_DB_FILE):
        # Create a default admin account
        default_admin = "admin"
        # In production, use a strong password and better hashing
        default_password = "admin123"
        
        # Hash the password (in production, use a stronger method with salt)
        hashed_password = hashlib.sha256(default_password.encode()).hexdigest()
        
        users = {
            default_admin: {
                "password": hashed_password,
                "admin": True,
                "created_at": datetime.datetime.now().isoformat(),
                "zerodha_api_key": "",
                "zerodha_api_secret": ""
            }
        }
        
        with open(USER_DB_FILE, 'w') as f:
            json.dump(users, f)
        
        logger.info("Initialized user database with default admin account")

# Get all users from the database
def get_users():
    try:
        if not os.path.exists(USER_DB_FILE):
            initialize_user_db()
            
        with open(USER_DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading user database: {str(e)}")
        st.error("Error accessing user database. Please contact the administrator.")
        return {}

# Save users to the database
def save_users(users):
    try:
        with open(USER_DB_FILE, 'w') as f:
            json.dump(users, f)
        return True
    except Exception as e:
        logger.error(f"Error saving user database: {str(e)}")
        return False

# Verify user credentials
def verify_user(username, password):
    users = get_users()
    
    if username in users:
        # Hash the provided password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check if the hash matches
        if users[username]["password"] == hashed_password:
            return True, users[username].get("admin", False), users[username]
    
    return False, False, None

# Add a new user
def add_user(username, password, is_admin=False, zerodha_api_key="", zerodha_api_secret=""):
    users = get_users()
    
    if username in users:
        return False, "Username already exists"
    
    # Hash the password
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    # Add the new user
    users[username] = {
        "password": hashed_password,
        "admin": is_admin,
        "created_at": datetime.datetime.now().isoformat(),
        "zerodha_api_key": zerodha_api_key,
        "zerodha_api_secret": zerodha_api_secret
    }
    
    # Save the updated user database
    if save_users(users):
        return True, "User added successfully"
    else:
        return False, "Error saving user database"

# Update user details
def update_user(username, data):
    users = get_users()
    
    if username not in users:
        return False, "User not found"
    
    # Update the user data
    for key, value in data.items():
        if key == "password" and value:
            # Hash the new password
            users[username][key] = hashlib.sha256(value.encode()).hexdigest()
        elif key != "password" or value:
            users[username][key] = value
    
    # Save the updated user database
    if save_users(users):
        return True, "User updated successfully"
    else:
        return False, "Error saving user database"

# Delete a user
def delete_user(username):
    users = get_users()
    
    if username not in users:
        return False, "User not found"
    
    # Delete the user
    del users[username]
    
    # Save the updated user database
    if save_users(users):
        return True, "User deleted successfully"
    else:
        return False, "Error saving user database"

# Secure API credentials storage
def save_api_credentials(username, api_key, api_secret):
    return update_user(username, {
        "zerodha_api_key": api_key,
        "zerodha_api_secret": api_secret
    })

# Get stored API credentials
def get_api_credentials(username):
    users = get_users()
    
    if username in users:
        return users[username].get("zerodha_api_key", ""), users[username].get("zerodha_api_secret", "")
    
    return "", ""

# Login function
def login():
    st.title("Zerodha Trading Tool - Login")
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    authenticated, is_admin, user_data = verify_user(username, password)
                    
                    if authenticated:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.admin = is_admin
                        st.success("Login successful!")
                        
                        # Reload the page to update the UI
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Create New Account")
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if not new_username or not new_password or not confirm_password:
                    st.error("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message = add_user(new_username, new_password)
                    
                    if success:
                        st.success(f"{message} You can now login.")
                    else:
                        st.error(message)

# Admin dashboard
def admin_dashboard():
    st.title("Admin Dashboard")
    
    # Create tabs for user management and system settings
    tab1, tab2 = st.tabs(["User Management", "System Settings"])
    
    with tab1:
        st.subheader("User Management")
        
        # Get all users
        users = get_users()
        
        # Create a table of users
        user_data = []
        for username, data in users.items():
            user_data.append({
                "Username": username,
                "Admin": "Yes" if data.get("admin", False) else "No",
                "Created": data.get("created_at", "Unknown"),
                "API Key Set": "Yes" if data.get("zerodha_api_key", "") else "No"
            })
        
        # Display user table
        if user_data:
            st.dataframe(pd.DataFrame(user_data))
        else:
            st.info("No users found")
        
        # Add new user form
        st.subheader("Add New User")
        
        with st.form("add_user_form"):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            is_admin = st.checkbox("Admin User")
            
            submitted = st.form_submit_button("Add User")
            
            if submitted:
                if not new_username or not new_password:
                    st.error("Please fill in all required fields")
                else:
                    success, message = add_user(new_username, new_password, is_admin)
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        # Delete user form
        st.subheader("Delete User")
        
        del_username = st.selectbox("Select User to Delete", list(users.keys()))
        
        if st.button("Delete User"):
            if del_username == st.session_state.username:
                st.error("You cannot delete your own account")
            else:
                success, message = delete_user(del_username)
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with tab2:
        st.subheader("System Settings")
        
        # Add any system settings here
        st.info("System settings will be added in a future update")

# Function to generate access token
def generate_access_token(api_key, api_secret, request_token):
    try:
        kite = KiteConnect(api_key=api_key)
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        logger.info("Access token generated successfully")
        return kite, access_token
    except Exception as e:
        logger.error(f"Error generating access token: {str(e)}")
        st.error(f"Error generating access token: {str(e)}")
        return None, None

# Function to get account balance
def get_account_balance(kite):
    try:
        # Get margins
        margins = kite.margins()
        
        # Log full margins response for debugging
        logger.info(f"Full margins response: {json.dumps(margins)}")
        
        balance_info = {}
        
        # Check for 'equity' segment in margins
        if 'equity' in margins:
            equity = margins['equity']
            
            # Check for 'available' dict in equity
            if 'available' in equity and isinstance(equity['available'], dict):
                available = equity['available']
                
                # Check for 'cash' in available
                if 'cash' in available:
                    balance_info['Available Cash'] = available['cash']
            
            # Check for 'utilized' dict in equity
            if 'utilized' in equity and isinstance(equity['utilized'], dict):
                utilized = equity['utilized']
                
                # Check for 'debits' in utilized
                if 'debits' in utilized:
                    balance_info['Used Margin'] = utilized['debits']
        
        return balance_info
            
    except Exception as e:
        logger.error(f"Error retrieving account balance: {str(e)}")
        return None

# Function to fetch stock details from Zerodha with better permission handling
def fetch_stock_details(kite, symbol):
    try:
        # Try to search in the available instruments
        if st.session_state.available_instruments is None:
            try:
                st.session_state.available_instruments = kite.instruments("NSE")
            except Exception as e:
                logger.error(f"Error fetching instruments: {str(e)}")
                st.warning("Could not fetch instruments list from Zerodha. Using limited functionality.")
                return {"Symbol": symbol, "Name": symbol, "LastPrice": 0}
        
        instruments = st.session_state.available_instruments
        
        # Filter the instrument by symbol
        found_instruments = [inst for inst in instruments if inst['tradingsymbol'] == symbol.upper()]
        
        if not found_instruments:
            # Search case insensitive
            found_instruments = [inst for inst in instruments if inst['tradingsymbol'].upper() == symbol.upper()]
        
        if found_instruments:
            instrument = found_instruments[0]
            
            # Fetch the latest quote
            try:
                quote = kite.quote(f"NSE:{symbol}")
                
                if f"NSE:{symbol}" in quote:
                    quote_data = quote[f"NSE:{symbol}"]
                    
                    return {
                        'Symbol': instrument['tradingsymbol'],
                        'Name': instrument['name'],
                        'Exchange': instrument['exchange'],
                        'ISIN': instrument.get('isin', 'N/A'),
                        'LastPrice': quote_data.get('last_price', 0),
                        'Change': quote_data.get('net_change', 0),
                        'PctChange': round(quote_data.get('net_change', 0) / quote_data.get('last_price', 1) * 100, 2) if quote_data.get('last_price') else 0,
                        'Volume': quote_data.get('volume', 0),
                        'AvgPrice': quote_data.get('average_price', 0),
                        'OHLC': {
                            'open': quote_data.get('ohlc', {}).get('open', 0),
                            'high': quote_data.get('ohlc', {}).get('high', 0),
                            'low': quote_data.get('ohlc', {}).get('low', 0),
                            'close': quote_data.get('ohlc', {}).get('close', 0)
                        }
                    }
            except Exception as quote_error:
                logger.error(f"Error fetching quote for {symbol}: {str(quote_error)}")
                
                if "Insufficient permission" in str(quote_error):
                    st.warning(f"⚠️ Your Zerodha API key doesn't have permission to fetch quotes. You'll need to manually enter prices or upgrade your API permissions.")
                
                # Return basic info without quote data
                return {
                    'Symbol': instrument['tradingsymbol'],
                    'Name': instrument['name'],
                    'Exchange': instrument['exchange'],
                    'ISIN': instrument.get('isin', 'N/A'),
                    'LastPrice': 0,  # Set to 0 since we can't get the price
                    'Volume': 0,
                    'PctChange': 0
                }
        else:
            logger.warning(f"Instrument not found for symbol: {symbol}")
            return {"Symbol": symbol, "Name": symbol, "LastPrice": 0}
                
    except Exception as e:
        logger.error(f"Error fetching stock details for {symbol}: {str(e)}")
        return {"Symbol": symbol, "Name": symbol, "LastPrice": 0}

# Modified order placement function to work without price data
def place_orders(kite, stocks_df, order_type="MARKET", dry_run=True, gtt_details=None):
    successful_orders = 0
    failed_orders = 0
    orders_info = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_stocks = len(stocks_df)
    for i, (_, row) in enumerate(stocks_df.iterrows()):
        try:
            symbol = row['Symbol']
            quantity = int(row['Quantity'])
            
            # Update progress
            progress = (i + 1) / total_stocks
            progress_bar.progress(progress)
            status_text.text(f"Processing {i+1} of {total_stocks}: {symbol}")
            
            if dry_run:
                logger.info(f"[DRY RUN] Would place {order_type} order for {quantity} shares of {symbol}")
                order_id = f"dry-run-{successful_orders+1}"
                successful_orders += 1
            else:
                if order_type == "MARKET":
                    # Place market order
                    order_id = kite.place_order(
                        variety=kite.VARIETY_REGULAR,
                        exchange=kite.EXCHANGE_NSE,
                        tradingsymbol=symbol,
                        transaction_type=kite.TRANSACTION_TYPE_BUY,
                        quantity=quantity,
                        order_type=kite.ORDER_TYPE_MARKET,
                        product=kite.PRODUCT_CNC  # CNC for delivery
                    )
                elif order_type == "GTT":
                    # Place GTT order
                    if gtt_details and 'trigger_price' in gtt_details and 'limit_price' in gtt_details:
                        trigger_price = gtt_details['trigger_price'].get(symbol, 0)
                        limit_price = gtt_details['limit_price'].get(symbol, 0)
                        
                        if trigger_price <= 0 or limit_price <= 0:
                            raise ValueError("Trigger price and limit price must be greater than zero")
                        
                        # Create a GTT order
                        gtt_params = {
                            "trigger_type": kite.GTT_TYPE_SINGLE,
                            "tradingsymbol": symbol,
                            "exchange": kite.EXCHANGE_NSE,
                            "trigger_values": [trigger_price],
                            "last_price": trigger_price,
                            "orders": [{
                                "transaction_type": kite.TRANSACTION_TYPE_BUY,
                                "quantity": quantity,
                                "price": limit_price,
                                "order_type": kite.ORDER_TYPE_LIMIT,
                                "product": kite.PRODUCT_CNC
                            }]
                        }
                        
                        # Place the GTT order
                        order_id = kite.place_gtt(gtt_params)
                    else:
                        raise ValueError("GTT details missing trigger_price or limit_price")
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
                    
                logger.info(f"Successfully placed {order_type} order for {quantity} shares of {symbol}, Order ID: {order_id}")
                successful_orders += 1
            
            # Get price from the row if available
            price = row['Price'] if 'Price' in row else 'N/A'
            if price == 'N/A' or price == 0:
                # Try to fetch price from Zerodha
                stock_details = fetch_stock_details(kite, symbol)
                if stock_details and 'LastPrice' in stock_details and stock_details['LastPrice'] > 0:
                    price = stock_details['LastPrice']
                else:
                    price = 'N/A'  # Keep as N/A if we can't get a valid price
            
            if price != 'N/A' and price != 0:
                try:
                    price = float(price)
                    estimated_cost = price * quantity
                except:
                    estimated_cost = 'N/A'
            else:
                estimated_cost = 'N/A'
                
            orders_info.append({
                'Symbol': symbol,
                'Quantity': quantity,
                'Order ID': order_id,
                'Status': 'Success' if not dry_run else 'Dry Run',
                'Price': price,
                'Estimated Cost': estimated_cost,
                'Order Type': order_type
            })
            
            # Sleep to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {str(e)}")
            failed_orders += 1
            
            orders_info.append({
                'Symbol': symbol,
                'Quantity': row['Quantity'] if 'Quantity' in row else 'N/A',
                'Order ID': 'Failed',
                'Status': f'Error: {str(e)}',
                'Price': row['Price'] if 'Price' in row else 'N/A',
                'Estimated Cost': 'N/A',
                'Order Type': order_type
            })
    
    # Create a DataFrame with order information
    orders_df = pd.DataFrame(orders_info)
    logger.info(f"Order summary: {successful_orders} successful, {failed_orders} failed")
    
    return successful_orders, failed_orders, orders_df

# Function to place orders
def place_orders(kite, stocks_df, order_type="MARKET", dry_run=True, gtt_details=None):
    successful_orders = 0
    failed_orders = 0
    orders_info = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_stocks = len(stocks_df)
    for i, (_, row) in enumerate(stocks_df.iterrows()):
        try:
            symbol = row['Symbol']
            quantity = int(row['Quantity'])
            
            # Update progress
            progress = (i + 1) / total_stocks
            progress_bar.progress(progress)
            status_text.text(f"Processing {i+1} of {total_stocks}: {symbol}")
            
            if dry_run:
                logger.info(f"[DRY RUN] Would place {order_type} order for {quantity} shares of {symbol}")
                order_id = f"dry-run-{successful_orders+1}"
                successful_orders += 1
            else:
                if order_type == "MARKET":
                    # Place market order
                    order_id = kite.place_order(
                        variety=kite.VARIETY_REGULAR,
                        exchange=kite.EXCHANGE_NSE,
                        tradingsymbol=symbol,
                        transaction_type=kite.TRANSACTION_TYPE_BUY,
                        quantity=quantity,
                        order_type=kite.ORDER_TYPE_MARKET,
                        product=kite.PRODUCT_CNC  # CNC for delivery
                    )
                elif order_type == "GTT":
                    # Place GTT order
                    if gtt_details and 'trigger_price' in gtt_details and 'limit_price' in gtt_details:
                        trigger_price = gtt_details['trigger_price'].get(symbol, 0)
                        limit_price = gtt_details['limit_price'].get(symbol, 0)
                        
                        if trigger_price <= 0 or limit_price <= 0:
                            raise ValueError("Trigger price and limit price must be greater than zero")
                        
                        # Create a GTT order
                        gtt_params = {
                            "trigger_type": kite.GTT_TYPE_SINGLE,
                            "tradingsymbol": symbol,
                            "exchange": kite.EXCHANGE_NSE,
                            "trigger_values": [trigger_price],
                            "last_price": trigger_price,
                            "orders": [{
                                "transaction_type": kite.TRANSACTION_TYPE_BUY,
                                "quantity": quantity,
                                "price": limit_price,
                                "order_type": kite.ORDER_TYPE_LIMIT,
                                "product": kite.PRODUCT_CNC
                            }]
                        }
                        
                        # Place the GTT order
                        order_id = kite.place_gtt(gtt_params)
                    else:
                        raise ValueError("GTT details missing trigger_price or limit_price")
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
                    
                logger.info(f"Successfully placed {order_type} order for {quantity} shares of {symbol}, Order ID: {order_id}")
                successful_orders += 1
            
            # Get price from the row if available
            price = row['Price'] if 'Price' in row else 'N/A'
            if price == 'N/A' or price == 0:
                # Try to fetch price from Zerodha
                stock_details = fetch_stock_details(kite, symbol)
                if stock_details and 'LastPrice' in stock_details:
                    price = stock_details['LastPrice']
            
            if price != 'N/A' and price != 0:
                try:
                    price = float(price)
                    estimated_cost = price * quantity
                except:
                    estimated_cost = 'N/A'
            else:
                estimated_cost = 'N/A'
                
            orders_info.append({
                'Symbol': symbol,
                'Quantity': quantity,
                'Order ID': order_id,
                'Status': 'Success' if not dry_run else 'Dry Run',
                'Price': price,
                'Estimated Cost': estimated_cost,
                'Order Type': order_type
            })
            
            # Sleep to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {str(e)}")
            failed_orders += 1
            
            orders_info.append({
                'Symbol': symbol,
                'Quantity': row['Quantity'] if 'Quantity' in row else 'N/A',
                'Order ID': 'Failed',
                'Status': f'Error: {str(e)}',
                'Price': row['Price'] if 'Price' in row else 'N/A',
                'Estimated Cost': 'N/A',
                'Order Type': order_type
            })
    
    # Create a DataFrame with order information
    orders_df = pd.DataFrame(orders_info)
    logger.info(f"Order summary: {successful_orders} successful, {failed_orders} failed")
    
    return successful_orders, failed_orders, orders_df

# Calculate optimal quantities based on available balance
def calculate_optimal_quantities(stocks_df, available_balance):
    try:
        # Create a working copy
        working_df = stocks_df.copy()
        
        # Ensure Price column exists and is numeric
        if 'Price' not in working_df.columns:
            working_df['Price'] = 0
        
        # Convert Price to numeric, handling non-numeric values
        working_df['Price'] = pd.to_numeric(working_df['Price'].astype(str).str.replace(',', ''), errors='coerce')
        
        # Replace NaN or 0 prices with fetched prices if available
        for i, row in working_df.iterrows():
            if pd.isna(row['Price']) or row['Price'] == 0:
                if 'FetchedPrice' in row and row['FetchedPrice'] > 0:
                    working_df.at[i, 'Price'] = row['FetchedPrice']
        
        # Filter out rows with invalid prices
        valid_df = working_df[working_df['Price'] > 0].copy()
        
        if valid_df.empty:
            return working_df, "No valid prices found for any stock"
        
        # Calculate the total cost with quantity = 1 for each stock
        valid_df['Cost'] = valid_df['Price']
        
        # Total cost if we buy 1 share of each stock
        total_base_cost = valid_df['Cost'].sum()
        
        if total_base_cost > 0:
            # Calculate allocation ratio
            allocation_ratio = available_balance / total_base_cost
            
            # Calculate optimal quantity for each stock
            valid_df['OptimalQuantity'] = (allocation_ratio * valid_df['Price'] / valid_df['Price']).apply(lambda x: max(1, int(x)))
            
            # Check if we're within budget
            valid_df['TotalCost'] = valid_df['OptimalQuantity'] * valid_df['Price']
            total_cost = valid_df['TotalCost'].sum()
            
            # If we're over budget, reduce quantities proportionally
            if total_cost > available_balance:
                reduction_factor = available_balance / total_cost
                valid_df['OptimalQuantity'] = (valid_df['OptimalQuantity'] * reduction_factor).apply(lambda x: max(1, int(x)))
                
                # Recalculate final cost
                valid_df['TotalCost'] = valid_df['OptimalQuantity'] * valid_df['Price']
            
            # Update the original dataframe with optimal quantities
            for i, row in valid_df.iterrows():
                idx = working_df.index.get_loc(i)
                working_df.at[idx, 'Quantity'] = row['OptimalQuantity']
            
            # Calculate the final total cost
            final_total_cost = sum(working_df['Price'] * working_df['Quantity'])
            
            return working_df, f"Optimized quantities to use ₹{final_total_cost:.2f} of available ₹{available_balance:.2f}"
        else:
            return working_df, "Could not calculate optimal quantities due to invalid prices"
    
    except Exception as e:
        logger.error(f"Error calculating optimal quantities: {str(e)}")
        return stocks_df, f"Error calculating optimal quantities: {str(e)}"

# User profile page
def user_profile_page():
    st.header("User Profile")
    
    # Display user information
    st.subheader(f"Profile: {st.session_state.username}")
    
    if st.session_state.admin:
        st.write("Account Type: Administrator")
    else:
        st.write("Account Type: Regular User")
    
    # Password change form
    st.subheader("Change Password")
    
    with st.form("change_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        submitted = st.form_submit_button("Change Password")
        
        if submitted:
            if not current_password or not new_password or not confirm_password:
                st.error("Please fill in all password fields")
            elif new_password != confirm_password:
                st.error("New passwords do not match")
            else:
                # Verify current password
                authenticated, _, _ = verify_user(st.session_state.username, current_password)
                
                if not authenticated:
                    st.error("Current password is incorrect")
                else:
                    # Update password
                    success, message = update_user(st.session_state.username, {"password": new_password})
                    
                    if success:
                        st.success("Password changed successfully")
                    else:
                        st.error(f"Failed to change password: {message}")
    
    # Zerodha API credentials
    st.subheader("Zerodha API Credentials")
    
    # Get current credentials
    api_key, api_secret = get_api_credentials(st.session_state.username)
    
    with st.form("api_credentials_form"):
        new_api_key = st.text_input("API Key", value=api_key)
        new_api_secret = st.text_input("API Secret", type="password", 
                                      value="••••••••" if api_secret else "")
        
        # Only update if the secret field is changed (not showing bullets)
        update_secret = new_api_secret != "••••••••"
        
        submitted = st.form_submit_button("Save API Credentials")
        
        if submitted:
            if not new_api_key:
                st.error("API Key cannot be empty")
            else:
                # Update credentials
                data = {
                    "zerodha_api_key": new_api_key
                }
                
                # Only update secret if it was changed
                if update_secret:
                    data["zerodha_api_secret"] = new_api_secret
                
                success, message = update_user(st.session_state.username, data)
                
                if success:
                    st.success("API credentials updated successfully")
                else:
                    st.error(f"Failed to update API credentials: {message}")

# Function to read CSV
def read_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        logger.info(f"Successfully read {len(df)} stocks from CSV")
        
        # Verify required columns exist
        required_columns = ['Symbol']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            st.error(f"The CSV file is missing these required columns: {missing_columns}")
            st.info("The CSV must contain at least a 'Symbol' column.")
            return None
            
        # Add a Quantity column if it doesn't exist
        if 'Quantity' not in df.columns:
            df['Quantity'] = 1
        
        # Add a Selected column
        df['Selected'] = True
        
        return df
        
    except Exception as e:
        logger.error(f"Error reading CSV file: {str(e)}")
        st.error(f"Error reading CSV file: {str(e)}")
        return None

# Zerodha login page
def zerodha_login_page():
    st.header("Step 1: Zerodha API Authentication")
    
    if st.session_state.api_authenticated:
        st.success("You are authenticated with Zerodha!")
        
        # Display account balance
        if st.session_state.account_balance:
            st.subheader("Account Balance")
            for key, value in st.session_state.account_balance.items():
                st.write(f"{key}: ₹{value}")
        
        # Option to retry fetching balance
        if st.button("Refresh Account Balance"):
            account_balance = get_account_balance(st.session_state.kite)
            if account_balance:
                st.session_state.account_balance = account_balance
                st.rerun()
            else:
                st.error("Could not retrieve account balance.")
        
        # Navigation button
        if st.button("Continue to Upload CSV", type="primary"):
            st.session_state.page = "upload_csv"
            st.rerun()
    else:
        st.info("""
        Connect to your Zerodha account using your API credentials.
        If you don't have API credentials, create them in the Zerodha Developer Console.
        """)
        
        # Get stored API credentials
        api_key, api_secret = get_api_credentials(st.session_state.username)
        
        # Check if credentials are saved
        use_saved = False
        if api_key and api_secret:
            use_saved = st.checkbox("Use saved API credentials", value=True)
        
        with st.form("zerodha_auth_form"):
            if use_saved:
                st.write("Using saved API credentials.")
                show_key = st.checkbox("Show API Key")
                if show_key:
                    st.text_input("Zerodha API Key", value=api_key, disabled=True)
            else:
                api_key = st.text_input("Zerodha API Key", value=api_key if api_key else "")
                api_secret = st.text_input("Zerodha API Secret", type="password", value=api_secret if api_secret else "")
                save_creds = st.checkbox("Save credentials for future use", value=True)
            
            # Generate login URL
            if api_key:
                login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
                st.markdown(f"After submitting, click this link to login: [Zerodha Login]({login_url})")
            
            request_token = st.text_input("Request Token (from redirect URL after login)")
            
            submitted = st.form_submit_button("Authenticate")
            
            if submitted and api_key and api_secret and request_token:
                with st.spinner("Authenticating with Zerodha..."):
                    # Save credentials if requested
                    if not use_saved and save_creds:
                        success, message = save_api_credentials(st.session_state.username, api_key, api_secret)
                        if success:
                            st.success("API credentials saved successfully")
                        else:
                            st.warning(f"Could not save API credentials: {message}")
                    
                    kite, access_token = generate_access_token(api_key, api_secret, request_token)
                    
                    if kite and access_token:
                        st.session_state.kite = kite
                        st.session_state.api_authenticated = True
                        
                        # Fetch account balance
                        account_balance = get_account_balance(kite)
                        if account_balance:
                            st.session_state.account_balance = account_balance
                        
                        # Prefetch available instruments for faster symbol lookup
                        try:
                            st.session_state.available_instruments = kite.instruments("NSE")
                            logger.info(f"Successfully fetched {len(st.session_state.available_instruments)} instruments from NSE")
                        except Exception as e:
                            logger.error(f"Error fetching instruments: {str(e)}")
                        
                        st.success("Successfully authenticated with Zerodha!")
                        st.rerun()

# Modified Upload CSV page with manual price entry
def upload_csv_page():
    st.header("Step 2: Upload CSV with Stock Data")
    
    if not st.session_state.api_authenticated:
        st.error("Please authenticate with Zerodha first.")
        if st.button("Go to Zerodha Authentication"):
            st.session_state.page = "zerodha_login"
            st.rerun()
        return
    
    # Add information about Zerodha API permissions
    with st.expander("⚠️ Important: About Zerodha API Permissions"):
        st.warning("""
        ### Zerodha API Permission Issues
        
        If you're seeing "Insufficient permission" errors, your Zerodha API key doesn't have market data permissions.
        
        **Solutions:**
        1. Enter prices manually in the CSV or stock selection page
        2. Upgrade your Zerodha API subscription to include market data access
        3. Contact Zerodha support to enable the necessary permissions for your API key
        
        The tool will still work, but you'll need to provide prices manually for proper calculations.
        """)
    
    st.info("""
    Upload a CSV file containing stock data.
    The CSV must have at least a 'Symbol' column.
    You can also include 'Quantity' and 'Price' columns.
    """)
    
    # Option to manually add stocks
    st.subheader("Add Stock Manually")
    
    with st.form("add_stock_form"):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            stock_symbol = st.text_input("Enter Stock Symbol")
            fetch_details = st.checkbox("Try to fetch stock details from Zerodha", value=True)
        
        with col2:
            manual_price = st.number_input("Manual Price (if fetch fails)", min_value=0.01, value=100.0, step=0.1)
            stock_qty = st.number_input("Quantity", min_value=1, value=1, step=1)
            
        submitted = st.form_submit_button("Add Stock")
        
        if submitted and stock_symbol:
            stock_details = None
            
            if fetch_details and st.session_state.kite:
                stock_details = fetch_stock_details(st.session_state.kite, stock_symbol)
                
                if stock_details:
                    price_info = ""
                    if stock_details['LastPrice'] > 0:
                        st.success(f"Successfully fetched details for {stock_details['Symbol']}")
                        price_info = f"Price: ₹{stock_details['LastPrice']}"
                    else:
                        st.warning(f"Found {stock_details['Symbol']} but could not fetch price data. Using manual price.")
                        stock_details['LastPrice'] = manual_price
                        price_info = f"Price: ₹{manual_price} (manual)"
                    
                    # Display stock details
                    st.write(f"Name: {stock_details['Name']}")
                    st.write(price_info)
                    
                    # Create a dataframe for this stock
                    if st.session_state.stocks_df is None:
                        stock_df = pd.DataFrame({
                            'Symbol': [stock_details['Symbol']],
                            'Name': [stock_details['Name']],
                            'Price': [stock_details['LastPrice']],
                            'Quantity': [stock_qty],
                            'Selected': [True],
                            'FetchedPrice': [stock_details['LastPrice']]
                        })
                        
                        st.session_state.stocks_df = stock_df
                    else:
                        # Check if the stock is already in the dataframe
                        if stock_details['Symbol'] in st.session_state.stocks_df['Symbol'].values:
                            st.warning(f"Stock {stock_details['Symbol']} already exists in your list")
                        else:
                            new_row = pd.DataFrame({
                                'Symbol': [stock_details['Symbol']],
                                'Name': [stock_details['Name']],
                                'Price': [stock_details['LastPrice']],
                                'Quantity': [stock_qty],
                                'Selected': [True],
                                'FetchedPrice': [stock_details['LastPrice']]
                            })
                            
                            st.session_state.stocks_df = pd.concat([st.session_state.stocks_df, new_row], ignore_index=True)
                else:
                    st.error(f"Could not find details for symbol: {stock_symbol}")
                    
                    # Add with manual price
                    if st.session_state.stocks_df is None:
                        stock_df = pd.DataFrame({
                            'Symbol': [stock_symbol.upper()],
                            'Price': [manual_price],
                            'Quantity': [stock_qty],
                            'Selected': [True]
                        })
                        
                        st.session_state.stocks_df = stock_df
                    else:
                        new_row = pd.DataFrame({
                            'Symbol': [stock_symbol.upper()],
                            'Price': [manual_price],
                            'Quantity': [stock_qty],
                            'Selected': [True]
                        })
                        
                        st.session_state.stocks_df = pd.concat([st.session_state.stocks_df, new_row], ignore_index=True)
                    
                    st.success(f"Added {stock_symbol.upper()} with manual price ₹{manual_price}")
            else:
                # Add without fetching details
                if st.session_state.stocks_df is None:
                    stock_df = pd.DataFrame({
                        'Symbol': [stock_symbol.upper()],
                        'Price': [manual_price],
                        'Quantity': [stock_qty],
                        'Selected': [True]
                    })
                    
                    st.session_state.stocks_df = stock_df
                else:
                    # Check if the stock is already in the dataframe
                    if stock_symbol.upper() in st.session_state.stocks_df['Symbol'].values:
                        st.warning(f"Stock {stock_symbol.upper()} already exists in your list")
                    else:
                        new_row = pd.DataFrame({
                            'Symbol': [stock_symbol.upper()],
                            'Price': [manual_price],
                            'Quantity': [stock_qty],
                            'Selected': [True]
                        })
                        
                        st.session_state.stocks_df = pd.concat([st.session_state.stocks_df, new_row], ignore_index=True)
                
                st.success(f"Added {stock_symbol.upper()} with manual price ₹{manual_price}")
    
    st.subheader("Or Upload CSV File")
    
    # Show example CSV format
    with st.expander("See example CSV format"):
        st.code("""Symbol,Price,Quantity
ONGC,180.5,10
RELIANCE,2450,2
TATASTEEL,135.75,15""", language="text")
        
        st.write("You can download this example and modify it:")
        example_df = pd.DataFrame({
            'Symbol': ['ONGC', 'RELIANCE', 'TATASTEEL'],
            'Price': [180.5, 2450, 135.75],
            'Quantity': [10, 2, 15]
        })
        
        csv_data = example_df.to_csv(index=False)
        st.download_button(
            label="Download Example CSV",
            data=csv_data,
            file_name="stock_example.csv",
            mime="text/csv"
        )
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        csv_df = read_csv(uploaded_file)
        
        if csv_df is not None:
            # If we already have stocks, ask if user wants to replace or append
            if st.session_state.stocks_df is not None:
                st.warning("You already have stocks in your list. How would you like to proceed?")
                replace = st.radio("Choose an option:", ["Append new stocks", "Replace existing stocks"])
                
                if replace == "Replace existing stocks":
                    st.session_state.stocks_df = csv_df
                else:
                    # Append, avoiding duplicates
                    existing_symbols = set(st.session_state.stocks_df['Symbol'])
                    new_symbols = [s for s in csv_df['Symbol'] if s not in existing_symbols]
                    
                    if new_symbols:
                        new_df = csv_df[csv_df['Symbol'].isin(new_symbols)]
                        st.session_state.stocks_df = pd.concat([st.session_state.stocks_df, new_df], ignore_index=True)
                        st.info(f"Added {len(new_symbols)} new stocks to your list")
                    else:
                        st.info("No new stocks found in the CSV")
            else:
                st.session_state.stocks_df = csv_df
    
    # Display current stocks
    if st.session_state.stocks_df is not None:
        st.success(f"Your list contains {len(st.session_state.stocks_df)} stocks!")
        
        # Option to fetch details for all stocks
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Try to Fetch Details for All Stocks"):
                if st.session_state.kite:
                    with st.spinner("Fetching stock details from Zerodha..."):
                        # Create a copy of the dataframe
                        updated_df = st.session_state.stocks_df.copy()
                        
                        # Add columns for fetched data if they don't exist
                        if 'Name' not in updated_df.columns:
                            updated_df['Name'] = None
                        if 'FetchedPrice' not in updated_df.columns:
                            updated_df['FetchedPrice'] = None
                        
                        # Fetch details for each stock
                        fetch_progress = st.progress(0)
                        fetch_status = st.empty()
                        fetch_success = 0
                        fetch_failed = 0
                        
                        for i, (idx, row) in enumerate(updated_df.iterrows()):
                            symbol = row['Symbol']
                            fetch_status.text(f"Fetching {i+1} of {len(updated_df)}: {symbol}")
                            fetch_progress.progress((i+1)/len(updated_df))
                            
                            stock_details = fetch_stock_details(st.session_state.kite, symbol)
                            
                            if stock_details:
                                updated_df.at[idx, 'Name'] = stock_details['Name']
                                
                                if stock_details['LastPrice'] > 0:
                                    updated_df.at[idx, 'FetchedPrice'] = stock_details['LastPrice']
                                    
                                    # Update Price column if it's empty or 0
                                    if 'Price' not in updated_df.columns:
                                        updated_df['Price'] = None
                                    
                                    if pd.isna(updated_df.at[idx, 'Price']) or updated_df.at[idx, 'Price'] == 0:
                                        updated_df.at[idx, 'Price'] = stock_details['LastPrice']
                                        fetch_success += 1
                                else:
                                    fetch_failed += 1
                            else:
                                fetch_failed += 1
                            
                            # Sleep to avoid rate limiting
                            time.sleep(0.1)
                        
                        # Update the dataframe
                        st.session_state.stocks_df = updated_df
                        
                        fetch_status.empty()
                        
                        if fetch_success > 0:
                            st.success(f"Successfully fetched prices for {fetch_success} stocks")
                        
                        if fetch_failed > 0:
                            st.warning(f"Could not fetch prices for {fetch_failed} stocks. You'll need to enter prices manually.")
        
        with col2:
            if st.button("Edit Prices Manually"):
                # Create a copy for editing
                if 'Price' not in st.session_state.stocks_df.columns:
                    st.session_state.stocks_df['Price'] = 0
                
                price_df = st.session_state.stocks_df[['Symbol', 'Price']].copy()
                
                # Make it editable
                edited_prices = st.data_editor(
                    price_df,
                    column_config={
                        "Symbol": st.column_config.TextColumn("Symbol", disabled=True),
                        "Price": st.column_config.NumberColumn("Price", min_value=0.01, step=0.05, format="₹%.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Update the main dataframe with edited prices
                if st.button("Save Manual Prices"):
                    for i, row in edited_prices.iterrows():
                        symbol = row['Symbol']
                        price = row['Price']
                        
                        mask = st.session_state.stocks_df['Symbol'] == symbol
                        st.session_state.stocks_df.loc[mask, 'Price'] = price
                    
                    st.success("Prices updated successfully!")
                    st.rerun()
        
        # Display the dataframe
        st.dataframe(st.session_state.stocks_df)
        
        # Show a balance-based allocation button if we have prices
        if 'Price' in st.session_state.stocks_df.columns or 'FetchedPrice' in st.session_state.stocks_df.columns:
            if st.session_state.account_balance and 'Available Cash' in st.session_state.account_balance:
                available_cash = st.session_state.account_balance['Available Cash']
                
                st.subheader("Optimize Quantities Based on Available Balance")
                st.write(f"Available Balance: ₹{available_cash}")
                
                allocation_pct = st.slider("Percentage of available balance to use", 
                                         min_value=10, max_value=100, value=90, step=5)
                
                budget = available_cash * (allocation_pct / 100)
                
                if st.button("Calculate Optimal Quantities"):
                    with st.spinner("Calculating optimal quantities..."):
                        optimized_df, message = calculate_optimal_quantities(
                            st.session_state.stocks_df, 
                            budget
                        )
                        
                        st.session_state.stocks_df = optimized_df
                        st.success(message)
                        st.dataframe(st.session_state.stocks_df)
        
        # Navigation button
        if st.button("Continue to Stock Selection", type="primary"):
            st.session_state.page = "select_stocks"
            st.rerun()

# Select stocks page
def select_stocks_page():
    st.header("Step 3: Select Stocks and Set Quantities")
    
    if not st.session_state.api_authenticated:
        st.error("Please authenticate with Zerodha first.")
        if st.button("Go to Zerodha Authentication"):
            st.session_state.page = "zerodha_login"
            st.rerun()
        return
    
    if st.session_state.stocks_df is None:
        st.error("Please upload a CSV file or add stocks first.")
        if st.button("Go to Upload/Add Stocks"):
            st.session_state.page = "upload_csv"
            st.rerun()
    else:
        # Get a working copy of the dataframe
        working_df = st.session_state.stocks_df.copy()
        
        # Display options in multiple columns
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Stock Selection")
            
            # Option to select/deselect all
            select_all = st.checkbox("Select All", value=True)
            if select_all:
                working_df['Selected'] = True
            else:
                working_df['Selected'] = False
                
            # Display editable dataframe
            edited_df = st.data_editor(
                working_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Selected": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select the stocks you want to trade",
                        default=True,
                    ),
                    "Quantity": st.column_config.NumberColumn(
                        "Quantity",
                        help="Number of shares to buy",
                        min_value=1,
                        step=1,
                        default=1,
                    ),
                    "Symbol": st.column_config.TextColumn(
                        "Symbol",
                        help="Stock symbol",
                        disabled=True,
                    ),
                    "Price": st.column_config.NumberColumn(
                        "Price",
                        help="Current price (read-only)",
                        format="₹%.2f",
                        disabled=True,
                    ) if "Price" in working_df.columns else None,
                    "Name": st.column_config.TextColumn(
                        "Name",
                        help="Stock name",
                        disabled=True,
                    ) if "Name" in working_df.columns else None,
                }
            )
            
            # Update the working dataframe
            working_df = edited_df
        
        with col2:
            st.subheader("Bulk Actions")
            
            # Set default quantity for all
            st.write("Set default quantity for selected stocks:")
            default_qty = st.number_input("Default Quantity", min_value=1, value=1, step=1)
            if st.button("Apply Default Quantity"):
                working_df.loc[working_df['Selected'], 'Quantity'] = default_qty
                st.session_state.stocks_df = working_df
                st.rerun()
            
            # Show a balance-based allocation button if we have prices
            if ('Price' in working_df.columns or 'FetchedPrice' in working_df.columns) and \
               st.session_state.account_balance and 'Available Cash' in st.session_state.account_balance:
                
                st.write("---")
                st.write("Balance-based allocation:")
                
                available_cash = st.session_state.account_balance['Available Cash']
                st.write(f"Available Balance: ₹{available_cash}")
                
                allocation_pct = st.slider("% of balance to use", 
                                         min_value=10, max_value=100, value=90, step=5)
                
                budget = available_cash * (allocation_pct / 100)
                
                if st.button("Calculate Optimal Quantities"):
                    with st.spinner("Calculating optimal quantities..."):
                        # Only consider selected stocks
                        selected_df = working_df[working_df['Selected']].copy()
                        
                        if not selected_df.empty:
                            optimized_df, message = calculate_optimal_quantities(
                                selected_df, 
                                budget
                            )
                            
                            # Update quantities in the main dataframe
                            for i, row in optimized_df.iterrows():
                                idx = working_df.index.get_loc(i)
                                working_df.at[idx, 'Quantity'] = row['Quantity']
                            
                            st.session_state.stocks_df = working_df
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning("No stocks selected for optimization")
            
            # Add a new stock
            st.write("---")
            st.write("Add a new stock:")
            
            new_symbol = st.text_input("Symbol")
            fetch_details = st.checkbox("Fetch details", value=True)
            new_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="new_stock_qty")
            
            if st.button("Add Stock") and new_symbol:
                if fetch_details and st.session_state.kite:
                    stock_details = fetch_stock_details(st.session_state.kite, new_symbol)
                    
                    if stock_details:
                        new_row = pd.DataFrame({
                            'Symbol': [stock_details['Symbol']],
                            'Name': [stock_details['Name']] if 'Name' in working_df.columns else None,
                            'Price': [stock_details['LastPrice']] if 'Price' in working_df.columns else None,
                            'Quantity': [new_qty],
                            'Selected': [True],
                            'FetchedPrice': [stock_details['LastPrice']]
                        })
                        
                        # Drop any None columns
                        new_row = new_row.dropna(axis=1, how='all')
                        
                        # Ensure working_df has the same columns
                        for col in new_row.columns:
                            if col not in working_df.columns:
                                working_df[col] = None
                        
                        working_df = pd.concat([working_df, new_row], ignore_index=True)
                        st.session_state.stocks_df = working_df
                        st.success(f"Added {stock_details['Symbol']} at ₹{stock_details['LastPrice']}")
                        st.rerun()
                    else:
                        st.error(f"Could not find details for symbol: {new_symbol}")
                else:
                    new_row = pd.DataFrame({
                        'Symbol': [new_symbol.upper()],
                        'Quantity': [new_qty],
                        'Selected': [True]
                    })
                    
                    working_df = pd.concat([working_df, new_row], ignore_index=True)
                    st.session_state.stocks_df = working_df
                    st.rerun()
        
        # Save button
        if st.button("Save Selection", type="primary"):
            # Filter to only selected stocks
            selected_stocks = working_df[working_df['Selected']].copy()
            
            if selected_stocks.empty:
                st.error("No stocks selected. Please select at least one stock.")
            else:
                st.session_state.selected_stocks = selected_stocks
                st.session_state.stocks_df = working_df
                st.success(f"Successfully saved {len(selected_stocks)} selected stocks!")
                
                # Display selected stocks
                st.subheader("Selected Stocks")
                st.dataframe(selected_stocks)
                
                # Navigation button
                if st.button("Continue to Review & Order", type="primary"):
                    st.session_state.page = "review_order"
                    st.rerun()

# Review and order page
def review_order_page():
    st.header("Step 4: Review and Place Orders")
    
    if not st.session_state.api_authenticated:
        st.error("Please authenticate with Zerodha first.")
        if st.button("Go to Zerodha Authentication"):
            st.session_state.page = "zerodha_login"
            st.rerun()
        return
    
    if st.session_state.selected_stocks is None or len(st.session_state.selected_stocks) == 0:
        st.error("No stocks selected. Please select stocks first.")
        if st.button("Go to Stock Selection"):
            st.session_state.page = "select_stocks"
            st.rerun()
    else:
        # Display account balance
        if st.session_state.account_balance:
            balance_col1, balance_col2 = st.columns(2)
            with balance_col1:
                st.subheader("Account Balance")
                for key, value in st.session_state.account_balance.items():
                    st.write(f"{key}: ₹{value}")
            
            with balance_col2:
                # Calculate and display total estimated cost
                st.subheader("Estimated Cost")
                try:
                    # Get a working copy
                    price_df = st.session_state.selected_stocks.copy()
                    
                    # If Price column exists, use it
                    if 'Price' in price_df.columns:
                        # Ensure Price is numeric
                        price_df['Price'] = pd.to_numeric(price_df['Price'].astype(str).str.replace(',', ''), errors='coerce')
                    # Try to use FetchedPrice if Price is not available
                    elif 'FetchedPrice' in price_df.columns:
                        price_df['Price'] = price_df['FetchedPrice']
                    else:
                        # Try to fetch prices for all stocks
                        if st.button("Fetch Current Prices"):
                            with st.spinner("Fetching current prices..."):
                                price_df['Price'] = None
                                
                                for i, row in price_df.iterrows():
                                    symbol = row['Symbol']
                                    stock_details = fetch_stock_details(st.session_state.kite, symbol)
                                    
                                    if stock_details and 'LastPrice' in stock_details:
                                        price_df.at[i, 'Price'] = stock_details['LastPrice']
                    
                    # Calculate cost if we have valid prices
                    if 'Price' in price_df.columns:
                        # Calculate cost for each stock
                        price_df['Cost'] = price_df['Price'] * price_df['Quantity']
                        
                        # Sum up the total cost
                        total_cost = price_df['Cost'].sum()
                        
                        st.write(f"Total: ₹{total_cost:.2f}")
                        
                        # Compare with available balance
                        if st.session_state.account_balance and 'Available Cash' in st.session_state.account_balance:
                            available_cash = st.session_state.account_balance['Available Cash']
                            
                            if total_cost > available_cash:
                                st.warning(f"⚠️ Total cost (₹{total_cost:.2f}) exceeds available balance (₹{available_cash:.2f})")
                            else:
                                st.success(f"✅ You have sufficient balance (₹{available_cash:.2f}) for this order (₹{total_cost:.2f})")
                                st.write(f"Remaining balance after order: ₹{available_cash - total_cost:.2f}")
                except Exception as e:
                    st.write("Could not calculate total cost. Please ensure stocks have valid prices.")
                    logger.error(f"Error calculating total cost: {str(e)}")
        
        # Display selected stocks
        st.subheader("Selected Stocks for Order")
        st.dataframe(st.session_state.selected_stocks)
        
        # Order placement options
        st.subheader("Order Placement")
        
        order_type = st.radio("Order Type", ["MARKET", "GTT (Good Till Triggered)"])
        
        if order_type == "GTT (Good Till Triggered)":
            st.info("GTT orders will be placed when the stock reaches your trigger price")
            
            # Create GTT details for all stocks
            gtt_details = {'trigger_price': {}, 'limit_price': {}}
            
            # Display form for GTT parameters
            st.subheader("GTT Parameters")
            
            # Option to set default values for all stocks
            col1, col2 = st.columns(2)
            with col1:
                default_trigger = st.number_input("Default Trigger Price (%)", 
                                                min_value=-10.0, max_value=10.0, value=-2.0, step=0.5,
                                                help="Set trigger price as percentage +/- from current price")
            with col2:
                default_limit = st.number_input("Default Limit Price (%)", 
                                             min_value=-10.0, max_value=10.0, value=-1.0, step=0.5,
                                             help="Set limit price as percentage +/- from current price")
            
            apply_default = st.button("Apply Default Parameters to All Stocks")
            
            # Create inputs for each stock
            for i, row in st.session_state.selected_stocks.iterrows():
                symbol = row['Symbol']
                current_price = 0
                
                # Try to get current price
                if 'Price' in row and pd.notna(row['Price']) and row['Price'] > 0:
                    current_price = row['Price']
                elif 'FetchedPrice' in row and pd.notna(row['FetchedPrice']) and row['FetchedPrice'] > 0:
                    current_price = row['FetchedPrice']
                
                st.write(f"**{symbol}** (Current Price: ₹{current_price if current_price > 0 else 'Unknown'})")
                
                gtt_col1, gtt_col2 = st.columns(2)
                
                # Calculate default values if requested
                if apply_default and current_price > 0:
                    trigger_value = current_price * (1 + default_trigger/100)
                    limit_value = current_price * (1 + default_limit/100)
                else:
                    trigger_value = 0
                    limit_value = 0
                
                with gtt_col1:
                    trigger_price = st.number_input(f"Trigger Price for {symbol}", 
                                                 min_value=0.01, step=0.05, value=float(trigger_value) if trigger_value > 0 else 0.01,
                                                 key=f"trigger_{symbol}")
                    gtt_details['trigger_price'][symbol] = trigger_price
                
                with gtt_col2:
                    limit_price = st.number_input(f"Limit Price for {symbol}", 
                                               min_value=0.01, step=0.05, value=float(limit_value) if limit_value > 0 else 0.01,
                                               key=f"limit_{symbol}")
                    gtt_details['limit_price'][symbol] = limit_price
                
                st.write("---")
        
        is_dry_run = st.checkbox("Dry Run Mode (No actual orders will be placed)", value=True)
        
        if is_dry_run:
            place_button = st.button(f"Place {order_type} Orders (Dry Run)", type="primary")
        else:
            place_button = st.button(f"Place REAL {order_type} Orders", type="primary", use_container_width=True)
        
        # Warning for real orders
        if not is_dry_run:
            st.warning(f"⚠️ You are about to place REAL {order_type} orders on Zerodha! These orders will use real money.")
        
        # Place orders
        if place_button:
            if not is_dry_run:
                confirmation = st.radio(
                    f"Are you absolutely sure you want to place REAL {order_type} orders?",
                    options=["No", f"Yes, I want to place REAL {order_type} orders"],
                    index=0
                )
                
                if confirmation != f"Yes, I want to place REAL {order_type} orders":
                    st.error("Order placement cancelled. Please confirm to proceed with real orders.")
                    place_button = False
            
            if place_button:
                with st.spinner("Processing orders..."):
                    gtt_params = None
                    if order_type == "GTT (Good Till Triggered)":
                        gtt_params = gtt_details
                    
                    successful, failed, orders_df = place_orders(
                        st.session_state.kite, 
                        st.session_state.selected_stocks, 
                        order_type="GTT" if order_type == "GTT (Good Till Triggered)" else "MARKET",
                        dry_run=is_dry_run,
                        gtt_details=gtt_params
                    )
                    
                    st.session_state.orders_result = {
                        "successful": successful,
                        "failed": failed,
                        "orders_df": orders_df,
                        "is_dry_run": is_dry_run,
                        "order_type": order_type,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
        
        # Display results
        if st.session_state.orders_result:
            result = st.session_state.orders_result
            
            st.subheader("Order Results")
            st.write(f"**Time:** {result['timestamp']}")
            st.write(f"**Mode:** {'Dry Run (No actual orders placed)' if result['is_dry_run'] else 'REAL ORDERS'}")
            st.write(f"**Order Type:** {result['order_type']}")
            st.write(f"**Summary:** {result['successful']} successful, {result['failed']} failed")
            
            # Display orders table
            st.dataframe(result['orders_df'])
            
            # Provide download option
            csv_data = result['orders_df'].to_csv(index=False)
            st.download_button(
                label="Download Results as CSV",
                data=csv_data,
                file_name=f"zerodha_orders_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

# Navigation and Main Menu
def main_menu():
    # Sidebar for navigation
    with st.sidebar:
        st.title("Navigation")
        
        # Display logged in user
        st.write(f"Logged in as: **{st.session_state.username}**")
        if st.session_state.admin:
            st.write("(Admin)")
        
        # Admin option
        if st.session_state.admin:
            admin_section = st.sidebar.expander("Admin", expanded=False)
            with admin_section:
                if st.button("Admin Dashboard"):
                    st.session_state.page = "admin"
                    st.rerun()
        
        st.subheader("Trading Tool")
        # Navigation options
        option = st.radio(
            "Steps",
            ["1. Zerodha Login", "2. Upload CSV", "3. Select Stocks", "4. Review & Order", "User Profile"]
        )
        
        if option == "1. Zerodha Login":
            st.session_state.page = "zerodha_login"
        elif option == "2. Upload CSV":
            st.session_state.page = "upload_csv"
        elif option == "3. Select Stocks":
            st.session_state.page = "select_stocks"
        elif option == "4. Review & Order":
            st.session_state.page = "review_order"
        elif option == "User Profile":
            st.session_state.page = "profile"
        
        # Logout button
        if st.button("Logout"):
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            # Reinitialize session state
            init_session_state()
            st.rerun()
        
        # Show status
        st.write("---")
        st.subheader("Status")
        
        if st.session_state.api_authenticated:
            st.success("✅ Zerodha Authenticated")
        else:
            st.warning("⚠️ Not Authenticated")
            
        if st.session_state.stocks_df is not None:
            st.success("✅ CSV Uploaded")
        else:
            st.warning("⚠️ CSV Not Uploaded")
            
        if st.session_state.selected_stocks is not None:
            st.success(f"✅ {len(st.session_state.selected_stocks)} Stocks Selected")
        else:
            st.warning("⚠️ No Stocks Selected")

# Main app flow
def main():
    # Initialize user database if it doesn't exist
    initialize_user_db()
    
    # Check authentication
    if not st.session_state.authenticated:
        login()
    else:
        # If we haven't set a page, default to zerodha_login
        if 'page' not in st.session_state:
            st.session_state.page = "zerodha_login"
        
        # Display the main menu in the sidebar
        main_menu()
        
        # Display the appropriate page based on navigation
        if st.session_state.page == "admin" and st.session_state.admin:
            admin_dashboard()
        elif st.session_state.page == "zerodha_login":
            zerodha_login_page()
        elif st.session_state.page == "upload_csv":
            upload_csv_page()
        elif st.session_state.page == "select_stocks":
            select_stocks_page()
        elif st.session_state.page == "review_order":
            review_order_page()
        elif st.session_state.page == "profile":
            user_profile_page()

# Run the app
if __name__ == "__main__":
    main()