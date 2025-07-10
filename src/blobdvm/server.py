import asyncio
import json
import time
import hashlib
import base64
from typing import List, Dict
from loguru import logger
from nostr_sdk import (
    Keys, Client, Filter, HandleNotification, Timestamp, 
    Kind, Event, EventBuilder, Tag, RelayMessage
)
from .chunker import FileChunker
from .constants import (
    CHUNK_SIZE, MAX_FILE_SIZE, DEFAULT_RETENTION,
    DVM_ANNOUNCEMENT_KIND, REQUEST_KIND, RESPONSE_KIND,
    CHUNK_KIND, STATUS_KIND, ERROR_CODES
)

class BlobDVMServer:
    def __init__(self, private_key_hex: str, relays: List[str]):
        self.keys = Keys.parse(private_key_hex)
        self.client = Client(self.keys)
        self.relays = relays
        self.storage = {}  # hash -> file_metadata
        self.chunker = FileChunker()
        self.job_queue = asyncio.Queue()
        self.running = False
        
    async def start(self):
        """
        Initialize relay connections and publish DVM announcement
        Start listening for requests
        """
        # Add relays
        for relay in self.relays:
            await self.client.add_relay(relay)
        
        await self.client.connect()
        logger.info("Connected to relays")
        
        # Publish DVM announcement
        await self.publish_dvm_announcement()
        
        # Subscribe to requests
        filter = Filter().kinds([Kind(REQUEST_KIND)]).since(Timestamp.now())
        await self.client.subscribe([filter])
        
        self.running = True
        
        # Start event processing
        handler = BlobDVMHandler(self)
        await asyncio.gather(
            self.process_job_queue(),
            self.client.handle_notifications(handler),
            self.cleanup_expired_files()
        )
        
    async def stop(self):
        """Stop the server gracefully"""
        self.running = False
        await self.client.disconnect()
        
    async def publish_dvm_announcement(self):
        """Publish DVM announcement event"""
        content = {
            "input_schema": {
                "type": "object",
                "oneOf": [
                    {
                        "required": ["action", "data"],
                        "properties": {
                            "action": {"const": "store"},
                            "data": {"type": "string", "description": "base64 encoded file"},
                            "filename": {"type": "string", "optional": True}
                        }
                    },
                    {
                        "required": ["action", "hash"],
                        "properties": {
                            "action": {"const": "retrieve"},
                            "hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
                        }
                    }
                ]
            }
        }
        
        tags = [
            Tag.parse(['d', 'blob-storage-v1']),
            Tag.parse(['k', str(REQUEST_KIND)]),
            Tag.parse(['response_kind', str(RESPONSE_KIND)]),
            Tag.parse(['name', 'BlobDVM Storage']),
            Tag.parse(['about', 'Content-addressed file storage over nostr']),
            Tag.parse(['max_file_size', str(MAX_FILE_SIZE)]),
            Tag.parse(['chunk_size', str(CHUNK_SIZE)]),
            Tag.parse(['retention_hours', '24'])
        ]
        
        event_builder = EventBuilder(
            kind=Kind(DVM_ANNOUNCEMENT_KIND),
            content=json.dumps(content),
            tags=tags
        )
        
        await self.client.send_event_builder(event_builder)
        logger.info("Published DVM announcement")
        
    async def process_job_queue(self):
        """Process incoming job requests"""
        while self.running:
            try:
                event = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                await self.handle_request(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                
    async def handle_request(self, event: Event):
        """Route request to appropriate handler"""
        try:
            request_data = json.loads(event.content())
            action = request_data.get('action')
            
            if action == 'store':
                await self.handle_store_request(event)
            elif action == 'retrieve':
                await self.handle_retrieve_request(event)
            elif action == 'delete':
                await self.handle_delete_request(event)
            else:
                await self.send_error(event, "INVALID_ACTION", f"Unknown action: {action}")
                
        except json.JSONDecodeError:
            await self.send_error(event, "INVALID_JSON", "Invalid JSON in request")
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            await self.send_error(event, "INTERNAL_ERROR", str(e))
        
    async def handle_store_request(self, event: Event) -> None:
        """Process file storage request"""
        try:
            request_data = json.loads(event.content())
            file_data = base64.b64decode(request_data['data'])
            
            # Validate file size
            if len(file_data) > MAX_FILE_SIZE:
                await self.send_error(event, "FILE_TOO_LARGE", ERROR_CODES["FILE_TOO_LARGE"])
                return
            
            # Generate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Create chunks
            chunks = self.chunker.create_chunks(file_data)
            
            # Store metadata
            self.storage[file_hash] = {
                'chunks': chunks,
                'size': len(file_data),
                'expires': time.time() + DEFAULT_RETENTION,
                'filename': request_data.get('filename', '')
            }
            
            # Publish chunk events
            await self.publish_chunk_events(file_hash, chunks)
            
            # Send response
            response_data = {
                'hash': file_hash,
                'size': len(file_data),
                'chunks': len(chunks),
                'expires': int(time.time() + DEFAULT_RETENTION),
                'status': 'stored'
            }
            
            await self.send_response(event, response_data)
            logger.info(f"Stored file {file_hash} with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error handling store request: {e}")
            await self.send_error(event, "INTERNAL_ERROR", str(e))
        
    async def handle_retrieve_request(self, event: Event) -> None:
        """Process file retrieval request"""
        try:
            request_data = json.loads(event.content())
            file_hash = request_data['hash']
            
            if file_hash not in self.storage:
                await self.send_error(event, "FILE_NOT_FOUND", ERROR_CODES["FILE_NOT_FOUND"])
                return
            
            file_metadata = self.storage[file_hash]
            
            # Check if expired
            if time.time() > file_metadata['expires']:
                del self.storage[file_hash]
                await self.send_error(event, "FILE_NOT_FOUND", "File expired")
                return
            
            # Republish chunk events
            await self.publish_chunk_events(file_hash, file_metadata['chunks'])
            
            # Send response
            response_data = {
                'hash': file_hash,
                'size': file_metadata['size'],
                'chunks': len(file_metadata['chunks']),
                'expires': int(file_metadata['expires']),
                'status': 'available'
            }
            
            await self.send_response(event, response_data)
            logger.info(f"Retrieved file {file_hash}")
            
        except Exception as e:
            logger.error(f"Error handling retrieve request: {e}")
            await self.send_error(event, "INTERNAL_ERROR", str(e))
            
    async def handle_delete_request(self, event: Event) -> None:
        """Process file deletion request"""
        try:
            request_data = json.loads(event.content())
            file_hash = request_data['hash']
            
            if file_hash in self.storage:
                del self.storage[file_hash]
                response_data = {
                    'hash': file_hash,
                    'status': 'deleted'
                }
                await self.send_response(event, response_data)
                logger.info(f"Deleted file {file_hash}")
            else:
                await self.send_error(event, "FILE_NOT_FOUND", ERROR_CODES["FILE_NOT_FOUND"])
                
        except Exception as e:
            logger.error(f"Error handling delete request: {e}")
            await self.send_error(event, "INTERNAL_ERROR", str(e))
            
    async def publish_chunk_events(self, file_hash: str, chunks: List[Dict]) -> None:
        """Publish all chunk events with proper expiration"""
        expiration = int(time.time() + DEFAULT_RETENTION)
        
        for chunk in chunks:
            tags = [
                Tag.parse(['file_hash', file_hash]),
                Tag.parse(['chunk_index', str(chunk['index'])]),
                Tag.parse(['chunk_total', str(len(chunks))]),
                Tag.parse(['chunk_hash', chunk['hash']]),
                Tag.parse(['expiration', str(expiration)])
            ]
            
            event_builder = EventBuilder(
                kind=Kind(CHUNK_KIND),
                content=chunk['data'],
                tags=tags
            )
            
            await self.client.send_event_builder(event_builder)
        
        logger.info(f"Published {len(chunks)} chunk events for {file_hash}")
        
    async def send_response(self, request_event: Event, response_data: Dict):
        """Send response event"""
        tags = [
            Tag.event(request_event.id()),
            Tag.parse(['p', request_event.author().to_hex()])
        ]
        
        if 'hash' in response_data:
            tags.append(Tag.parse(['file_hash', response_data['hash']]))
        if 'expires' in response_data:
            tags.append(Tag.parse(['expires', str(response_data['expires'])]))
            
        event_builder = EventBuilder(
            kind=Kind(RESPONSE_KIND),
            content=json.dumps(response_data),
            tags=tags
        )
        
        await self.client.send_event_builder(event_builder)
        
    async def send_error(self, request_event: Event, error_code: str, error_msg: str):
        """Send error response"""
        response_data = {
            'error': error_code,
            'message': error_msg,
            'status': 'error'
        }
        await self.send_response(request_event, response_data)
        
    async def cleanup_expired_files(self):
        """Periodically clean up expired files"""
        while self.running:
            try:
                current_time = time.time()
                expired_hashes = [
                    hash for hash, metadata in self.storage.items()
                    if current_time > metadata['expires']
                ]
                
                for hash in expired_hashes:
                    del self.storage[hash]
                    logger.info(f"Cleaned up expired file {hash}")
                    
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)

class BlobDVMHandler(HandleNotification):
    def __init__(self, server: BlobDVMServer):
        self.server = server
        
    async def handle(self, relay_url: str, subscription_id: str, event: Event):
        # Check if this is a request for our DVM
        for tag in event.tags():
            if tag.as_vec()[0] == 'a' and 'blob-storage-v1' in tag.as_vec()[1]:
                await self.server.job_queue.put(event)
                break
        
    async def handle_msg(self, relay_url: str, msg: RelayMessage):
        pass  # Handle relay messages if needed