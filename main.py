import logging
from telegram import Chat, ChatMember, ChatMemberUpdated, Update,InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,ChatMemberHandler,CallbackQueryHandler,ConversationHandler,MessageHandler,filters
import re
from web3 import Web3
import requests
import time
import mysql.connector
from mysql.connector import Error
import asyncio
from decimal import Decimal, getcontext
import threading
import json
## ================================ db ========================##

# db_config = {
#     'user': 'root',
#     'password': 'Testimonyalade@2003',
#     'host': 'localhost',
#     'database': 'telegram_bot',
# }


db_config = {
    'user': 'root',
    'password': 'Str0ng!Passw0rd',
    'host': '154.12.231.59',
    'database': 'christianity_db',
}
stop_events = {}

# 'CREATE DATABASE christianity_db; '

def create_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None


def create_tables():
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Create `group_numbers` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_numbers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    group_id BIGINT NOT NULL,
                    number INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_group (group_id)
                )
            """)

            # Create `media` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_id VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_chat (chat_id)
                )
            """)

            # Create `emojis` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emojis (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    emoji VARCHAR(50) NOT NULL,
                    chat_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_chat (chat_id)
                )
            """)

            # Create `chat_info` table with UNIQUE constraint on `chat_id`
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_info (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    token_address VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pair_address VARCHAR(255),
                    blockchain VARCHAR(50),
                    UNIQUE KEY unique_chat (chat_id)
                )
            """)

            # Create `solana_price` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS solana_price (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    price DECIMAL(18, 8) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)

            # Create `token_market_cap` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `token_market_cap` (
                    `token_address` varchar(255) NOT NULL,
                    `market_cap` decimal(20,2) DEFAULT NULL,
                    `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (`token_address`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """)

            # Create `welcome_settings` table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `welcome_settings` (
                    `id` int NOT NULL AUTO_INCREMENT,
                    `chat_id` bigint NOT NULL,
                    `welcome_users` varchar(255) DEFAULT 'false',
                    `del_old_welcomes` varchar(255) DEFAULT 'false',
                    `del_serve_msg` varchar(255) DEFAULT 'false',
                    `msg_content` varchar(255) DEFAULT 'Hey there {first}, and welcome to {chatname}! How are you?',
                    `file_id` varchar(255) DEFAULT NULL,
                    `file_type` enum('image','video','gif','sticker') DEFAULT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `chat_id` (`chat_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
            """)

            conn.commit()
            print("All tables created successfully or already exist.")
        except Error as e:
            print(f"Error: {e}")
        finally:
            cursor.close()
            conn.close()
def update_welcome_setting(chat_id, setting_name, value):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Check if the chat_id exists
        cursor.execute("SELECT * FROM welcome_settings WHERE chat_id = %s", (chat_id,))
        result = cursor.fetchone()
        
        if result:
            # Update the specific setting
            query = f"UPDATE welcome_settings SET {setting_name} = %s WHERE chat_id = %s"
            cursor.execute(query, (value, chat_id))
        else:
            # Insert new record with the setting on
            query = f"""
                INSERT INTO welcome_settings (chat_id, {setting_name})
                VALUES (%s, %s)
            """
            cursor.execute(query, (chat_id, value))
        
        conn.commit()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()
def read_user_settings(chat_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Query to fetch the settings for the given chat_id
        query = "SELECT * FROM welcome_settings WHERE chat_id = %s"
        cursor.execute(query, (chat_id,))
        result = cursor.fetchone()
        
        if result:
            print(f"Settings for chat_id {chat_id}:")
            welcome_users = result.get('welcome_users', 'Not Found')
            del_old_welcomes = result.get('del_old_welcomes', 'Not Found')
            del_serve_msg = result.get('del_serve_msg', 'Not Found')
            msg_content = result.get('msg_content', 'Not Found')
        
            return welcome_users , del_old_welcomes,del_serve_msg,msg_content
            
        else:
            print(f"No settings found for chat_id {chat_id}.")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

def save_media(chat_id: int, file_id: str, file_type: str):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        # Validate file_type
        valid_file_types = {'image', 'video', 'gif', 'sticker'}
        if file_type not in valid_file_types:
            raise ValueError("Invalid file_type. Must be one of: 'image', 'video', 'gif', 'sticker'.")

        # Insert or update the file_id and file_type in the welcome_settings table
        cursor.execute("""
            INSERT INTO welcome_settings (chat_id, file_id, file_type)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            file_id = VALUES(file_id),
            file_type = VALUES(file_type)
        """, (chat_id, file_id, file_type))

        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except ValueError as ve:
        print(f"Value Error: {ve}")
    finally:
        cursor.close()
        conn.close()

def clear_media(chat_id: int):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        # Update the file_id and file_type to NULL for the given chat_id
        cursor.execute("""
            UPDATE welcome_settings
            SET file_id = NULL,
                file_type = NULL
            WHERE chat_id = %s
        """, (chat_id,))

        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

def fetch_media(chat_id: int):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Fetch the file_id and file_type for the given chat_id
        cursor.execute("""
            SELECT file_id, file_type
            FROM welcome_settings
            WHERE chat_id = %s
        """, (chat_id,))
        
        result = cursor.fetchone()
        
        if result:
            file_id, file_type = result
            return file_id, file_type
        else:
            return None, None
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def insert_new_group(chat_id):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO welcome_settings (chat_id)
            VALUES (%s)
        """
        cursor.execute(query, (chat_id,))
        conn.commit()

        print(f"New group with chat_id {chat_id} inserted successfully.")

    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
            print(f"Group with chat_id {chat_id} already exists.")
        else:
            print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

