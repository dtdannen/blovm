#!/usr/bin/env python3
"""
Example of running a BlobDVM server
"""
import asyncio
import sys
from nostr_sdk import Keys, init_logger, LogLevel
from src.blobdvm import BlobDVMServer
from loguru import logger

# Initialize nostr logging
init_logger(LogLevel.INFO)

async def main():
    # Generate server keys (in production, use a persistent key)
    keys = Keys.generate()
    print(f"Server public key: {keys.public_key().to_hex()}")
    print(f"Server nsec: {keys.secret_key().to_bech32()}")
    print(f"\nSave this key to reuse the same server identity!")
    
    # Configure relays
    relays = [
        "wss://relay.damus.io",
        "wss://nos.lol",
        "wss://relay.nostr.band"
    ]
    
    # Create and start server
    server = BlobDVMServer(keys.secret_key().to_hex(), relays)
    
    print(f"\nStarting BlobDVM server...")
    print(f"Connecting to relays: {', '.join(relays)}")
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        await server.stop()
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())