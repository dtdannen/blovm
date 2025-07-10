import hashlib
import base64
from typing import List, Dict
from .constants import CHUNK_SIZE

class FileChunker:
    def __init__(self, chunk_size=CHUNK_SIZE):
        self.chunk_size = chunk_size
    
    def create_chunks(self, file_data: bytes) -> List[Dict]:
        """
        Split file into chunks with metadata
        Returns list of chunk dictionaries with:
        - index: chunk position
        - data: base64 encoded chunk
        - hash: SHA256 of chunk
        - size: chunk size in bytes
        """
        chunks = []
        for i in range(0, len(file_data), self.chunk_size):
            chunk_data = file_data[i:i + self.chunk_size]
            chunk_hash = hashlib.sha256(chunk_data).hexdigest()
            chunks.append({
                'index': i // self.chunk_size,
                'data': base64.b64encode(chunk_data).decode(),
                'hash': chunk_hash,
                'size': len(chunk_data)
            })
        return chunks
        
    def verify_chunks(self, chunks: List[Dict], expected_hash: str) -> bool:
        """
        Verify chunk integrity and reassemble to verify file hash
        """
        try:
            reassembled = self.reassemble_file(chunks)
            actual_hash = hashlib.sha256(reassembled).hexdigest()
            return actual_hash == expected_hash
        except Exception:
            return False
        
    def reassemble_file(self, chunks: List[Dict]) -> bytes:
        """
        Reassemble chunks into original file
        Must verify each chunk hash before assembly
        """
        sorted_chunks = sorted(chunks, key=lambda x: x['index'])
        file_data = b''
        
        for chunk in sorted_chunks:
            chunk_bytes = base64.b64decode(chunk['data'])
            # Verify chunk hash
            if hashlib.sha256(chunk_bytes).hexdigest() != chunk['hash']:
                raise ValueError(f"Chunk {chunk['index']} hash mismatch")
            file_data += chunk_bytes
            
        return file_data