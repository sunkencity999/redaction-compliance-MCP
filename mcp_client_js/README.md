# MCP Redaction Client - JavaScript/TypeScript SDK

Browser and Node.js client for MCP Redaction & Compliance Server.

## Installation

### Option 1: Copy to Your Project

```bash
# Copy the SDK file
cp mcp-client.js /path/to/your/project/src/

# For TypeScript projects, also copy types
cp mcp-client.d.ts /path/to/your/project/src/
```

### Option 2: CDN (Browser Only)

```html
<script src="https://your-cdn.com/mcp-client.js"></script>
```

### Option 3: NPM (Future)

```bash
npm install @your-org/mcp-redaction-client
```

---

## Quick Start

### Browser (Vanilla JavaScript)

```html
<!DOCTYPE html>
<html>
<head>
    <script src="mcp-client.js"></script>
</head>
<body>
    <script>
        // Initialize client
        const mcp = new MCPClient({
            serverUrl: 'https://mcp.yourcompany.com',
            caller: 'my-web-app'
        });

        // Redact sensitive data before sending to LLM
        async function safeChatCompletion(userInput) {
            try {
                const { sanitized, tokenHandle } = await mcp.redact(userInput);
                
                // Send sanitized version to your LLM
                const llmResponse = await callOpenAI(sanitized);
                
                // Restore non-secret tokens
                const final = await mcp.detokenize(llmResponse, tokenHandle);
                
                return final;
            } catch (error) {
                if (error instanceof MCPBlockedError) {
                    alert('This request contains sensitive data and was blocked.');
                }
                throw error;
            }
        }
    </script>
</body>
</html>
```

### React

```jsx
import { MCPClient } from './mcp-client.js';
import { useState, useEffect } from 'react';

function ChatApp() {
    const [mcp, setMcp] = useState(null);

    useEffect(() => {
        const client = new MCPClient({
            serverUrl: process.env.REACT_APP_MCP_SERVER,
            caller: 'react-chat-app'
        });
        setMcp(client);
    }, []);

    const handleSubmit = async (userInput) => {
        const response = await mcp.safeLLMCall(
            userInput,
            async (sanitized) => {
                // Call your LLM here
                return await callOpenAI(sanitized);
            }
        );
        return response;
    };

    return <div>{/* Your chat UI */}</div>;
}
```

### TypeScript

```typescript
import { MCPClient, MCPConfig, MCPBlockedError } from './mcp-client';

const config: MCPConfig = {
    serverUrl: 'https://mcp.yourcompany.com',
    caller: 'typescript-app',
    region: 'us',
    timeout: 30000
};

const mcp = new MCPClient(config);

async function protectedLLMCall(input: string): Promise<string> {
    try {
        const { sanitized, tokenHandle } = await mcp.redact(input);
        const llmResponse = await yourLLMFunction(sanitized);
        const final = await mcp.detokenize(llmResponse, tokenHandle);
        return final;
    } catch (error) {
        if (error instanceof MCPBlockedError) {
            console.error('Blocked by policy:', error.decision);
            throw new Error('Request contains sensitive data');
        }
        throw error;
    }
}
```

### Node.js

```javascript
const { MCPClient } = require('./mcp-client.js');

const mcp = new MCPClient({
    serverUrl: 'https://mcp.yourcompany.com',
    caller: 'node-app'
});

async function main() {
    const userInput = "My AWS key is AKIAIOSFODNN7EXAMPLE";
    
    // Check if safe
    const isSafe = await mcp.isSafe(userInput);
    console.log('Is safe?', isSafe); // false
    
    // Try to redact
    try {
        const { sanitized } = await mcp.redact(userInput);
        console.log('Sanitized:', sanitized);
    } catch (error) {
        console.error('Blocked:', error.message);
    }
}

main();
```

---

## API Reference

### Constructor

```javascript
new MCPClient(config)
```

**Config Options:**
- `serverUrl` (string, required): MCP server URL
- `caller` (string, required): Application identifier
- `region` (string, optional): Region code (default: 'us')
- `env` (string, optional): Environment (default: 'prod')
- `timeout` (number, optional): Request timeout in ms (default: 30000)

### Methods

#### `classify(payload)`

Classify payload to detect sensitive content.

```javascript
const result = await mcp.classify("My password is secret123");
console.log(result.categories); // [{ type: 'pii', confidence: 0.85 }]
console.log(result.suggested_action); // 'redact' or 'block'
```

#### `redact(payload)`

Redact sensitive content from payload.

