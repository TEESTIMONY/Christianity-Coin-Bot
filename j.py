import requests

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

# Replace with your token's Solana mint address
token_address = "X2h2pyb81yWFw6fFCF864F9sYYs3d7us4ZHBq2pFSnf"  # Replace with actual token mint address

# Fetch and display the market cap
get_market_cap_from_dexscreener(token_address)


