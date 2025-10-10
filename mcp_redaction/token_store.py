import os, hmac, hashlib, json, time, base64
from typing import Dict, Tuple, Optional, Protocol
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import orjson

class TokenStore(Protocol):
    """Protocol for token store implementations."""
    def create(self, ttl_seconds: int = 4*3600) -> str: ...
    def put(self, handle: str, key: str, value: str, meta: str) -> None: ...
    def get(self, handle: str, key: str) -> Optional[str]: ...
    def all(self, handle: str) -> Tuple[Dict[str, str], Dict[str, str]]: ...
    def cleanup(self) -> None: ...


class InMemoryTokenStore:
    """In-memory token store for development/testing."""
    def __init__(self):
        self._maps: Dict[str, Tuple[float, Dict[str,str], Dict[str,str]]] = {}

    def create(self, ttl_seconds: int = 4*3600):
        handle = f"tm_{int(time.time()*1000)}"
        self._maps[handle] = (time.time()+ttl_seconds, {}, {})
        return handle

    def put(self, handle: str, key: str, value: str, meta: str):
        if handle not in self._maps:
            raise KeyError("invalid handle")
        exp, kv, meta_kv = self._maps[handle]
        kv[key] = value
        meta_kv[key] = meta

    def get(self, handle: str, key: str) -> Optional[str]:
        exp, kv, _ = self._maps.get(handle, (0,{},{}))
        if exp < time.time():
            return None
        return kv.get(key)

    def all(self, handle: str):
        exp, kv, meta_kv = self._maps.get(handle, (0,{},{}))
        if exp < time.time():
            return {}, {}
        return kv, meta_kv

    def cleanup(self):
        now = time.time()
        for k,(exp,_,_) in list(self._maps.items()):
            if exp < now:
                del self._maps[k]


class RedisTokenStore:
    """
    Redis-backed token store with AES-GCM encryption.
    
    Tokens are encrypted at rest in Redis using AES-256-GCM.
    Encryption key is derived from MCP_ENCRYPTION_KEY environment variable.
    """
    
    def __init__(self, redis_url: str, encryption_key: Optional[str] = None):
        """
        Initialize Redis token store.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            encryption_key: Base64-encoded 32-byte encryption key. 
                          If None, reads from MCP_ENCRYPTION_KEY env var.
        """
        try:
            import redis
        except ImportError:
            raise RuntimeError("redis package required for RedisTokenStore. Install with: pip install redis")
        
        self.redis = redis.from_url(redis_url, decode_responses=False)
        
        # Initialize encryption
        encryption_key = encryption_key or os.getenv("MCP_ENCRYPTION_KEY")
        if not encryption_key:
            raise RuntimeError("MCP_ENCRYPTION_KEY environment variable required for RedisTokenStore")
        
        # Derive AES-256 key from provided key using PBKDF2
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"mcp-redaction-salt-v1",  # Static salt for deterministic key derivation
            iterations=100000,
        )
        key_bytes = encryption_key.encode('utf-8')
        self.encryption_key = kdf.derive(key_bytes)
        self.aesgcm = AESGCM(self.encryption_key)
    
    def _encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-GCM.
        Returns: nonce (12 bytes) + ciphertext + tag (16 bytes)
        """
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    
    def _decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt AES-GCM encrypted data.
        Expects: nonce (12 bytes) + ciphertext + tag (16 bytes)
        """
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None)
    
    def create(self, ttl_seconds: int = 4*3600) -> str:
        """Create a new token map handle."""
        handle = f"tm_{int(time.time()*1000)}"
        
        # Store empty map with expiration
        data = orjson.dumps({"kv": {}, "meta": {}})
        encrypted = self._encrypt(data)
        
        self.redis.setex(
            f"tokenmap:{handle}",
            ttl_seconds,
            encrypted
        )
        return handle
    
    def put(self, handle: str, key: str, value: str, meta: str) -> None:
        """Store a token in the map."""
        redis_key = f"tokenmap:{handle}"
        
        # Get existing data
        encrypted_data = self.redis.get(redis_key)
        if not encrypted_data:
            raise KeyError("invalid handle")
        
        decrypted = self._decrypt(encrypted_data)
        data = orjson.loads(decrypted)
        
        # Update maps
        data["kv"][key] = value
        data["meta"][key] = meta
        
        # Re-encrypt and store
        new_data = orjson.dumps(data)
        encrypted = self._encrypt(new_data)
        
        # Preserve TTL
        ttl = self.redis.ttl(redis_key)
        if ttl > 0:
            self.redis.setex(redis_key, ttl, encrypted)
        else:
            self.redis.set(redis_key, encrypted)
    
    def get(self, handle: str, key: str) -> Optional[str]:
        """Retrieve a single token from the map."""
        redis_key = f"tokenmap:{handle}"
        encrypted_data = self.redis.get(redis_key)
        
        if not encrypted_data:
            return None
        
        decrypted = self._decrypt(encrypted_data)
        data = orjson.loads(decrypted)
        return data.get("kv", {}).get(key)
    
    def all(self, handle: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Retrieve all tokens and metadata from the map."""
        redis_key = f"tokenmap:{handle}"
        encrypted_data = self.redis.get(redis_key)
        
        if not encrypted_data:
            return {}, {}
        
        decrypted = self._decrypt(encrypted_data)
        data = orjson.loads(decrypted)
        return data.get("kv", {}), data.get("meta", {})
    
    def cleanup(self) -> None:
        """Cleanup expired entries (handled automatically by Redis TTL)."""
        pass  # Redis handles expiration automatically


def token_placeholder(token_type: str, raw: str, salt: bytes) -> str:
    """
    Generate a deterministic placeholder for a token.
    
    Args:
        token_type: Category of the token (e.g., 'SECRET', 'PII')
        raw: The raw sensitive value
        salt: HMAC salt for deterministic hashing
    
    Returns:
        Placeholder string in format: «token:TYPE:HASH4»
    """
    h = hmac.new(salt, raw.encode("utf-8"), hashlib.sha256).hexdigest()[:4]
    return f"«token:{token_type}:{h}»"


def create_token_store(backend: str = "memory", redis_url: Optional[str] = None) -> TokenStore:
    """
    Factory function to create appropriate token store.
    
    Args:
        backend: 'memory' or 'redis'
        redis_url: Redis connection URL (required if backend='redis')
    
    Returns:
        TokenStore implementation
    """
    if backend == "redis":
        if not redis_url:
            raise ValueError("redis_url required for redis backend")
        return RedisTokenStore(redis_url)
    elif backend == "memory":
        return InMemoryTokenStore()
    else:
        raise ValueError(f"Unknown token store backend: {backend}")
