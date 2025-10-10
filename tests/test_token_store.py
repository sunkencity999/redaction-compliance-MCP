"""
Tests for token store implementations (in-memory and Redis with AES-GCM).
"""

import pytest
import os
import time
from mcp_redaction.token_store import (
    InMemoryTokenStore,
    RedisTokenStore,
    token_placeholder,
    create_token_store,
)


class TestInMemoryTokenStore:
    """Test in-memory token store."""
    
    def test_create_handle(self):
        store = InMemoryTokenStore()
        handle = store.create()
        assert handle.startswith("tm_")
    
    def test_put_and_get(self):
        store = InMemoryTokenStore()
        handle = store.create()
        
        store.put(handle, "key1", "secret_value", "secret")
        value = store.get(handle, "key1")
        assert value == "secret_value"
    
    def test_put_invalid_handle(self):
        store = InMemoryTokenStore()
        with pytest.raises(KeyError):
            store.put("invalid_handle", "key1", "value", "meta")
    
    def test_get_nonexistent_key(self):
        store = InMemoryTokenStore()
        handle = store.create()
        value = store.get(handle, "nonexistent")
        assert value is None
    
    def test_all_tokens(self):
        store = InMemoryTokenStore()
        handle = store.create()
        
        store.put(handle, "key1", "value1", "secret")
        store.put(handle, "key2", "value2", "pii")
        
        kv, meta = store.all(handle)
        assert kv["key1"] == "value1"
        assert kv["key2"] == "value2"
        assert meta["key1"] == "secret"
        assert meta["key2"] == "pii"
    
    def test_expiration(self):
        store = InMemoryTokenStore()
        handle = store.create(ttl_seconds=1)
        store.put(handle, "key1", "value1", "secret")
        
        # Should be accessible immediately
        assert store.get(handle, "key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        assert store.get(handle, "key1") is None
    
    def test_cleanup(self):
        store = InMemoryTokenStore()
        handle = store.create(ttl_seconds=1)
        store.put(handle, "key1", "value1", "secret")
        
        time.sleep(1.1)
        store.cleanup()
        
        # Handle should be removed
        kv, meta = store.all(handle)
        assert kv == {}
        assert meta == {}


class TestRedisTokenStore:
    """Test Redis token store with encryption."""
    
    @pytest.fixture
    def redis_available(self):
        """Check if Redis is available for testing."""
        try:
            import redis
            r = redis.from_url("redis://localhost:6379/15")
            r.ping()
            return True
        except:
            pytest.skip("Redis not available for testing")
    
    @pytest.fixture
    def redis_store(self, redis_available):
        """Create a Redis store for testing."""
        os.environ["MCP_ENCRYPTION_KEY"] = "test-encryption-key-for-redis-store"
        store = RedisTokenStore("redis://localhost:6379/15")
        yield store
        # Cleanup
        store.redis.flushdb()
    
    def test_create_handle(self, redis_store):
        handle = redis_store.create()
        assert handle.startswith("tm_")
    
    def test_put_and_get_encrypted(self, redis_store):
        handle = redis_store.create()
        
        redis_store.put(handle, "key1", "secret_value", "secret")
        value = redis_store.get(handle, "key1")
        assert value == "secret_value"
        
        # Verify data is encrypted in Redis
        raw_data = redis_store.redis.get(f"tokenmap:{handle}")
        assert b"secret_value" not in raw_data  # Should be encrypted
    
    def test_put_invalid_handle(self, redis_store):
        with pytest.raises(KeyError):
            redis_store.put("invalid_handle", "key1", "value", "meta")
    
    def test_all_tokens_encrypted(self, redis_store):
        handle = redis_store.create()
        
        redis_store.put(handle, "key1", "value1", "secret")
        redis_store.put(handle, "key2", "value2", "pii")
        
        kv, meta = redis_store.all(handle)
        assert kv["key1"] == "value1"
        assert kv["key2"] == "value2"
        assert meta["key1"] == "secret"
        assert meta["key2"] == "pii"
    
    def test_expiration_redis(self, redis_store):
        handle = redis_store.create(ttl_seconds=2)
        redis_store.put(handle, "key1", "value1", "secret")
        
        # Should be accessible immediately
        assert redis_store.get(handle, "key1") == "value1"
        
        # Wait for expiration
        time.sleep(2.1)
        assert redis_store.get(handle, "key1") is None
    
    def test_encryption_decryption(self, redis_store):
        test_data = b'{"kv": {"key": "sensitive"}, "meta": {"key": "secret"}}'
        encrypted = redis_store._encrypt(test_data)
        
        # Verify it's different from original
        assert encrypted != test_data
        assert len(encrypted) > len(test_data)  # Includes nonce and tag
        
        # Decrypt and verify
        decrypted = redis_store._decrypt(encrypted)
        assert decrypted == test_data
    
    def test_missing_encryption_key(self):
        if "MCP_ENCRYPTION_KEY" in os.environ:
            del os.environ["MCP_ENCRYPTION_KEY"]
        
        with pytest.raises(RuntimeError, match="MCP_ENCRYPTION_KEY"):
            RedisTokenStore("redis://localhost:6379/15")


class TestTokenPlaceholder:
    """Test deterministic token placeholder generation."""
    
    def test_placeholder_format(self):
        salt = b"test-salt"
        placeholder = token_placeholder("SECRET", "my-secret-value", salt)
        assert placeholder.startswith("«token:SECRET:")
        assert placeholder.endswith("»")
        assert len(placeholder.split(":")) == 3
    
    def test_deterministic_generation(self):
        salt = b"test-salt"
        ph1 = token_placeholder("PII", "john@example.com", salt)
        ph2 = token_placeholder("PII", "john@example.com", salt)
        assert ph1 == ph2
    
    def test_different_values_different_placeholders(self):
        salt = b"test-salt"
        ph1 = token_placeholder("PII", "john@example.com", salt)
        ph2 = token_placeholder("PII", "jane@example.com", salt)
        assert ph1 != ph2
    
    def test_different_salts_different_placeholders(self):
        ph1 = token_placeholder("PII", "john@example.com", b"salt1")
        ph2 = token_placeholder("PII", "john@example.com", b"salt2")
        assert ph1 != ph2
    
    def test_different_types_different_placeholders(self):
        salt = b"test-salt"
        ph1 = token_placeholder("PII", "data", salt)
        ph2 = token_placeholder("SECRET", "data", salt)
        assert ph1 != ph2


class TestTokenStoreFactory:
    """Test token store factory function."""
    
    def test_create_memory_store(self):
        store = create_token_store("memory")
        assert isinstance(store, InMemoryTokenStore)
    
    def test_create_redis_store_missing_url(self):
        os.environ["MCP_ENCRYPTION_KEY"] = "test-key"
        with pytest.raises(ValueError, match="redis_url required"):
            create_token_store("redis")
    
    def test_invalid_backend(self):
        with pytest.raises(ValueError, match="Unknown token store backend"):
            create_token_store("invalid_backend")
