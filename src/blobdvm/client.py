import os
import asyncio
import json
import base64
import hashlib
from typing import List, Dict, Optional
from loguru import logger
from nostr_sdk import (
    Keys, Client, Filter, HandleNotification, Timestamp,
    Kind, Event, EventBuilder, Tag, RelayMessage
)
from .chunker import FileChunker
from .constants import (
    DVM_ANNOUNCEMENT_KIND, REQUEST_KIND, RESPONSE_KIND,
    CHUNK_KIND, STATUS_KIND
)

class BlobDVMClient:
    def __init__(self, private_key_hex: str, relays: List[str]):
        self.keys = Keys.parse(private_key_hex)
        self.client = Client(self.keys)
        self.relays = relays
        self.chunker = FileChunker()
        self.response_events = {}  # request_id -> response_event
        self.chunk_events = {}  # file_hash -> list of chunk events
        
    async def start(self):
        """Initialize client connection"""
        for relay in self.relays:
            await self.client.add_relay(relay)
        await self.client.connect()
        logger.info("Client connected to relays")
        
    async def discover_servers(self) -> List[Dict]:
        """Query relays for BlobDVM announcements"""
        filter = Filter().kinds([Kind(DVM_ANNOUNCEMENT_KIND)]).tag(
            'k', [str(REQUEST_KIND)]
        ).limit(50)
        
        events = await self.client.get_events_of([filter])
        servers = []
        
        for event in events:
            try:
                content = json.loads(event.content())
                tags_dict = {}
                for tag in event.tags():
                    tag_vec = tag.as_vec()
                    if len(tag_vec) >= 2:
                        tags_dict[tag_vec[0]] = tag_vec[1] if len(tag_vec) == 2 else tag_vec[1:]
                
                server_info = {
                    'pubkey': event.author().to_hex(),
                    'content': content,
                    'tags': tags_dict
                }
                servers.append(server_info)
            except Exception as e:
                logger.error(f"Error parsing server announcement: {e}")
                
        return servers
        
    async def upload_file(self, file_path: str, server_pubkey: str = None) -> Dict:
        """Upload file to BlobDVM"""
        # Read file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Encode as base64
        file_b64 = base64.b64encode(file_data).decode()
        
        # Select server if not specified
        if not server_pubkey:
            servers = await self.discover_servers()
            if not servers:
                raise Exception("No BlobDVM servers found")
            server_pubkey = servers[0]['pubkey']
        
        # Create request
        request_data = {
            'action': 'store',
            'data': file_b64,
            'filename': os.path.basename(file_path)
        }
        
        tags = [Tag.parse(['a', f"{DVM_ANNOUNCEMENT_KIND}:{server_pubkey}:blob-storage-v1"])]
        
        event_builder = EventBuilder(
            kind=Kind(REQUEST_KIND),
            content=json.dumps(request_data),
            tags=tags
        )
        
        request_event = await self.client.send_event_builder(event_builder)
        
        # Wait for response
        response = await self.wait_for_response(request_event.id().to_hex())
        
        if 'error' in response:
            raise Exception(f"Upload failed: {response['message']}")
            
        return response
        
    async def download_file(self, file_hash: str, output_path: str = None) -> bytes:
        """Download file from BlobDVM"""
        # Find servers
        servers = await self.discover_servers()
        if not servers:
            raise Exception("No BlobDVM servers found")
        
        # Request file from first server
        server_pubkey = servers[0]['pubkey']
        
        request_data = {
            'action': 'retrieve',
            'hash': file_hash
        }
        
        tags = [Tag.parse(['a', f"{DVM_ANNOUNCEMENT_KIND}:{server_pubkey}:blob-storage-v1"])]
        
        event_builder = EventBuilder(
            kind=Kind(REQUEST_KIND),
            content=json.dumps(request_data),
            tags=tags
        )
        
        request_event = await self.client.send_event_builder(event_builder)
        
        # Wait for response
        response = await self.wait_for_response(request_event.id().to_hex())
        
        if 'error' in response:
            raise Exception(f"Download failed: {response['message']}")
        
        # Wait for chunks
        chunks = await self.collect_chunk_events(file_hash, response['chunks'])
        
        # Reassemble file
        file_data = self.chunker.reassemble_file(chunks)
        
        # Verify file hash
        actual_hash = hashlib.sha256(file_data).hexdigest()
        if actual_hash != file_hash:
            raise Exception(f"File integrity check failed: expected {file_hash}, got {actual_hash}")
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(file_data)
                
        return file_data
        
    async def delete_file(self, file_hash: str, server_pubkey: str = None) -> Dict:
        """Delete file from BlobDVM"""
        # Select server if not specified
        if not server_pubkey:
            servers = await self.discover_servers()
            if not servers:
                raise Exception("No BlobDVM servers found")
            server_pubkey = servers[0]['pubkey']
        
        request_data = {
            'action': 'delete',
            'hash': file_hash
        }
        
        tags = [Tag.parse(['a', f"{DVM_ANNOUNCEMENT_KIND}:{server_pubkey}:blob-storage-v1"])]
        
        event_builder = EventBuilder(
            kind=Kind(REQUEST_KIND),
            content=json.dumps(request_data),
            tags=tags
        )
        
        request_event = await self.client.send_event_builder(event_builder)
        
        # Wait for response
        response = await self.wait_for_response(request_event.id().to_hex())
        
        if 'error' in response:
            raise Exception(f"Delete failed: {response['message']}")
            
        return response
        
    async def wait_for_response(self, request_id: str, timeout: int = 30) -> Dict:
        """Wait for response event"""
        # Subscribe to response events
        filter = Filter().kinds([Kind(RESPONSE_KIND)]).tag('e', [request_id]).since(Timestamp.now())
        await self.client.subscribe([filter])
        
        handler = ResponseHandler(self, request_id)
        
        # Start handling notifications
        handle_task = asyncio.create_task(self.client.handle_notifications(handler))
        
        # Wait for response with timeout
        start_time = asyncio.get_event_loop().time()
        while request_id not in self.response_events:
            if asyncio.get_event_loop().time() - start_time > timeout:
                handle_task.cancel()
                raise Exception("Timeout waiting for response")
            await asyncio.sleep(0.1)
        
        handle_task.cancel()
        
        response_event = self.response_events.pop(request_id)
        return json.loads(response_event.content())
        
    async def collect_chunk_events(self, file_hash: str, expected_chunks: int, timeout: int = 60) -> List[Dict]:
        """Collect all chunk events for a file"""
        # Subscribe to chunk events
        filter = Filter().kinds([Kind(CHUNK_KIND)]).tag('file_hash', [file_hash]).since(Timestamp.now())
        await self.client.subscribe([filter])
        
        self.chunk_events[file_hash] = []
        handler = ChunkHandler(self, file_hash)
        
        # Start handling notifications
        handle_task = asyncio.create_task(self.client.handle_notifications(handler))
        
        # Wait for all chunks
        start_time = asyncio.get_event_loop().time()
        while len(self.chunk_events.get(file_hash, [])) < expected_chunks:
            if asyncio.get_event_loop().time() - start_time > timeout:
                handle_task.cancel()
                raise Exception(f"Timeout collecting chunks: got {len(self.chunk_events.get(file_hash, []))}/{expected_chunks}")
            await asyncio.sleep(0.1)
        
        handle_task.cancel()
        
        chunks = self.chunk_events.pop(file_hash)
        
        # Convert events to chunk dictionaries
        chunk_dicts = []
        for event in chunks:
            tags_dict = {}
            for tag in event.tags():
                tag_vec = tag.as_vec()
                if len(tag_vec) >= 2:
                    tags_dict[tag_vec[0]] = tag_vec[1]
            
            chunk_dicts.append({
                'index': int(tags_dict['chunk_index']),
                'data': event.content(),
                'hash': tags_dict['chunk_hash'],
                'size': len(base64.b64decode(event.content()))
            })
            
        return chunk_dicts

class ResponseHandler(HandleNotification):
    def __init__(self, client: BlobDVMClient, request_id: str):
        self.client = client
        self.request_id = request_id
        
    async def handle(self, relay_url: str, subscription_id: str, event: Event):
        # Check if this is the response we're waiting for
        for tag in event.tags():
            if tag.as_vec()[0] == 'e' and tag.as_vec()[1] == self.request_id:
                self.client.response_events[self.request_id] = event
                break
                
    async def handle_msg(self, relay_url: str, msg: RelayMessage):
        pass

class ChunkHandler(HandleNotification):
    def __init__(self, client: BlobDVMClient, file_hash: str):
        self.client = client
        self.file_hash = file_hash
        
    async def handle(self, relay_url: str, subscription_id: str, event: Event):
        # Check if this chunk belongs to our file
        for tag in event.tags():
            if tag.as_vec()[0] == 'file_hash' and tag.as_vec()[1] == self.file_hash:
                if self.file_hash not in self.client.chunk_events:
                    self.client.chunk_events[self.file_hash] = []
                self.client.chunk_events[self.file_hash].append(event)
                break
                
    async def handle_msg(self, relay_url: str, msg: RelayMessage):
        pass