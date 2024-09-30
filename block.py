import requests
import time
from datetime import datetime
import re
import networkx as nx
import matplotlib.pyplot as plt
import streamlit as st

# Etherscan API configuration
ETH_API_KEY = "AD1C72JWVGD6M4V4QUQRWNYN2IAP6JS6YR"
ETH_BASE_URL = "https://api.etherscan.io/api"

# Blockchain.com Base URL for Bitcoin
BTC_BASE_URL = "https://blockchain.info"

# Rate limit settings
REQUEST_DELAY = 1  # seconds

# Ethereum functions
def is_valid_transaction_hash_eth(tx_hash):
    return isinstance(tx_hash, str) and re.match(r'^0x[a-fA-F0-9]{64}$', tx_hash) is not None

def get_transaction_details_eth(tx_hash):
    if not is_valid_transaction_hash_eth(tx_hash):
        st.error(f"Invalid Ethereum transaction hash format: {tx_hash}")
        return None

    params = {
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": ETH_API_KEY
    }
    try:
        response = requests.get(ETH_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "result" in data:
            return data["result"]
        else:
            st.error("Unexpected API response structure.")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching transaction details: {e}")
        return None

def get_block_timestamp(block_number):
    params = {
        "module": "block",
        "action": "getblockreward",
        "blockno": block_number,
        "apikey": ETH_API_KEY
    }
    try:
        response = requests.get(ETH_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] == "1":
            return int(data["result"]["timeStamp"])
        else:
            st.error("Failed to retrieve block timestamp.")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching block timestamp: {e}")
        return None

def get_outgoing_transactions(address, start_timestamp, end_block=99999999):
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": end_block,
        "sort": "asc",
        "apikey": ETH_API_KEY
    }
    try:
        response = requests.get(ETH_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] == "1":
            return [tx for tx in data["result"] if int(tx['timeStamp']) > start_timestamp and tx['from'].lower() == address.lower()]
        else:
            st.error("Failed to retrieve transactions.")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching transactions: {e}")
        return []

def get_token_transfers(address, start_timestamp, end_block=99999999):
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": end_block,
        "sort": "asc",
        "apikey": ETH_API_KEY
    }
    try:
        response = requests.get(ETH_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] == "1":
            return [tx for tx in data["result"] if int(tx['timeStamp']) > start_timestamp and tx['from'].lower() == address.lower()]
        else:
            st.error("Failed to retrieve token transfers.")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching token transfers: {e}")
        return []

def visualize_transactions(outgoing_transactions, token_transfers, start_address):
    G = nx.DiGraph()

    # Add nodes and edges for outgoing Ether transactions
    for tx in outgoing_transactions:
        G.add_edge(start_address, tx['to'], label=f"{float(tx['value']) / 1e18:.6f} ETH")
    
    # Add nodes and edges for outgoing token transfers
    for tx in token_transfers:
        token_value = float(tx['value']) / (10 ** int(tx['tokenDecimal']))
        G.add_edge(start_address, tx['to'], label=f"{token_value:.6f} {tx['tokenSymbol']}")

    # Drawing the graph
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G)

    # Draw nodes and edges
    nx.draw(G, pos, with_labels=False, node_color="lightblue", node_size=3000, font_size=10, font_weight="bold", arrows=True)

    # Draw edge labels
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    plt.title("Ethereum Transaction Flow")
    
    # Show the graph (using Streamlit for web apps)
    st.pyplot(plt)

# Bitcoin functions
def is_valid_transaction_hash_btc(tx_hash):
    return isinstance(tx_hash, str) and len(tx_hash) == 64

def get_transaction_details_btc(tx_hash):
    if not is_valid_transaction_hash_btc(tx_hash):
        st.error(f"Invalid Bitcoin transaction hash format: {tx_hash}")
        return None
    
    url = f"{BTC_BASE_URL}/rawtx/{tx_hash}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching transaction details: {e}")
        return None

def get_address_transactions(address):
    url = f"{BTC_BASE_URL}/rawaddr/{address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["txs"]
    except requests.exceptions.RequestException as e:
        if e.response.status_code == 429:
            st.error("Too many requests. Please try again later.")
        else:
            st.error(f"An error occurred while fetching address transactions: {e}")
        return []

def visualize_transaction_tree(transaction_tree):
    G = nx.DiGraph()

    # Add nodes and edges from the tree
    for node, children in transaction_tree.items():
        for child in children:
            G.add_edge(node, child)

    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=3000, font_size=10, font_weight='bold')
    plt.title("Bitcoin Transaction Tree")
    st.pyplot(plt)

def build_transaction_tree(tx_hash, depth=1):
    tx_details = get_transaction_details_btc(tx_hash)
    if not tx_details:
        st.error("Transaction details not found.")
        return {}

    transaction_tree = {}
    
    # Collect all receiver addresses
    output_addresses = [output['addr'] for output in tx_details['out'] if 'addr' in output]
    
    # Root transaction node
    transaction_tree[tx_hash] = output_addresses

    if depth > 0:
        for address in output_addresses:
            outgoing_transactions = get_address_transactions(address)
            time.sleep(REQUEST_DELAY)  # Rate limiting
            for tx in outgoing_transactions:
                child_tx = tx['hash']
                child_tree = build_transaction_tree(child_tx, depth-1)
                transaction_tree.update(child_tree)

    return transaction_tree

# Main application
def main():
    st.title("Blockchain Transaction Visualizer")

    option = st.selectbox("Select blockchain:", ["Ethereum", "Bitcoin"])
    
    if option == "Ethereum":
        tx_hash = st.text_input("Enter a valid Ethereum transaction hash (should start with '0x' and be 66 characters long): ")
        
        if tx_hash:
            tx_details = get_transaction_details_eth(tx_hash)
            if tx_details:
                block_number = int(tx_details['blockNumber'], 16)
                timestamp = get_block_timestamp(block_number)
                
                if timestamp:
                    st.write(f"Original transaction timestamp: {datetime.fromtimestamp(timestamp)}")
                    
                    receiver_address = tx_details['to']
                    st.write(f"Original receiver (R1) address: {receiver_address}")
                    
                    outgoing_transactions = get_outgoing_transactions(receiver_address, timestamp)
                    token_transfers = get_token_transfers(receiver_address, timestamp)
                    
                    st.write(f"Number of outgoing Ether transactions from R1 after the original timestamp: {len(outgoing_transactions)}")
                    st.write(f"Number of outgoing token transfers from R1 after the original timestamp: {len(token_transfers)}")
                    
                    # Visualize the transaction flow
                    visualize_transactions(outgoing_transactions, token_transfers, receiver_address)
                else:
                    st.error("Failed to retrieve block timestamp.")
            else:
                st.error("Failed to retrieve transaction details.")

    elif option == "Bitcoin":
        tx_hash = st.text_input("Enter a valid Bitcoin transaction hash (should be 64 characters long): ")
        
        if tx_hash:
            depth = st.number_input("Enter the depth level (e.g., 1, 2): ", min_value=1, max_value=5, value=1)
            transaction_tree = build_transaction_tree(tx_hash, depth)

            if transaction_tree:
                st.write("Transaction tree built successfully!")
                visualize_transaction_tree(transaction_tree)
            else:
                st.error("Failed to build the transaction tree.")

if __name__ == "__main__":
    main()