def check_group_exists(group_id):
    try:
        for_connect = create_connection()
        # Establish a database connection
        if for_connect.is_connected():
            print("Connected to the database")

            cursor = for_connect.cursor()

            # Define the SQL command to check if the group exists
            check_query = """
            SELECT COUNT(*)
            FROM chat_info
            WHERE chat_id = %s;
            """
            # Execute the SQL command
            cursor.execute(check_query, (group_id,))

            # Fetch the result
            result = cursor.fetchone()
            count = result[0]

            if count > 0:
                return 'good'
            else:
                return 'bad'
    except Error as e:
        print(f"Error: {e}")
    finally:
        if for_connect.is_connected():
            cursor.close()
            for_connect.close()

def fetch_token_address(group_id):
    try:
        # Establish a database connection
        connection = create_connection()
        if connection.is_connected():
            print("Connected to the database")

            cursor = connection.cursor()

            # Define the SQL command to fetch the token address
            fetch_query = """
            SELECT token_address
            FROM chat_info
            WHERE chat_id = %s;
            """

            # Execute the SQL command
            cursor.execute(fetch_query, (group_id,))

            # Fetch the result
            result = cursor.fetchone()

            if result:
                token_address = result[0]
                return token_address
            else:
                return 'No token yet'

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def insert_user(telegram_id, given_address, pair_address, blockchain):
    try:
        # Connect to the database
        to_connect = create_connection()

        if to_connect.is_connected():
            print("Connected to the database")

            cursor = to_connect.cursor()

            # Define the SQL command to insert a record
            insert_query = """
            INSERT INTO chat_info (chat_id, token_address, pair_address, blockchain)
            VALUES (%s, %s, %s, %s);
            """

            # Execute the SQL command
            cursor.execute(insert_query, (telegram_id, given_address, pair_address, blockchain))

            # Commit the transaction
            to_connect.commit()
            print("User data inserted successfully.")

    except Error as e:
        print(f"Error: {e}")
    finally:
        if to_connect.is_connected():
            cursor.close()
            to_connect.close()