```javascript
const { sanitized, tokenHandle } = await mcp.redact(
    "My AWS key is AKIAIOSFODNN7EXAMPLE"
);
// sanitized: "My AWS key is «token:SECRET:a3f9»"
// tokenHandle: "conv-123-abc"
```

**Throws:** `MCPBlockedError` if policy blocks the request.

#### `detokenize(payload, tokenHandle, allowCategories?)`

Restore tokens from payload (selective).

```javascript
const final = await mcp.detokenize(
    llmResponse,
    tokenHandle,
    ['pii', 'ops_sensitive'] // NOT 'secret'
);
```

**Note:** Secrets are NEVER detokenized.

#### `safeLLMCall(userInput, llmFunction, shouldDetokenize?, allowCategories?)`

Convenience wrapper for automatic redaction/detokenization.

```javascript
const response = await mcp.safeLLMCall(
    userInput,
    async (sanitized) => {
        return await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${OPENAI_KEY}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: 'gpt-4',
                messages: [{ role: 'user', content: sanitized }]
            })
        }).then(r => r.json()).then(d => d.choices[0].message.content);
    }
);
```

#### `isSafe(payload)`

Quick check if payload is safe to send to external LLM.

```javascript
const safe = await mcp.isSafe(userInput);
if (!safe) {
    alert('This message contains sensitive data!');
}
```

#### `health()`

Check MCP server health.

```javascript
const status = await mcp.health();
console.log(status); // { status: 'healthy', version: '2.0.0', ... }
```

---

## Error Handling

### MCPBlockedError

Thrown when request is blocked by policy.

```javascript
try {
    await mcp.redact("My password is secret123");
} catch (error) {
    if (error instanceof MCPBlockedError) {
        console.log('Blocked by policy');
        console.log('Decision:', error.decision);
    }
}
```

### MCPAuthError

Thrown when authentication/authorization fails.

```javascript
try {
    await mcp.detokenize(text, handle);
} catch (error) {
    if (error instanceof MCPAuthError) {
        console.log('Not authorized to detokenize');
    }
}
```

### MCPConnectionError

Thrown when connection to MCP server fails.

```javascript
try {
    await mcp.classify(text);
} catch (error) {
    if (error instanceof MCPConnectionError) {
        console.log('Cannot reach MCP server');
    }
}
```

---

## Configuration

### Environment Variables (Recommended)

Create a `.env` file:

```bash
REACT_APP_MCP_SERVER=https://mcp.yourcompany.com
REACT_APP_MCP_CALLER=my-app
REACT_APP_MCP_REGION=us
```

Then use in your app:

```javascript
const mcp = new MCPClient({
    serverUrl: process.env.REACT_APP_MCP_SERVER,
    caller: process.env.REACT_APP_MCP_CALLER,
    region: process.env.REACT_APP_MCP_REGION
});
```

### CORS Configuration

The MCP server must allow your domain. Contact your administrator to add your domain to the allowed origins.

Server-side (in `.env`):

```bash
CORS_ORIGINS=https://yourapp.com,https://app.yourcompany.com
```

---

## Examples

See `examples/` directory:
- `basic-browser.html` - Simple browser demo
- `react-example.jsx` - React component example

---

## Framework Integration

### Vue.js

```vue
<template>
  <div>
    <input v-model="userInput" @keyup.enter="sendMessage" />
    <button @click="sendMessage">Send</button>
  </div>
</template>

<script>
import { MCPClient } from './mcp-client.js';

export default {
  data() {
    return {
      mcp: null,
      userInput: ''
    };
  },
  created() {
    this.mcp = new MCPClient({
      serverUrl: process.env.VUE_APP_MCP_SERVER,
      caller: 'vue-app'
    });
  },
  methods: {
    async sendMessage() {
      const response = await this.mcp.safeLLMCall(
        this.userInput,
        async (sanitized) => {
          return await this.callLLM(sanitized);
        }
      );
      // Handle response
    }
  }
};
</script>
```

### Angular

```typescript
import { Injectable } from '@angular/core';
import { MCPClient } from './mcp-client';

@Injectable({ providedIn: 'root' })
export class MCPService {
  private mcp: MCPClient;

  constructor() {
    this.mcp = new MCPClient({
      serverUrl: environment.mcpServer,
      caller: 'angular-app'
    });
  }

  async safeLLMCall(input: string, llmFn: (s: string) => Promise<string>): Promise<string> {
    return await this.mcp.safeLLMCall(input, llmFn);
  }
}
```

---

## License

MIT

## Support

- **Documentation**: See main repository README
- **Issues**: https://github.com/sunkencity999/redaction-compliance-MCP/issues
- **Server Setup**: See `DEPLOYMENT.md` in repository
