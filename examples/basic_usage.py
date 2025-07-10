#!/usr/bin/env python3
"""
Basic usage example for BlobDVM
"""
import asyncio
import sys
from nostr_sdk import Keys, init_logger, LogLevel
from src.blobdvm import BlobDVMClient

# Initialize nostr logging
init_logger(LogLevel.INFO)

async def main():
    # Generate keys (or use your own)
    keys = Keys.generate()
    print(f"Using temporary key: {keys.secret_key().to_bech32()}")
    
    # Create client
    relays = ["wss://relay.damus.io", "wss://nos.lol"]
    client = BlobDVMClient(keys.secret_key().to_hex(), relays)
    
    # Connect
    await client.start()
    
    # Discover servers
    print("\nDiscovering BlobDVM servers...")
    servers = await client.discover_servers()
    
    if not servers:
        print("No servers found. Make sure a server is running.")
        return
        
    print(f"Found {len(servers)} server(s)")
    for server in servers:
        print(f"  - {server['pubkey'][:8]}...")
        print(f"    Name: {server['tags'].get('name', 'Unknown')}")
        
    # Example: Upload a file
    # print("\nUpload example:")
    # result = await client.upload_file("test.txt")
    # print(f"File uploaded! Hash: {result['hash']}")
    
    # Example: Download a file
    # print("\nDownload example:")
    # data = await client.download_file(result['hash'], "downloaded.txt")
    # print(f"File downloaded! Size: {len(data)} bytes")

if __name__ == "__main__":
    asyncio.run(main())