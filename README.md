# BlobDVM - Decentralized File Storage over Nostr

BlobDVM is a proof-of-concept implementation of a decentralized file storage system using Nostr's Data Vending Machine (DVM) protocol. It combines content-addressed storage with nostr's relay network to eliminate DNS dependencies and create a fully decentralized file storage solution.

## Features

- **Content-addressed storage**: Files are identified by their SHA256 hash
- **Decentralized**: No central servers or DNS requirements
- **Chunked transfer**: Large files are split into manageable chunks
- **Automatic discovery**: Find storage providers via nostr relays
- **Simple CLI**: Easy-to-use command line interface

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Quick Start

### List available storage servers

```bash
python src/cli.py list-servers
```

### Upload a file

```bash
python src/cli.py upload myfile.jpg
```

### Download a file

```bash
python src/cli.py download <file_hash> --output downloaded.jpg
```

### Run a storage server

```bash
python src/cli.py serve --private-key <your_nsec_or_hex_key>
```

## Architecture

BlobDVM uses the following Nostr event kinds:

- **Kind 31999**: DVM service announcement
- **Kind 24210**: Storage/retrieve requests
- **Kind 24211**: Storage responses
- **Kind 24212**: File chunk events (ephemeral)
- **Kind 21999**: Status/error events

### How it works

1. **Storage providers** announce their service using kind 31999 events
2. **Clients** discover providers and send storage requests (kind 24210)
3. **Files are chunked** into 32KB pieces and published as ephemeral events
4. **Content addressing** ensures file integrity via SHA256 hashing
5. **Automatic expiration** cleans up old files (default: 24 hours)

## Configuration

The system uses these default settings:

- **Chunk size**: 32KB
- **Max file size**: 10MB
- **Default retention**: 24 hours

## Development

### Run tests

```bash
pytest tests/
```

### Project structure

```
blobdvm/
├── src/
│   ├── blobdvm/
│   │   ├── __init__.py
│   │   ├── server.py       # Storage provider implementation
│   │   ├── client.py       # Client library
│   │   ├── chunker.py      # File chunking logic
│   │   └── constants.py    # Configuration constants
│   └── cli.py              # Command-line interface
├── tests/
│   └── test_chunker.py     # Unit tests
├── requirements.txt
├── setup.py
└── README.md
```

## Limitations

This is a proof-of-concept with the following limitations:

- 10MB file size limit
- 24-hour retention period
- No encryption (can be added)
- No payment integration (can be added via Lightning)

## Future Improvements

- Add encryption support
- Implement payment for storage via Lightning
- Increase file size limits
- Add redundancy across multiple providers
- Implement pinning for permanent storage
- Create web interface

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
