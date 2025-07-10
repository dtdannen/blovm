# Configuration Constants
CHUNK_SIZE = 32768  # 32KB chunks
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit
DEFAULT_RETENTION = 24 * 3600  # 24 hours

# Event Kinds
DVM_ANNOUNCEMENT_KIND = 31999
REQUEST_KIND = 24210
RESPONSE_KIND = 24211
CHUNK_KIND = 24212
STATUS_KIND = 21999

# Error Codes
ERROR_CODES = {
    'FILE_TOO_LARGE': 'File exceeds maximum size limit',
    'INVALID_HASH': 'Invalid SHA256 hash format',
    'FILE_NOT_FOUND': 'Requested file not found',
    'CHUNK_MISSING': 'One or more chunks missing',
    'INTEGRITY_FAILED': 'File integrity verification failed',
    'STORAGE_FULL': 'Storage capacity exceeded',
    'INTERNAL_ERROR': 'Internal server error'
}