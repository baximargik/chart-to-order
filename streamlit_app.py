import streamlit as st
import pandas as pd
import time
import logging
import datetime
import json
import io
from kiteconnect import KiteConnect

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

# App title and description
st.title("Zerodha Trading Tool")
st.markdown("""
This app helps you place orders on Zerodha based on a list of stocks from a CSV file.
Follow the steps below to select stocks, set quantities, and place orders.
""")

# Initialize session state variables if they don't exist
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

# Sidebar for navigation
with st.sidebar:
    st.header("Navigation")
    step = st.radio(
        "Steps",
        ["1. Upload CSV", "2. Select Stocks", "3. Zerodha Login", "4. Review & Order"],
        index=0
    )
    
    # Add a reset button
    if st.button("Reset App"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    # Show status
    st.write("---")
    st.subheader("Status")
    
    if st.session_state.stocks_df is not None:
        st.success("✅ CSV Uploaded")
    else:
        st.warning("⚠️ CSV Not Uploaded")
        
    if st.session_state.selected_stocks is not None:
        st.success(f"✅ {len(st.session_state.selected_stocks)} Stocks Selected")
    else:
        st.warning("⚠️ No Stocks Selected")
        
    if st.session_state.api_authenticated:
        st.success("✅ Zerodha Authenticated")
    else:
        st.warning("⚠️ Not Authenticated")

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

# Function to place orders
def place_orders(kite, stocks_df, dry_run=True):
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
                logger.info(f"[DRY RUN] Would place order for {quantity} shares of {symbol}")
                order_id = f"dry-run-{successful_orders+1}"
                successful_orders += 1
            else:
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
                
                logger.info(f"Successfully placed order for {quantity} shares of {symbol}, Order ID: {order_id}")
                successful_orders += 1
            
            # Get price from the row if available
            price = row['Price'] if 'Price' in row else 'N/A'
            if price != 'N/A':
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
                'Estimated Cost': estimated_cost
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
                'Estimated Cost': 'N/A'
            })
    
    # Create a DataFrame with order information
    orders_df = pd.DataFrame(orders_info)
    logger.info(f"Order summary: {successful_orders} successful, {failed_orders} failed")
    
    return successful_orders, failed_orders, orders_df

# STEP 1: Upload CSV
if step == "1. Upload CSV":
    st.header("Step 1: Upload CSV with Stock Data")
    
    st.info("""
    Upload a CSV file containing stock data.
    The CSV must have at least a 'Symbol' column.
    You can also include 'Quantity' and 'Price' columns.
    """)
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        st.session_state.stocks_df = read_csv(uploaded_file)
        
        if st.session_state.stocks_df is not None:
            st.success(f"Successfully loaded {len(st.session_state.stocks_df)} stocks!")
            st.dataframe(st.session_state.stocks_df)
            
            # Add navigation button
            st.button("Continue to Stock Selection", type="primary")

