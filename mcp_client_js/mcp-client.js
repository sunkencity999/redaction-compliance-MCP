/**
 * MCP Redaction Client - JavaScript/Browser SDK
 * Version 2.0.0
 * 
 * Seamless integration for browser-based applications
 * Works with vanilla JS, React, Vue, Angular, etc.
 */

class MCPClient {
    /**
     * Create MCP client instance
     * @param {Object} config - Configuration object
     * @param {string} config.serverUrl - MCP server URL (e.g., 'https://mcp.yourcompany.com')
     * @param {string} config.caller - Application identifier (e.g., 'web-app')
     * @param {string} config.region - Region code (default: 'us')
     * @param {string} config.env - Environment (default: 'prod')
     * @param {number} config.timeout - Request timeout in ms (default: 30000)
     */
    constructor(config) {
        this.serverUrl = config.serverUrl;
        this.caller = config.caller;
        this.region = config.region || 'us';
        this.env = config.env || 'prod';
        this.timeout = config.timeout || 30000;
    }

    /**
     * Build context object for requests
     * @private
     */
    _getContext() {
        return {
            caller: this.caller,
            region: this.region,
            env: this.env
        };
    }

    /**
     * Make HTTP request to MCP server
     * @private
     */
    async _request(endpoint, data) {
        const url = `${this.serverUrl}/${endpoint.replace(/^\//, '')}`;
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                signal: controller.signal,
                credentials: 'include' // Include cookies for authentication
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                if (response.status === 403) {
                    const error = await response.json();
                    throw new MCPAuthError(error.detail || 'Authorization failed');
                }
                throw new MCPError(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new MCPConnectionError(`Request timed out after ${this.timeout}ms`);
            }
            if (error instanceof MCPError) {
                throw error;
            }
            throw new MCPConnectionError(`Failed to connect to MCP server: ${error.message}`);
        }
    }

    /**
     * Classify payload to detect sensitive content
     * @param {string} payload - Text to classify
     * @returns {Promise<Object>} Classification result
     */
    async classify(payload) {
        return await this._request('/classify', {
            payload: payload,
            context: this._getContext()
        });
    }

    /**
     * Redact sensitive content from payload
     * @param {string} payload - Text to redact
     * @returns {Promise<{sanitized: string, tokenHandle: string}>} Sanitized payload and token handle
     * @throws {MCPBlockedError} If request is blocked by policy
     */
    async redact(payload) {
        // First classify to check policy
        const classification = await this.classify(payload);
        
        if (classification.suggested_action === 'block') {
            throw new MCPBlockedError(
                'Request blocked by policy',
                classification.decision
            );
        }

        // Redact
        const response = await this._request('/redact', {
            payload: payload,
            context: this._getContext()
        });

        return {
            sanitized: response.sanitized_payload,
            tokenHandle: response.token_map_handle
        };
    }

    /**
     * Restore tokens from payload (selective)
     * @param {string} payload - Text with tokens to restore
     * @param {string} tokenHandle - Token handle from redact()
     * @param {Array<string>} allowCategories - Categories to restore (default: ['pii', 'ops_sensitive'])
     * @returns {Promise<string>} Text with allowed tokens restored
     */
    async detokenize(payload, tokenHandle, allowCategories = ['pii', 'ops_sensitive']) {
        const response = await this._request('/detokenize', {
            payload: payload,
            token_map_handle: tokenHandle,
            allow_categories: allowCategories,
            context: this._getContext()
        });

        return response.restored_payload;
    }

    /**
     * Safely call an LLM with automatic redaction/detokenization
     * @param {string} userInput - User input (may contain sensitive data)
     * @param {Function} llmFunction - Async function that calls LLM with sanitized input
     * @param {boolean} shouldDetokenize - Whether to detokenize response (default: true)
     * @param {Array<string>} allowCategories - Categories to restore (default: ['pii', 'ops_sensitive'])
     * @returns {Promise<string>} Safe response
     */
    async safeLLMCall(userInput, llmFunction, shouldDetokenize = true, allowCategories = ['pii', 'ops_sensitive']) {
        // Redact
        const { sanitized, tokenHandle } = await this.redact(userInput);
        
        // Call LLM
        const llmResponse = await llmFunction(sanitized);
        
        // Detokenize if requested
        if (shouldDetokenize) {
            return await this.detokenize(llmResponse, tokenHandle, allowCategories);
        }
        
        return llmResponse;
    }

    /**
     * Quick check if payload is safe to send to external LLM
     * @param {string} payload - Text to check
     * @returns {Promise<boolean>} True if safe, false if blocked
     */
    async isSafe(payload) {
        try {
            const result = await this.classify(payload);
            return result.suggested_action !== 'block';
        } catch (error) {
            // On error, assume unsafe
            return false;
        }
    }

    /**
     * Check MCP server health
     * @returns {Promise<Object>} Health status
     */
    async health() {
        const response = await fetch(`${this.serverUrl}/health`, {
            method: 'GET'
        });
        
        if (!response.ok) {
            throw new MCPConnectionError('Health check failed');
        }
        
        return await response.json();
    }
}

/**
 * Base MCP error
 */
class MCPError extends Error {
    constructor(message) {
        super(message);
        this.name = 'MCPError';
    }
}

/**
 * Request was blocked by policy
 */
class MCPBlockedError extends MCPError {
    constructor(message, decision = null) {
        super(message);
        this.name = 'MCPBlockedError';
        this.decision = decision;
    }
}

/**
 * Authentication/authorization error
 */
class MCPAuthError extends MCPError {
    constructor(message) {
        super(message);
        this.name = 'MCPAuthError';
    }
}

/**
 * Connection error
 */
class MCPConnectionError extends MCPError {
    constructor(message) {
        super(message);
        this.name = 'MCPConnectionError';
    }
}

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
    // Node.js / CommonJS
    module.exports = {
        MCPClient,
        MCPError,
        MCPBlockedError,
        MCPAuthError,
        MCPConnectionError
    };
}

if (typeof window !== 'undefined') {
    // Browser global
    window.MCPClient = MCPClient;
    window.MCPError = MCPError;
    window.MCPBlockedError = MCPBlockedError;
    window.MCPAuthError = MCPAuthError;
    window.MCPConnectionError = MCPConnectionError;
}
