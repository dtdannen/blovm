#!/usr/bin/env python3
import click
import asyncio
import os
from nostr_sdk import Keys, init_logger, LogLevel
from blobdvm import BlobDVMClient, BlobDVMServer
from loguru import logger

# Initialize nostr logging
init_logger(LogLevel.INFO)

@click.group()
def cli():
    """BlobDVM CLI - Decentralized file storage over nostr"""
    pass

@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--server', help='Specific server pubkey')
@click.option('--relays', multiple=True, default=['wss://relay.damus.io'])
@click.option('--private-key', envvar='BLOBDVM_PRIVATE_KEY', help='Private key (nsec or hex)')
def upload(file_path, server, relays, private_key):
    """Upload a file to BlobDVM storage"""
    async def _upload():
        # Generate or parse keys
        if private_key:
            keys = Keys.parse(private_key)
        else:
            keys = Keys.generate()
            click.echo(f"Generated temporary key: {keys.secret_key().to_bech32()}")
        
        client = BlobDVMClient(keys.secret_key().to_hex(), list(relays))
        await client.start()
        
        try:
            click.echo(f"Uploading {file_path}...")
            result = await client.upload_file(file_path, server)
            click.echo(f"✓ File uploaded successfully!")
            click.echo(f"  Hash: {result['hash']}")
            click.echo(f"  Size: {result['size']} bytes")
            click.echo(f"  Chunks: {result['chunks']}")
            click.echo(f"  Expires: {result['expires']} (unix timestamp)")
        except Exception as e:
            click.echo(f"✗ Upload failed: {e}", err=True)
            
    asyncio.run(_upload())

@cli.command()
@click.argument('file_hash')
@click.option('--output', '-o', help='Output file path')
@click.option('--relays', multiple=True, default=['wss://relay.damus.io'])
@click.option('--private-key', envvar='BLOBDVM_PRIVATE_KEY', help='Private key (nsec or hex)')
def download(file_hash, output, relays, private_key):
    """Download a file by hash"""
    async def _download():
        # Generate or parse keys
        if private_key:
            keys = Keys.parse(private_key)
        else:
            keys = Keys.generate()
        
        client = BlobDVMClient(keys.secret_key().to_hex(), list(relays))
        await client.start()
        
        try:
            click.echo(f"Downloading {file_hash}...")
            data = await client.download_file(file_hash, output)
            
            if output:
                click.echo(f"✓ Downloaded to {output} ({len(data)} bytes)")
            else:
                click.echo(f"✓ Downloaded {len(data)} bytes")
                
        except Exception as e:
            click.echo(f"✗ Download failed: {e}", err=True)
            
    asyncio.run(_download())

@cli.command()
@click.argument('file_hash')
@click.option('--server', help='Specific server pubkey')
@click.option('--relays', multiple=True, default=['wss://relay.damus.io'])
@click.option('--private-key', envvar='BLOBDVM_PRIVATE_KEY', help='Private key (nsec or hex)')
def delete(file_hash, server, relays, private_key):
    """Delete a file by hash"""
    async def _delete():
        # Generate or parse keys
        if private_key:
            keys = Keys.parse(private_key)
        else:
            keys = Keys.generate()
        
        client = BlobDVMClient(keys.secret_key().to_hex(), list(relays))
        await client.start()
        
        try:
            click.echo(f"Deleting {file_hash}...")
            result = await client.delete_file(file_hash, server)
            click.echo(f"✓ File deleted successfully!")
            
        except Exception as e:
            click.echo(f"✗ Delete failed: {e}", err=True)
            
    asyncio.run(_delete())

@cli.command()
@click.option('--relays', multiple=True, default=['wss://relay.damus.io'])
def list_servers(relays):
    """List available BlobDVM servers"""
    async def _list():
        keys = Keys.generate()
        client = BlobDVMClient(keys.secret_key().to_hex(), list(relays))
        await client.start()
        
        try:
            click.echo("Discovering BlobDVM servers...")
            servers = await client.discover_servers()
            
            if not servers:
                click.echo("No servers found")
                return
                
            click.echo(f"\nFound {len(servers)} server(s):\n")
            
            for server in servers:
                click.echo(f"Server: {server['pubkey']}")
                tags = server['tags']
                
                if 'name' in tags:
                    click.echo(f"  Name: {tags['name']}")
                if 'about' in tags:
                    click.echo(f"  About: {tags['about']}")
                if 'max_file_size' in tags:
                    size_mb = int(tags['max_file_size']) / (1024 * 1024)
                    click.echo(f"  Max file size: {size_mb:.1f} MB")
                if 'chunk_size' in tags:
                    size_kb = int(tags['chunk_size']) / 1024
                    click.echo(f"  Chunk size: {size_kb:.0f} KB")
                if 'retention_hours' in tags:
                    click.echo(f"  Retention: {tags['retention_hours']} hours")
                    
                click.echo()
                
        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)
            
    asyncio.run(_list())

@cli.command()
@click.option('--private-key', required=True, help='Server private key (nsec or hex)')
@click.option('--relays', multiple=True, default=['wss://relay.damus.io'])
@click.option('--data-dir', default='./blobdvm-data', help='Directory for stored files')
def serve(private_key, relays, data_dir):
    """Run a BlobDVM server"""
    async def _serve():
        # Parse server keys
        keys = Keys.parse(private_key)
        click.echo(f"Starting BlobDVM server with pubkey: {keys.public_key().to_hex()}")
        
        server = BlobDVMServer(keys.secret_key().to_hex(), list(relays))
        
        try:
            click.echo(f"Connecting to relays: {', '.join(relays)}")
            await server.start()
        except KeyboardInterrupt:
            click.echo("\nShutting down server...")
            await server.stop()
        except Exception as e:
            click.echo(f"✗ Server error: {e}", err=True)
            
    asyncio.run(_serve())

if __name__ == '__main__':
    cli()