# STEP 2: Select Stocks
elif step == "2. Select Stocks":
    st.header("Step 2: Select Stocks and Set Quantities")
    
    if st.session_state.stocks_df is None:
        st.error("Please upload a CSV file first.")
        if st.button("Go to CSV Upload"):
            st.session_state.step = "1. Upload CSV"
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
            
            # Add a new stock
            st.write("Add a new stock:")
            new_symbol = st.text_input("Symbol")
            new_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="new_stock_qty")
            if st.button("Add Stock") and new_symbol:
                new_row = pd.DataFrame({
                    'Symbol': [new_symbol],
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

# STEP 3: Zerodha Login
elif step == "3. Zerodha Login":
    st.header("Step 3: Zerodha API Authentication")
    
    if st.session_state.selected_stocks is None:
        st.error("Please select stocks first.")
        if st.button("Go to Stock Selection"):
            st.session_state.step = "2. Select Stocks"
            st.rerun()
    else:
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
            
            st.button("Continue to Review & Order", type="primary")
        else:
            st.info("""
            Connect to your Zerodha account using your API credentials.
            If you don't have API credentials, create them in the Zerodha Developer Console.
            """)
            
            with st.form("zerodha_auth_form"):
                api_key = st.text_input("Zerodha API Key")
                api_secret = st.text_input("Zerodha API Secret", type="password")
                
                # Generate login URL
                if api_key:
                    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
                    st.markdown(f"After submitting, click this link to login: [Zerodha Login]({login_url})")
                
                request_token = st.text_input("Request Token (from redirect URL after login)")
                
                submitted = st.form_submit_button("Authenticate")
                
                if submitted and api_key and api_secret and request_token:
                    with st.spinner("Authenticating with Zerodha..."):
                        kite, access_token = generate_access_token(api_key, api_secret, request_token)
                        
                        if kite and access_token:
                            st.session_state.kite = kite
                            st.session_state.api_authenticated = True
                            
                            # Fetch account balance
                            account_balance = get_account_balance(kite)
                            if account_balance:
                                st.session_state.account_balance = account_balance
                            
                            st.success("Successfully authenticated with Zerodha!")
                            st.rerun()

# STEP 4: Review & Order
elif step == "4. Review & Order":
    st.header("Step 4: Review and Place Orders")
    
    if not st.session_state.api_authenticated:
        st.error("Please authenticate with Zerodha first.")
        if st.button("Go to Zerodha Login"):
            st.session_state.step = "3. Zerodha Login"
            st.rerun()
    elif st.session_state.selected_stocks is None or len(st.session_state.selected_stocks) == 0:
        st.error("No stocks selected. Please select stocks first.")
        if st.button("Go to Stock Selection"):
            st.session_state.step = "2. Select Stocks"
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
                if 'Price' in st.session_state.selected_stocks.columns:
                    st.subheader("Estimated Cost")
                    try:
                        # Ensure Price is numeric
                        price_df = st.session_state.selected_stocks.copy()
                        price_df['Price'] = pd.to_numeric(price_df['Price'].astype(str).str.replace(',', ''), errors='coerce')
                        
                        # Calculate cost for each stock
                        price_df['Cost'] = price_df['Price'] * price_df['Quantity']
                        
                        # Sum up the total cost
                        total_cost = price_df['Cost'].sum()
                        
                        st.write(f"Total: ₹{total_cost:.2f}")
                    except Exception as e:
                        st.write("Could not calculate total cost.")
        
        # Display selected stocks
        st.subheader("Selected Stocks for Order")
        st.dataframe(st.session_state.selected_stocks)
        
        # Order placement options
        st.subheader("Order Placement")
        
        col1, col2 = st.columns(2)
        
        with col1:
            is_dry_run = st.checkbox("Dry Run Mode (No actual orders will be placed)", value=True)
        
        with col2:
            if is_dry_run:
                place_button = st.button("Place Orders (Dry Run)", type="primary")
            else:
                place_button = st.button("Place REAL Orders", type="primary", use_container_width=True)
        
        # Warning for real orders
        if not is_dry_run:
            st.warning("⚠️ You are about to place REAL orders on Zerodha! These orders will use real money.")
        
        # Place orders
        if place_button:
            if not is_dry_run:
                confirmation = st.radio(
                    "Are you absolutely sure you want to place REAL orders?",
                    options=["No", "Yes, I want to place REAL orders"],
                    index=0
                )
                
                if confirmation != "Yes, I want to place REAL orders":
                    st.error("Order placement cancelled. Please confirm to proceed with real orders.")
                    place_button = False
            
            if place_button:
                with st.spinner("Processing orders..."):
                    successful, failed, orders_df = place_orders(
                        st.session_state.kite, 
                        st.session_state.selected_stocks, 
                        dry_run=is_dry_run
                    )
                    
                    st.session_state.orders_result = {
                        "successful": successful,
                        "failed": failed,
                        "orders_df": orders_df,
                        "is_dry_run": is_dry_run,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
        
        # Display results
        if st.session_state.orders_result:
            result = st.session_state.orders_result
            
            st.subheader("Order Results")
            st.write(f"**Time:** {result['timestamp']}")
            st.write(f"**Mode:** {'Dry Run (No actual orders placed)' if result['is_dry_run'] else 'REAL ORDERS'}")
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