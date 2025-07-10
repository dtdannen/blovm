import pytest
import hashlib
from src.blobdvm.chunker import FileChunker

class TestFileChunker:
    def test_create_chunks_single_chunk(self):
        """Test creating chunks for data smaller than chunk size"""
        chunker = FileChunker(chunk_size=1024)
        data = b"Hello, World!"
        
        chunks = chunker.create_chunks(data)
        
        assert len(chunks) == 1
        assert chunks[0]['index'] == 0
        assert chunks[0]['size'] == len(data)
        assert chunks[0]['hash'] == hashlib.sha256(data).hexdigest()
        
    def test_create_chunks_multiple_chunks(self):
        """Test creating multiple chunks"""
        chunker = FileChunker(chunk_size=10)
        data = b"A" * 25  # 25 bytes, should create 3 chunks
        
        chunks = chunker.create_chunks(data)
        
        assert len(chunks) == 3
        assert chunks[0]['size'] == 10
        assert chunks[1]['size'] == 10
        assert chunks[2]['size'] == 5
        assert chunks[0]['index'] == 0
        assert chunks[1]['index'] == 1
        assert chunks[2]['index'] == 2
        
    def test_reassemble_file(self):
        """Test reassembling chunks back to original file"""
        chunker = FileChunker(chunk_size=100)
        original_data = b"This is a test file content that will be chunked and reassembled" * 10
        
        # Create chunks
        chunks = chunker.create_chunks(original_data)
        
        # Reassemble
        reassembled = chunker.reassemble_file(chunks)
        
        assert reassembled == original_data
        assert hashlib.sha256(reassembled).hexdigest() == hashlib.sha256(original_data).hexdigest()
        
    def test_verify_chunks_valid(self):
        """Test verifying valid chunks"""
        chunker = FileChunker(chunk_size=50)
        data = b"Test data for chunk verification"
        expected_hash = hashlib.sha256(data).hexdigest()
        
        chunks = chunker.create_chunks(data)
        
        assert chunker.verify_chunks(chunks, expected_hash) == True
        
    def test_verify_chunks_invalid_hash(self):
        """Test verifying chunks with wrong expected hash"""
        chunker = FileChunker(chunk_size=50)
        data = b"Test data for chunk verification"
        wrong_hash = "0" * 64
        
        chunks = chunker.create_chunks(data)
        
        assert chunker.verify_chunks(chunks, wrong_hash) == False
        
    def test_verify_chunks_corrupted_chunk(self):
        """Test verifying chunks with corrupted chunk data"""
        chunker = FileChunker(chunk_size=50)
        data = b"Test data for chunk verification"
        expected_hash = hashlib.sha256(data).hexdigest()
        
        chunks = chunker.create_chunks(data)
        
        # Corrupt one chunk
        chunks[0]['hash'] = "corrupted_hash"
        
        # Should fail verification
        assert chunker.verify_chunks(chunks, expected_hash) == False
        
    def test_chunk_order_preservation(self):
        """Test that chunks can be reassembled regardless of order"""
        chunker = FileChunker(chunk_size=10)
        data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        chunks = chunker.create_chunks(data)
        
        # Reverse the chunk order
        reversed_chunks = list(reversed(chunks))
        
        # Should still reassemble correctly
        reassembled = chunker.reassemble_file(reversed_chunks)
        assert reassembled == data
        
    def test_empty_data(self):
        """Test handling empty data"""
        chunker = FileChunker()
        data = b""
        
        chunks = chunker.create_chunks(data)
        
        assert len(chunks) == 0
        
        reassembled = chunker.reassemble_file(chunks)
        assert reassembled == b""