def retrieve_group_number(group_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT number FROM group_numbers WHERE group_id = %s", (group_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def get_emoji_from_db(chat_id: int) -> str:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT emoji FROM emojis
        WHERE chat_id = %s
    """, (chat_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return result[0]
    return None

def fetch_pair_address_and_blockchain_for_group(chat_id):
    try:
        # Connect to the database
        to_connect = create_connection()

        if to_connect.is_connected():
            print("Connected to the database")

            cursor = to_connect.cursor()

            # Define the SQL query to retrieve pair_address and blockchain for a specific chat_id
            select_query = "SELECT pair_address, blockchain FROM chat_info WHERE chat_id = %s"

            # Execute the query with the chat_id parameter
            cursor.execute(select_query, (chat_id,))

            # Fetch all rows from the result of the query
            results = cursor.fetchall()

            # Check if any results were found
            if results:
                # Process and print the results
                for row in results:
                    pair_address = row[0]
                    blockchain = row[1]
                    return pair_address,blockchain
            else:
                return None
    except Error as e:
        print(f"Error: {e}")
    finally:
        if to_connect.is_connected():
            cursor.close()
            to_connect.close()
            print("Database connection closed.")

def save_emoji_to_db(emoji: str, chat_id: int) -> None:
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emojis (emoji, chat_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            emoji = VALUES(emoji),
            created_at = CURRENT_TIMESTAMP
        """, (emoji, chat_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(e)

def save_or_update_media_in_db(file_id: str, file_type: str, chat_id: int):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO media (file_id, file_type, chat_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        file_id = VALUES(file_id),
        file_type = VALUES(file_type),
        created_at = CURRENT_TIMESTAMP
    """, (file_id, file_type, chat_id))
    conn.commit()
    cursor.close()
    conn.close()

def download_file(file_url):
    response = requests.get(file_url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception("Failed to download file")

def save_or_update_group_buy_number(group_id, number):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO group_numbers (group_id, number)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
        number = VALUES(number)
    """, (group_id, number))
    conn.commit()
    cursor.close()
    conn.close()

def fetch_media_from_db(chat_id: int):
    conn =create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type FROM media WHERE chat_id = %s ORDER BY created_at DESC LIMIT 1", (chat_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def chat_id_exists(chat_id):
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM chat_info WHERE chat_id = %s", (chat_id,))
            result = cursor.fetchone()
            return result is not None
        except Error as e:
            print(f"Error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def special_format(number):
    if number == 0:
        return "0"
    # Set precision high enough to capture small numbers accurately
    getcontext().prec = 50
    number = Decimal(str(number))
    # Handle very small decimals with more than 5 leading zeros
    if 0 < number < Decimal('0.0001'):
        return "⬇️0.0001"
    # Handle other small decimals with fewer than 4 leading zeros
    if 0 < number < 1:
        return f"{number:.4f}".rstrip('0').rstrip('.')
    # Handle larger numbers with suffixes
    abs_number = abs(number)
    if abs_number >= 1_000_000_000:
        formatted = f"{number / 1_000_000_000:.1f}B"
    elif abs_number >= 1_000_000:
        formatted = f"{number / 1_000_000:.0f}M"
    elif abs_number >= 1_000:
        formatted = f"{number:,.0f}"
    else:
        formatted = f"{number:.4f}".rstrip('0').rstrip('.')
    return formatted

def format_number_with_commas(number):
    return "{:,}".format(int(number))


def delete_chat_id(chat_id):
    try:
        # Establish the connection
        to_delete = create_connection()

        if to_delete.is_connected():
            cursor = to_delete.cursor()

            # SQL query to delete a row by chat_id
            sql_delete_query = """DELETE FROM chat_info WHERE chat_id = %s"""
            cursor.execute(sql_delete_query, (chat_id,))
            # Commit the transaction
            to_delete.commit()
            print(f"Row with chat_id = {chat_id} deleted successfully.")
        else:
            print('didnt happen')
    except Error as e:
        print(f"Error: {e}")

    finally:
        if to_delete.is_connected():
            cursor.close()
            to_delete.close()

def save_market_cap_to_db(token_address, market_cap):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Check if the token address already exists in the database
        cursor.execute("SELECT token_address FROM token_market_cap WHERE token_address = %s", (token_address,))
        result = cursor.fetchone()
        
        if result:
            # Update existing market cap
            cursor.execute("""
                UPDATE token_market_cap
                SET market_cap = %s, updated_at = NOW()
                WHERE token_address = %s
            """, (market_cap, token_address))
            print(f"Updated market cap for {token_address}: ${market_cap:,.2f}")
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO token_market_cap (token_address, market_cap)
                VALUES (%s, %s)
            """, (token_address, market_cap))
            print(f"Inserted new market cap for {token_address}: ${market_cap:,.2f}")
        
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error interacting with MySQL: {e}")

def fetch_market_cap_from_db(token_address):
    try:
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Query the market cap for the given token address
        query = "SELECT market_cap FROM token_market_cap WHERE token_address = %s"
        cursor.execute(query, (token_address,))
        
        # Fetch the result
        result = cursor.fetchone()
        
        # Check if result is found
        if result:
            market_cap = result[0]
            print(f"Market Cap for token {token_address}: ${market_cap:,.2f}")
            return market_cap
        else:
            print(f"No market cap data found for token address: {token_address}")
            return None
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error fetching market cap from database: {e}")
        return None
### ================ utils =============================##

def get_token_market_data(token_address):
    url = f"https://api.dexscreener.io/latest/dex/tokens/{token_address}"
    
    try:
        response = requests.get(url)
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching token data: {e}")
        return None

def get_market_cap_from_dexscreener(token_address):
    # Get token market data from Dexscreener
    data = get_token_market_data(token_address)
    
    if not data or 'pairs' not in data:
        print("Token data not found.")
        return None

    # Dexscreener provides data for different trading pairs, so we'll use the first one
    first_pair = data['pairs'][0]
    
    # Extract market cap if available
    market_cap = first_pair.get('fdv')  # FDV is Fully Diluted Valuation (approx. market cap)
    
    if market_cap:
        print(f"Market Cap for token {token_address}: ${market_cap:,.2f}")
    else:
        print("Market Cap not available for this token.") 
    return market_cap


def update_mkt_cap():
    while True:
        token_address = 'X2h2pyb81yWFw6fFCF864F9sYYs3d7us4ZHBq2pFSnf'
        price = get_market_cap_from_dexscreener(token_address)
        save_market_cap_to_db(token_address,price)
        time.sleep(120)  # Wait for 2 minutes
        print(price)

def start_price_updater_thread():
    thread = threading.Thread(target=update_mkt_cap)
    thread.daemon = True  # Daemonize thread to stop it when the main program exits
    thread.start()

api_count = 0
class AxiosInstance:
    def __init__(self, base_url):
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json'
        })
        self.base_url = base_url
        # self.proxies = random.choice(proxies_list)  # Add support for proxies
    def get(self, endpoint):
        try:
            response = self.session.get(self.base_url + endpoint)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {self.base_url + endpoint}:\n", e)
            return False
axios_instance = AxiosInstance("https://api.geckoterminal.com/api/v2/")

def api_limit_wait():
    time.sleep(1)  # Adjust the sleep time according to your API rate limits
def solana_get_token(address):
    global api_count
    api_count += 1
    api_limit_wait()
    return axios_instance.get(f"networks/solana/tokens/{address}/info")
def solana_get_token_pools(address, page="1"):
    global api_count
    api_count += 1
    api_limit_wait()
    return axios_instance.get(f"networks/solana/tokens/{address}/pools?page={page}")

FOR_SOL,SEND_MEDIA =range(2)

async def fetch_data(url):
    return requests.get(url).json()
logged_signatures = set()  # Set to store logged signatures

### function ==============================================####

async def dexes(pool_address,token_address, context, chat_id,name,symbol,stop_event):
    try:
        prev_resp =None
        page="1"
        while not stop_event.is_set():
            get_token_url = f'https://api.geckoterminal.com/api/v2/networks/solana/tokens/{pool_address}/info'
            get_pools_url = f'https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_address}/pools?page={page}'
            get_last_pools_url = f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/trades'
            print('dex is live')
            last_trades = await fetch_data(get_last_pools_url)
            token_pools = await fetch_data(get_pools_url)
            if last_trades and 'data' in last_trades:
                for trade in reversed(last_trades['data'][:7]):
                    signature = trade['attributes']['tx_hash']
                    swap_kind = trade['attributes']['kind']
                    the_signer = trade['attributes']['tx_from_address']
                    # If this signature hasn't been logged yet
                    if signature not in logged_signatures:
                        logged_signatures.add(signature)
                        if swap_kind != 'sell':
                            chart = f"<a href='https://dexscreener.com/solana/{pool_address}'>Chart</a>"
                            trend_url = f"https://t.me/BSCTRENDING/5431871"
                            trend = f"<a href='{trend_url}'>Trending</a>"
                            thenew_signer = f"{the_signer[:7]}...{the_signer[-4:]}"
                            sign = f"<a href='https://solscan.io/account/{the_signer}'>{thenew_signer}</a>"
                            txn = f"<a href='https://solscan.io/tx/{signature}'>TXN</a>"
                            sol_amount = trade['attributes']['from_token_amount']
                            token_amount = trade['attributes']['to_token_amount']
                            usd_value_bought = float(trade['attributes']['volume_in_usd'])
                            try:
                                mkt_cap = fetch_market_cap_from_db(token_address)
                            except Exception as e:
                                mkt_cap ='N/A'
                            emoji = get_emoji_from_db(chat_id)
                            buy_step_number = retrieve_group_number(chat_id)
                            # print(fdv)
                            if buy_step_number == None:
                                buuy = 10
                            else:
                                buuy = buy_step_number
                            # print(buuy)
                            calc = (usd_value_bought/buuy)
                            calc = int(calc)
                            # print(calc)
                            if chat_id_exists(chat_id):
                                if emoji:
                                    message = (
                                        f"<b> ✅{name}</b> Buy!\n\n"
                                        f"{emoji*calc}\n"
                                        f"💵 {special_format(sol_amount)} <b>SOL</b>\n"
                                        f"🪙{special_format(token_amount)} <b>{symbol}</b>\n"
                                        f"👤{sign}|{txn}\n"
                                        f"🔷${special_format(int(usd_value_bought))}\n"
                                        f"🧢MKT Cap : ${format_number_with_commas(mkt_cap)}\n\n"
                                        f"🦎{chart} 🔷{trend}"
                                    )
                                else:
                                    message = (
                                        f"<b> ✅{name}</b> Buy!\n\n"
                                        f"{'✝️⚔️ '*calc}\n"
                                        f"💵 {special_format(sol_amount)} <b>SOL</b>\n"
                                        f"🪙{special_format(token_amount)} <b>{symbol}</b>\n"
                                        f"👤{sign}|{txn}\n"
                                        f"🔷${special_format(int(usd_value_bought))}\n"
                                        f"🧢MKT Cap : ${format_number_with_commas(mkt_cap)}\n\n"
                                        f"🦎{chart} 🔷{trend}"
                                    )
                        
                            if message:
                                try:
                                    media = fetch_media_from_db(chat_id)
                                    if media:
                                        # print(message)
                                        file_id, file_type = media
                                        if file_type == 'photo':
                                            asyncio.run_coroutine_threadsafe(
                                                context.bot.send_photo(chat_id=chat_id, photo=file_id,caption=message,parse_mode='HTML'),
                                                asyncio.get_event_loop()
                                            )
                                        elif file_type == 'gif':
                                            asyncio.run_coroutine_threadsafe(
                                                context.bot.send_document(chat_id=chat_id, document=file_id,caption = message,parse_mode='HTML'),
                                                asyncio.get_event_loop()
                                            )
                                        else:
                                            print('idont know')
                                    else:
                                        # print("No media found in the database for this group.")
                                        # print(message)
                                        asyncio.run_coroutine_threadsafe(
                                            context.bot.send_message(chat_id=chat_id, text=message,parse_mode='HTML',disable_web_page_preview=True),
                                            asyncio.get_event_loop()
                                        )
                                        # await context.bot.send_message(chat_id=chat_id, text=message,parse_mode='HTML',disable_web_page_preview=True)

                                except Exception as e:
                                    print(e)
                    prev_resp = signature
                    await asyncio.sleep(2)
            else:
                print("Failed to retrieve last pool trades.")   
            await asyncio.sleep(1)  # Adjust the interval as needed

    except Exception as e:
        print(e)

def start_dexes(pool_address,token_address,context, chat_id, name, symbol):
    if chat_id not in stop_events:
        stop_events[chat_id] = asyncio.Event()
    stop_event = stop_events[chat_id]
    stop_event.clear()
    def run_dex_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            dexes(pool_address,token_address, context, chat_id, name, symbol, stop_event)
        )
    # Start the thread
    thread = threading.Thread(target=run_dex_in_thread)
    thread.start()

### ===================== bot =================================##

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.my_chat_member.new_chat_member.status == 'member':
        chat_id = update.my_chat_member.chat.id
        group_name = update.my_chat_member.chat.title
        logger.info(f"Bot added to group '{group_name}' (Chat ID: {chat_id})")
        welcome_message = (
        "🤝 Welcome, Believer! 🤝\n\n"
        "Thank you for connecting with the official $CHRIST Coin bot! 🌟\n\n"
        "Whether you’re here to learn about the coin, check the latest updates, or just explore our mission of faith and unity in the crypto space, you’re in the right place. 🙏\n\n"
        "Type /start to begin your journey!"
    )

        keyboard = [
        [InlineKeyboardButton("Open Help", url="https://t.me/Christianity_Coin_bot?start=help_")]
    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try: 
            insert_new_group(chat_id)
            await context.bot.send_message(chat_id=chat_id, text=welcome_message,reply_markup=reply_markup,parse_mode='HTML')
        except Exception as e:
            print('an error',{e})

async def start(update:Update,context : ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    welcome_message = (
        "🤝 Welcome, Believer! 🤝\n\n"
        "Thank you for connecting with the official $CHRIST Coin bot! 🌟\n\n"
        "Whether you’re here to learn about the coin, check the latest updates, or just explore our mission of faith and unity in the crypto space, you’re in the right place. 🙏\n\n"
        "Type /start to begin your journey!"
    )
    keyboard = [
            [InlineKeyboardButton("Add me to your chat!", url="https://t.me/Christianity_Coin_bot?startgroup=botstart")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_photo(chat_id=user_id, photo=open('christ.jpg', 'rb'),caption=welcome_message,parse_mode='HTML',reply_markup=reply_markup)
async def is_user_admin(update:Update,context:ContextTypes.DEFAULT_TYPE):
    ## check if usser is admin
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    admins = await context.bot.get_chat_administrators(chat_id)
    return any(admin.user.id == user_id for admin in admins)

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get the argument from the command (if any)
        chat_type:str = update.message.chat.type
        print(chat_type)
        chat_id = update.effective_chat.id
        original_message_id = update.message.message_id 
        if chat_type =='group' or chat_type == 'supergroup':
            if not await is_user_admin(update , context):
                await update.message.reply_text("You're not authorized to use this bot")
            else:
                bot_chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if bot_chat_member.status == "administrator":
                    args = context.args
                    # Check if there's an argument and handle it
                    if args:
                        arg = args[0].lower()

                        if arg in ["on", "yes", "true"]:
                            # Logic to turn on the welcome feature
                            setting_name = 'welcome_users'
                            new_value =  'true'
                            update_welcome_setting(chat_id,setting_name,new_value)
                            await update.message.reply_text("I'll be Welcoming all new memebers to the group from now on!")
                        elif arg in ["off", "no", "false"]:
                            # Logic to turn off the welcome feature
                            setting_name = 'welcome_users'
                            new_value =  'false'
                            update_welcome_setting(chat_id,setting_name,new_value)
                            await update.message.reply_text("I'll stay quiet when new members join the group.")
                        else:
                            # Handle unrecognized arguments
                            await update.message.reply_text("Invalid argument! Please use 'on', 'off', 'yes', 'no', 'true', or 'false'.")
                    else:
                        # Default behavior when no argument is provided
                        try:
                            welcome_users , del_old_welcomes,del_serve_msg,msg_content =  read_user_settings(chat_id)
                            message = (
                                f'''
                    I am currently welcoming users:<b> {welcome_users}</b>
I am currently deleting old welcomes: <b>{del_old_welcomes}</b>
I am currently deleting service messages: <b>{del_serve_msg}</b>
Members are currently welcomed with: \n<b>{msg_content}</b>'''
                            )

                            await update.message.reply_text(message,parse_mode='HTML')
                        except Exception as e:
                            print(f'error {e}')

                else:
                    await update.message.reply_text("I need to be admin to welcome users in this chat. Please make me admin first.")

    except Exception as e:
        print(f'something didnt work out because of {e}')

async def new_user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for new_member in update.message.new_chat_members:
        if not new_member.is_bot:
            chat_id = update.message.chat.id
            group_name = update.message.chat.title
            logger.info(f"New user '{new_member.full_name}' (User ID: {new_member.id}) joined group '{group_name}' (Chat ID: {chat_id})")
            # welcome_user_message = f"Welcome {new_member.full_name} to {group_name}!"
            try:
                welcome_users , del_old_welcomes,del_serve_msg,msg_content = read_user_settings(chat_id)
                if welcome_users == 'true':
                    if fetch_media(chat_id):
                        file_id,file_type =fetch_media(chat_id)
                        message = msg_content
                        message = msg_content.format(first=new_member.first_name , chatname=group_name)
                        if file_type == 'image':
                            sent_message = await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=message, parse_mode='HTML')
                        elif file_type == 'video':
                            sent_message = await context.bot.send_video(chat_id=chat_id, video=file_id, caption=message, parse_mode='HTML')
                        elif file_type == 'sticker':
                            sent_message = await context.bot.send_sticker(chat_id=chat_id, sticker=file_id)
                        elif file_type == 'gif':
                            sent_message = await context.bot.send_animation(chat_id=chat_id, animation=file_id, caption=message, parse_mode='HTML')
                        else:
                            welcome_user_message = msg_content.format(first=new_member.first_name, chatname=group_name)
                            sent_message = await context.bot.send_message(chat_id=chat_id, text=welcome_user_message, parse_mode='HTML')
                    else:
                        welcome_user_message = msg_content.format(first=new_member.first_name, chatname=group_name)
                        sent_message = await context.bot.send_message(chat_id=chat_id, text=welcome_user_message, parse_mode='HTML')
                    if sent_message:
                        await asyncio.sleep(3)
                        try:
                            await context.bot.delete_message(chat_id=sent_message.chat_id, message_id=sent_message.message_id)
                        except Exception as delete_error:
                            logger.error(f"Failed to delete welcome message: {delete_error}")
                else:
                    None
            except Exception as e:
                logger.error(f"Failed to send welcome message to {new_member.full_name}: {e}")
                print('database not accessible')   

async def setwelcome_media(update:Update , context:ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        message =update.message
        if message.reply_to_message:
            if message.reply_to_message.photo:
                file_id = message.reply_to_message.photo[-1].file_id
                media_type = 'photo'
                save_media(chat_id, file_id, 'image')
                await update.message.reply_text("The new welcome message has been saved!")
            elif message.reply_to_message.video:
                # Handle video
                file_id = message.reply_to_message.video.file_id
                media_type = 'video'
                save_media(chat_id, file_id, 'video')
                await update.message.reply_text("The new welcome message has been saved!")
            elif message.reply_to_message.sticker:
                # Handle sticker
                file_id = message.reply_to_message.sticker.file_id
                media_type = 'sticker'
                save_media(chat_id, file_id, 'sticker')
                await update.message.reply_text("The new welcome message has been saved!")
            elif message.reply_to_message.text:
                replied_message = message.reply_to_message.text
                setting_name = 'msg_content'
                new_value =  replied_message
                update_welcome_setting(chat_id,setting_name,new_value)
                await update.message.reply_text("The new welcome message has been saved!")
                print('it is text')
            elif message.reply_to_message.animation:
                file_id = message.reply_to_message.animation.file_id
                media_type = 'gif'
                save_media(chat_id, file_id, 'gif')
                await update.message.reply_text("The new welcome message has been saved!")
            else:
                # If there's no supported media, return
                await context.bot.send_message(chat_id=chat_id, text="Please reply to a valid media message (photo, video, or sticker).")
                print('not foto')
    except Exception as e:
        print('setiing welcome error',e,'happened')

async def setwelcome(update:Update ,context:ContextTypes.DEFAULT_TYPE):
    try:
        message =update.message
        chat_type:str = update.message.chat.type
        print(chat_type)
        chat_id = update.effective_chat.id
        original_message_id = update.message.message_id 
        if chat_type =='group' or chat_type == 'supergroup':
            if not await is_user_admin(update , context):
                await update.message.reply_text("You're not authorized to use this bot")
            else:
                bot_chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if bot_chat_member.status == "administrator":
                    args = context.args
                    if args and not message.reply_to_message:
                        # print(args)
                        content = ' '.join(args)
                        setting_name = 'msg_content'
                        new_value =  content
                        update_welcome_setting(chat_id,setting_name,new_value)
                        clear_media(chat_id)
                        await update.message.reply_text("The new welcome message has been saved!")
                    elif message.reply_to_message:
                        await setwelcome_media(update , context)
                        if args:
                            content = ' '.join(args)
                            setting_name = 'msg_content'
                            new_value =  content
                            update_welcome_setting(chat_id,setting_name,new_value)
                            print('saved but with args')
                        else:
                            if message.reply_to_message.text:
                                setting_name = 'msg_content'
                                new_value =  message.reply_to_message.text
                                update_welcome_setting(chat_id,setting_name,new_value)
                            else:
                                setting_name = 'msg_content'
                                new_value =  ''
                                update_welcome_setting(chat_id,setting_name,new_value)
                    else:
                        await update.message.reply_text("You need to give the welcome message some content!")
                else:
                    await update.message.reply_text("I need to be admin to welcome users in this chat. Please make me admin first.")  
    except Exception as e:
        print('an error',e)

async def reset_welcome(update:Update,context:ContextTypes.DEFAULT_TYPE):
    message =update.message
    chat_type:str = update.message.chat.type
    print(chat_type)
    chat_id = update.effective_chat.id
    original_message_id = update.message.message_id 
    if chat_type =='group' or chat_type == 'supergroup':
        if not await is_user_admin(update , context):
            await update.message.reply_text("You're not authorized to use this bot")
        else:
            bot_chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_chat_member.status == "administrator":
                setting_name = 'msg_content'
                new_value =  (
                "🌟 Welcome, {first}! 🌟\n\n"
                "You've joined the {chatname} community!\n\n"
                "We are spreading faith, hope, and positivity through crypto. 🙏\n"
                "Feel free to ask questions, share thoughts, and be part of this mission. "
                "Let’s grow together!"
            )
                
                update_welcome_setting(chat_id,setting_name,new_value)
                clear_media(chat_id)
                await update.message.reply_text("The welcome message has been reset to default!")
            else:
                await update.message.reply_text("I need to be admin to welcome users in this chat. Please make me admin first.")

async def add(update:Update , context:ContextTypes.DEFAULT_TYPE):
    chat_type:str = update.message.chat.type
    print(chat_type)
    original_message_id = update.message.message_id 
    if chat_type =='group' or chat_type == 'supergroup':
        chat_id = update.effective_chat.id
        if not await is_user_admin(update , context):
            await update.message.reply_text("You're not authorized to use this bot")
        else:
            bot_chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_chat_member.status == "administrator":
                text = f'''
<B>✝️⚔️Christianity Coin Bot</b>
Choose a Chain ⛓️'''
                keyboard = [
                [InlineKeyboardButton("⚡Solana Chain ($CHRIST)", callback_data='sol')],
            ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(text=text, reply_markup=reply_markup,parse_mode='HTML'),

            else:
                await update.message.reply_text("❗️Ineed administrator permission to proceed. Please make me an admin!")
    else:
        await update.message.reply_text("This Command is only accessible on the group")

async def add_query(update:Update , context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    original_message_id = query.message.message_id
    await query.answer()
    if query.data == "sol":
        await query.edit_message_text(text="➡[✝️ CHRIST] Token address?")
        context.user_data['state'] = FOR_SOL

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_type: str = update.message.chat.type
    if chat_type == 'group' or chat_type == 'supergroup':
        btn2= InlineKeyboardButton("✝️ Christianity Coin Bot Settings", callback_data='buybot_settings')
        btn9= InlineKeyboardButton("🔴 Close menu", callback_data='close_menu')
        row2= [btn2]
        row9= [btn9]
        reply_markup_pair = InlineKeyboardMarkup([row2,row9])
        await update.message.reply_text(
            '🛠 Settings Menu:',
            reply_markup=reply_markup_pair
        )
    else:
        await update.message.reply_text("This Command is only accessible in the group")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    original_message_id = query.message.message_id

    await query.answer()
    if query.data == 'buybot_settings':
        buy_number = retrieve_group_number(chat_id)
        print(buy_number)
        if buy_number == None:
            buy_number_use = 10
        else:
            buy_number_use = buy_number
         
        emoji = get_emoji_from_db(chat_id)
        if emoji:
            emoji_use = emoji
        else:
            emoji_use = '✝️'
        try:
            pair_adress,blockchain =fetch_pair_address_and_blockchain_for_group(chat_id)
        except Exception as e:
            blockchain = ''
            pair_adress= ''
        btn1=InlineKeyboardButton("📊 Gif / Image: 🔴", callback_data='gif_video')
        btn2=InlineKeyboardButton(f"{emoji_use} Buy Emoji", callback_data='buy_emoji') 
        btn4=InlineKeyboardButton(f"💲 Buy Step: ${buy_number_use}", callback_data='buy_step') 
        btn9=InlineKeyboardButton("📉 Chart: DexScreener", callback_data='chart_dexscreener',url=f'https://dexscreener.com/solana/5qtdxmzcl4xfedxmbjlqiib8fvuqxqgcxyknopzb28q6')
        btn11=InlineKeyboardButton("🔙 Back To Group Settings", callback_data='back_group_settings')

        text ='''
<b>✝️⚔️Christianity Coin Bot</b>

⚙Settings'''
        row1=[btn1]
        row2=[btn2,btn4]
        row6=[btn9]
        row8=[btn11]
        reply_markup_pair = InlineKeyboardMarkup([row1,row2,row6,row8])
        await query.edit_message_text(text, reply_markup=reply_markup_pair,parse_mode='HTML')
    elif query.data == 'close_menu':
        await query.edit_message_reply_markup(reply_markup=None)

async def another_query(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = SEND_MEDIA
    if context.user_data['state'] == SEND_MEDIA:
        query = update.callback_query
        chat_id = query.message.chat_id
        original_message_id = query.message.message_id
        if query.data == 'gif_video':
            context.user_data['state'] = SEND_MEDIA
            context.user_data['awaiting_media'] = True
            await query.edit_message_text(text="Send me a image/gif")
        elif query.data == 'buy_emoji':
            print('you cicked emoji')
            await query.edit_message_text(text="Please send emoji")
            context.user_data['awaiting_emoji'] = True
        elif query.data == 'buy_step':
            print('here')
            await query.edit_message_text(text="Send me a number for your buy step")
            context.user_data['awaiting_number'] = True
        elif query.data == 'back_group_settings':
            btn2= InlineKeyboardButton("🟢 BuyBot Settings", callback_data='buybot_settings')
            btn9= InlineKeyboardButton("🔴 Close menu", callback_data='close_menu')
            row2= [btn2]
            row9= [btn9]
            reply_markup_pair = InlineKeyboardMarkup([row2,row9])
            await query.edit_message_reply_markup(reply_markup=reply_markup_pair)

async def handle_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    chat_id = update.effective_chat.id
    if user_data.get('awaiting_emoji'):
        emoji = update.message.text
        print(type(emoji))
        if emoji:
            save_emoji_to_db(emoji, chat_id)
            await update.message.reply_text(f'Emoji {emoji} saved to database.')
            user_data['awaiting_emoji'] = False
        else:
            await update.message.reply_text('Please send a valid emoji.')
    else:
        await update.message.reply_text('Send /setemoji to start the emoji process.')

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo or update.message.animation or update.message.text.startswith("http"):
        user_data = context.user_data
        if user_data.get('awaiting_media'):
            message = update.message
            chat_id = update.effective_chat.id
            try:
                if context.user_data['state'] == SEND_MEDIA:
                    if message.photo:
                        file_id = message.photo[-1].file_id
                        save_or_update_media_in_db(file_id, 'photo', chat_id)
                        await message.reply_text("Photo receivedgg and saved.")
                        context.user_data.clear()
                        user_data['awaiting_media'] = False
                    elif message.animation:
                        file_id = message.document.file_id
                        save_or_update_media_in_db(file_id, 'gif', chat_id)
                        await message.reply_text("GIF received and saved.")
                        context.user_data.clear()
                        user_data['awaiting_media'] = False
                    else:
                        context.user_data.clear()
                        user_data['awaiting_media'] = False
            except Exception as e:
               print('An error occured please type /settings to send media')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    message_text = update.message.text
    if context.user_data.get('awaiting_emoji'):
        emoji = update.message.text
        if emoji:
            save_emoji_to_db(emoji, update.effective_chat.id)
            await update.message.reply_text(f'Emoji {emoji} saved to database.')
            context.user_data['awaiting_emoji'] = False
        else:
            await update.message.reply_text('Please send a valid emoji.')
    elif context.user_data.get('awaiting_number'):
        try:
            buy_step_number = update.message.text
            if int(buy_step_number) < 10 :
                await update.message.reply_text('Buy Step should not be less than 10.')
            else:
                save_or_update_group_buy_number(chat_id,buy_step_number)
                await update.message.reply_text('Buy Step saved.')
                context.user_data['awaiting_number'] = False
        except Exception as e:
            print(e)
            await update.message.reply_text('An Error Occured please try again')
            context.user_data['awaiting_number'] = False
    elif update.message.text and update.message.text.startswith("http"):
            file_url = update.message.text
            if file_url.endswith(".gif"):
                try:
                    gif_file = download_file(file_url)
                    response = await context.bot.send_document(chat_id=chat_id, document=gif_file)
                    file_id = response.document.file_id
                    save_or_update_media_in_db(file_id, 'gif', chat_id)
                    await update.message.reply_text("GIF received from the link and saved.")
                except Exception as e:
                    await update.message.reply_text(f"Failed to process the link: {e}")
            else:
                await update.message.reply_text("Please provide a valid GIF link.")
    else:
        if 'state' in context.user_data:
            if context.user_data['state'] == FOR_SOL:
                context.user_data['message'] = message_text 
                try:
                    sol_address = context.user_data['message']
                    token_info = solana_get_token(sol_address)
                    sol_check= check_group_exists(chat_id)
                    if  sol_check == 'good':
                        sol_db_token = fetch_token_address(chat_id)
                        print('user already exist')
                        await context.bot.send_message(chat_id=chat_id, text=f'❗️Bot already in use in this group for token {sol_db_token}',parse_mode='HTML',disable_web_page_preview=True)

                    else:
                        deep_down = token_info['data']['attributes']
                        if deep_down:
                            name = deep_down['name']
                            symbol = deep_down['symbol']
                            decimal = deep_down['decimals']
                            sol_done=insert_user(chat_id, sol_address,'','solana')
                            # sol_db_token = fetch_token_address(chat_id)
                            sol_respnse = (
                                        f"✝️⚔️Christianity Coin Bot is now tracking\n"
                                        f"📈:{sol_address}\n"
                                        f"✅NAME : {name}\n"
                                        f"🔣SYMBOL : {symbol}\n"
                                    )
                            await context.bot.send_message(chat_id=chat_id, text=sol_respnse,parse_mode='HTML',disable_web_page_preview=True)
                            btn2= InlineKeyboardButton("🟢 BuyBot Settings", callback_data='buybot_settings')
                            btn9= InlineKeyboardButton("🔴 Close menu", callback_data='close_menu')

                            row2= [btn2]
                            row9= [btn9]
                            reply_markup_pair = InlineKeyboardMarkup([row2,row9])
                            await update.message.reply_text(
                                '🛠 Settings Menu:',
                                reply_markup=reply_markup_pair
                            )

                            token_pools = solana_get_token_pools(sol_address, page="1")
                            if token_pools:
                                # print("Token Pools:", token_pools)
                                pair_address = token_pools['data'][0]['attributes']['address']
                                print(pair_address)

                                start_dexes(pair_address,sol_address,context,chat_id,name,symbol)
                                context.user_data.clear()

                            else:
                                print("Failed to retrieve token pools.")
                                context.user_data.clear()
                except Exception as e:
                    print(e)
                    await context.bot.send_message(chat_id=chat_id, text='An Error Occured / Invalid Token address type /add to add a different pair address',parse_mode='HTML',disable_web_page_preview=True)
                    context.user_data.clear()

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in stop_events:
        stop_events[chat_id].set() 
        print('stopped')
    else:
        print('fuck')
    chat_type: str = update.message.chat.type
    if chat_type == 'group' or chat_type == 'supergroup':
        chat_id = update.effective_chat.id
        if not await is_user_admin(update, context):
            await update.message.reply_text("You're not authorized to use this bot")
        else:   
            bot_chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_chat_member.status == "administrator":
                group_token = fetch_token_address(chat_id)
                # Ask for confirmation
                text = f"Are you sure you want to remove token : {group_token}?"
                keyboard = [
                    [InlineKeyboardButton("✅Yes", callback_data='confirm_remove')],
                    [InlineKeyboardButton("❌No", callback_data='cancel_remove')],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                asyncio.run_coroutine_threadsafe(
                    update.message.reply_text(text=text, reply_markup=reply_markup),
                    asyncio.get_event_loop()
                            )
            else:
                await update.message.reply_text("❗️I need administrator permission to proceed. Please make me an admin!")
    else:
        await update.message.reply_text("This Command is only accessible in the group")

async def done_too(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    if query.data == 'confirm_remove':
        print(chat_id)
        chat_id_to_delete = chat_id
        delete_chat_id(chat_id_to_delete) # Replace with actual token name
        await query.edit_message_text(text="Token has been removed successfully.")

    elif query.data == 'cancel_remove':
        await query.edit_message_text(text="Token removal has been cancelled.")

    else:
        print('didnt get that')

TOKEN_KEY_ = '7755481707:AAFcYVDbT4vRQuCnoB_EGHkJlrGw-EqmTZA'
def main():
    start_price_updater_thread()
    app = ApplicationBuilder().token(TOKEN_KEY_).build()
    create_tables()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("welcome", welcome))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("resetwelcome", reset_welcome))
    app.add_handler(CommandHandler('settings', settings))
    app.add_handler(CommandHandler('remove', remove))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_user_joined))
    app.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(done_too,pattern='^(confirm_remove|cancel_remove)$'))
    app.add_handler(CallbackQueryHandler(another_query,pattern='^(gif_video|buy_emoji|buy_step|back_group_settings)$'))
    app.add_handler(CallbackQueryHandler(add_query,pattern='^(sol)$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.ANIMATION, handle_media))
    app.add_handler(CallbackQueryHandler(button,pattern='^(buybot_settings|close_menu)$'))

    app.run_polling()
if __name__ == '__main__':
    main()



