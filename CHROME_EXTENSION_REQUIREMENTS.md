# 🔐 Chrome Extension - Requirements Specification

## MCP Redaction & Compliance Browser Extension

**Version:** 1.0  
**Target Browsers:** Chrome, Edge, Brave (Chromium-based)  
**Firefox:** Adaptable with minor manifest changes

---

## 📋 Executive Summary

A browser extension that:
1. **Intercepts** LLM API requests (OpenAI, Claude, Gemini)
2. **Redacts** sensitive PII and IP before sending to vendors
3. **Verifies claims** in responses using local LLM
4. **Annotates** responses with verification warnings
5. **Maintains audit logs** of all redactions and verifications

---

## 🎯 Core Features

### 1. Request Interception & Redaction

#### Capabilities:
- **Intercept** all requests to:
  - `api.openai.com/*`
  - `api.anthropic.com/*`
  - `generativelanguage.googleapis.com/*`
  - Configurable custom domains

- **Detect and redact** sensitive information:
  - **PII**: SSN, credit cards, phone numbers, email addresses, names
  - **IP**: Trade secrets, proprietary code, internal URLs, credentials
  - **Custom patterns**: User-defined regex patterns

- **Replace** with tokens:
  - Format: `«token:CATEGORY:id»`
  - Example: `«token:SSN:a1b2», «token:EMAIL:c3d4»`

- **Store mapping** in extension local storage
  - Token → Original value
  - Encrypted with user's master key
  - Auto-expire after configurable time (default: 24h)

#### Flow:
```
User types → Extension intercepts → Redacts PII/IP → Forwards to API
```

---

### 2. Response Detokenization

#### Capabilities:
- **Intercept** responses from LLM vendors
- **Detect** token placeholders in response text
- **Replace** tokens with original values (if allowed by policy)
- **Maintain context** across streaming responses

#### Flow:
```
API response → Extension intercepts → Detokenizes → Shows to user
```

---

### 3. Claim Verification (Local LLM)

#### Capabilities:
- **Extract claims** from LLM responses
- **Verify** using local LLM (Ollama, LM Studio, vLLM)
- **Annotate** response with warnings
- **Support** streaming verification (async)

#### Local LLM Integration:
- **API Endpoint**: `http://localhost:11434/api/chat` (Ollama)
- **Alternative**: LM Studio, vLLM, any OpenAI-compatible local API
- **Models**: llama3, mistral, phi-3, or custom
- **Fallback**: Skip verification if local LLM unavailable

#### Verification Process:
1. **Parse** LLM response into claims
2. **Query** local LLM to verify each claim
3. **Score** reliability (0-100%)
4. **Annotate** response inline with warnings

#### Annotation Format:
```
⚠️ [Confidence: 45%] This claim needs verification.
```

---

## 🏗️ Technical Architecture

### Extension Structure

```
mcp-extension/
├── manifest.json           # Extension manifest (Manifest V3)
├── background/
│   └── service-worker.js   # Main background service worker
├── content/
│   ├── content-script.js   # Injected into web pages
│   └── injector.js         # DOM manipulation
├── popup/
│   ├── popup.html          # Extension popup UI
│   ├── popup.js            # Popup logic
│   └── popup.css           # Popup styles
├── lib/
│   ├── redactor.js         # PII/IP detection & redaction
│   ├── tokenizer.js        # Token management
│   ├── verifier.js         # Claim verification logic
│   ├── storage.js          # Encrypted storage handler
│   └── crypto.js           # Encryption utilities
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── config/
    ├── patterns.json       # Redaction patterns
    └── settings.json       # Default settings
```

---

## 📦 Manifest.json (Manifest V3)

```json
{
  "manifest_version": 3,
  "name": "MCP Redaction & Compliance",
  "version": "1.0.0",
  "description": "Automatically redacts PII/IP and verifies claims using local LLM",
  
  "permissions": [
    "storage",
    "webRequest",
    "scripting",
    "activeTab"
  ],
  
  "host_permissions": [
    "https://api.openai.com/*",
    "https://api.anthropic.com/*",
    "https://generativelanguage.googleapis.com/*",
    "http://localhost:11434/*"
  ],
  
  "background": {
    "service_worker": "background/service-worker.js"
  },
  
  "content_scripts": [
    {
      "matches": [
        "https://chat.openai.com/*",
        "https://claude.ai/*",
        "https://gemini.google.com/*"
      ],
      "js": ["content/content-script.js"],
      "run_at": "document_start"
    }
  ],
  
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  
  "web_accessible_resources": [
    {
      "resources": ["content/injector.js"],
      "matches": ["<all_urls>"]
    }
  ]
}
```

---

## 🔧 Core Components

### 1. Redactor Module (`lib/redactor.js`)

#### Responsibilities:
- Detect PII/IP patterns in text
- Generate unique tokens
- Maintain redaction mappings

#### Key Functions:
```javascript
class Redactor {
  constructor(patterns) {
    this.patterns = patterns;
    this.tokenMap = new Map();
  }
  
  // Detect and redact sensitive information
  redact(text) {
    const redacted = text;
    const tokens = [];
    
    // For each pattern category (SSN, EMAIL, etc.)
    for (const [category, pattern] of this.patterns) {
      const matches = redacted.matchAll(pattern);
      
      for (const match of matches) {
        const token = this.generateToken(category);
        this.tokenMap.set(token, match[0]);
        redacted = redacted.replace(match[0], token);
        tokens.push({ category, token, original: match[0] });
      }
    }
    
    return { redacted, tokens };
  }
  
  // Restore original values from tokens
  detokenize(text, allowedCategories) {
    let restored = text;
    
    for (const [token, original] of this.tokenMap) {
      const category = this.extractCategory(token);
      if (allowedCategories.includes(category)) {
        restored = restored.replace(token, original);
      }
    }
    
    return restored;
  }
  
  generateToken(category) {
    const id = crypto.randomUUID().substring(0, 8);
    return `«token:${category}:${id}»`;
  }
}
```

#### Redaction Patterns:

```javascript
const REDACTION_PATTERNS = {
  // PII Patterns
  SSN: /\b\d{3}-\d{2}-\d{4}\b/g,
  EMAIL: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
  PHONE: /\b(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/g,
  CREDIT_CARD: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g,
  
  // IP Patterns
  INTERNAL_URL: /\b(http|https):\/\/(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|internal\.[a-z]+)\b/gi,
  API_KEY: /\b(sk-[a-zA-Z0-9]{48}|api_key_[a-zA-Z0-9]+)\b/g,
  AWS_KEY: /\b(AKIA[0-9A-Z]{16})\b/g,
  PRIVATE_IP: /\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b/g,
  
  // Custom patterns (user-configurable)
  COMPANY_NAME: /\bAcme Corp\b/gi,  // Example
  PROJECT_CODE: /\bPROJ-\d{4}\b/g   // Example
};
```

---

### 2. Verifier Module (`lib/verifier.js`)

#### Responsibilities:
- Connect to local LLM
- Extract claims from responses
- Verify claims
- Generate annotations

#### Key Functions:
```javascript
class ClaimVerifier {
  constructor(localLLMEndpoint) {
    this.endpoint = localLLMEndpoint || 'http://localhost:11434/api/chat';
    this.model = 'llama3';
  }
  
  // Verify claims in text using local LLM
  async verifyResponse(text) {
    try {
      // 1. Extract claims
      const claims = await this.extractClaims(text);
      
      // 2. Verify each claim
      const verifications = [];
      for (const claim of claims) {
        const result = await this.verifyClaim(claim);
        verifications.push(result);
      }
      
      // 3. Annotate text
      return this.annotateText(text, verifications);
      
    } catch (error) {
      console.warn('Verification failed:', error);
      return text; // Return original if verification fails
    }
  }
  
  async extractClaims(text) {
    const prompt = `Extract factual claims from this text. 
Return as JSON array of objects with 'claim' and 'location' (character position).

Text: """${text}"""`;

    const response = await this.queryLLM(prompt);
    return JSON.parse(response);
  }
  
  async verifyClaim(claim) {
    const prompt = `Assess the verifiability of this claim. 
Rate confidence 0-100% and explain briefly.

Claim: "${claim}"

Return JSON: {"confidence": <number>, "reasoning": "<string>"}`;

    const response = await this.queryLLM(prompt);
    return JSON.parse(response);
  }
  
  async queryLLM(prompt) {
    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: this.model,
        messages: [{ role: 'user', content: prompt }],
        stream: false
      })
    });
    
    const data = await response.json();
    return data.message.content;
  }
  
  annotateText(text, verifications) {
    let annotated = text;
    
    // Sort verifications by confidence (lowest first = most concerning)
    verifications.sort((a, b) => a.confidence - b.confidence);
    
    for (const verification of verifications) {
      if (verification.confidence < 70) {
        const annotation = `⚠️ [Confidence: ${verification.confidence}%] ${verification.reasoning}`;
        // Insert annotation near the claim
        // Implementation depends on text structure
      }
    }
    
    return annotated;
  }
}
```

---

### 3. Service Worker (`background/service-worker.js`)

#### Responsibilities:
- Intercept network requests
- Apply redaction before forwarding
- Detokenize responses
- Trigger claim verification

#### Implementation:
```javascript
// Intercept requests to LLM APIs
chrome.webRequest.onBeforeRequest.addListener(
  async (details) => {
    if (details.method !== 'POST') return;
    
    // Parse request body
    const requestData = parseRequestBody(details.requestBody);
    
    // Extract messages/content
    const messages = extractMessages(requestData);
    
    // Redact sensitive information
    const redactor = new Redactor(REDACTION_PATTERNS);
    const redactedMessages = messages.map(msg => {
      const { redacted, tokens } = redactor.redact(msg.content);
      return { ...msg, content: redacted };
    });
    
    // Store tokens for later detokenization
    await saveTokenMapping(details.requestId, redactor.tokenMap);
    
    // Update request with redacted content
    updateRequestBody(requestData, redactedMessages);
    
    // Log for audit
    logRedaction(details.url, tokens);
    
    return { requestBody: requestData };
  },
  {
    urls: [
      'https://api.openai.com/v1/chat/completions',
      'https://api.anthropic.com/v1/messages',
      'https://generativelanguage.googleapis.com/*'
    ]
  },
  ['requestBody']
);

// Intercept responses
chrome.webRequest.onCompleted.addListener(
  async (details) => {
    // Get stored token mapping
    const tokenMap = await getTokenMapping(details.requestId);
    
    if (!tokenMap) return;
    
    // Fetch response (requires content script cooperation)
    const response = await getResponseBody(details.requestId);
    
    // Detokenize
    const redactor = new Redactor();
    redactor.tokenMap = tokenMap;
    const detokenized = redactor.detokenize(response, ['PII', 'OPS']);
    
    // Verify claims (async, non-blocking)
    const verifier = new ClaimVerifier();
    const verified = await verifier.verifyResponse(detokenized);
    
    // Inject verified/annotated response back to page
    injectResponse(details.tabId, verified);
    
    // Clean up token mapping
    cleanupTokenMapping(details.requestId);
  },
  {
    urls: [
      'https://api.openai.com/v1/chat/completions',
      'https://api.anthropic.com/v1/messages',
      'https://generativelanguage.googleapis.com/*'
    ]
  }
);
```

---

### 4. Content Script (`content/content-script.js`)

#### Responsibilities:
- Monitor DOM for chat interfaces
- Extract user messages before submission
- Inject annotated responses
- Handle streaming responses

#### Implementation:
```javascript
// Inject into page context to intercept fetch/XHR
(function() {
  const originalFetch = window.fetch;
  
  window.fetch = async function(...args) {
    const [url, options] = args;
    
    // Check if this is an LLM API call
    if (isLLMEndpoint(url)) {
      // Send to background for processing
      const processed = await chrome.runtime.sendMessage({
        type: 'INTERCEPT_REQUEST',
        url,
        body: options.body
      });
      
      // Use processed body
      options.body = processed.body;
    }
    
    // Make actual request
    const response = await originalFetch.apply(this, args);
    
    // Intercept response
    if (isLLMEndpoint(url)) {
      const cloned = response.clone();
      const text = await cloned.text();
      
      // Send to background for detokenization & verification
      const processed = await chrome.runtime.sendMessage({
        type: 'PROCESS_RESPONSE',
        url,
        body: text
      });
      
      // Return modified response
      return new Response(processed.body, {
        status: response.status,
        headers: response.headers
      });
    }
    
    return response;
  };
})();
```

---

### 5. Storage Module (`lib/storage.js`)

#### Responsibilities:
- Encrypted storage of token mappings
- User settings
- Audit logs

#### Implementation:
```javascript
class SecureStorage {
  constructor() {
    this.masterKey = null;
  }
  
  async initialize(password) {
    // Derive encryption key from password
    this.masterKey = await this.deriveKey(password);
  }
  
  async saveTokenMapping(requestId, tokenMap) {
    const encrypted = await this.encrypt(JSON.stringify([...tokenMap]));
    
    await chrome.storage.local.set({
      [`tokens_${requestId}`]: {
        data: encrypted,
        timestamp: Date.now(),
        expiresAt: Date.now() + (24 * 60 * 60 * 1000) // 24h
      }
    });
  }
  
  async getTokenMapping(requestId) {
    const result = await chrome.storage.local.get(`tokens_${requestId}`);
    const stored = result[`tokens_${requestId}`];
    
    if (!stored || Date.now() > stored.expiresAt) {
      return null;
    }
    
    const decrypted = await this.decrypt(stored.data);
    return new Map(JSON.parse(decrypted));
  }
  
  async encrypt(data) {
    // Use Web Crypto API
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.masterKey,
      new TextEncoder().encode(data)
    );
    
    return {
      iv: Array.from(iv),
      data: Array.from(new Uint8Array(encrypted))
    };
  }
  
  async decrypt(encrypted) {
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: new Uint8Array(encrypted.iv) },
      this.masterKey,
      new Uint8Array(encrypted.data)
    );
    
    return new TextDecoder().decode(decrypted);
  }
  
  async deriveKey(password) {
    const salt = await this.getSalt();
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      'PBKDF2',
      false,
      ['deriveBits', 'deriveKey']
    );
    
    return await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt,
        iterations: 100000,
        hash: 'SHA-256'
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
  }
}
```

---

## 🎨 User Interface

### Popup UI Features:

1. **Status Indicator**
   - 🟢 Active & Redacting
   - 🟡 Active but LLM verification unavailable
   - 🔴 Disabled

2. **Statistics Dashboard**
   - Redactions today: X
   - Claims verified: Y
   - Warnings issued: Z

3. **Settings**
   - Enable/disable redaction
   - Configure patterns
   - Local LLM endpoint
   - Verification threshold
   - Auto-expire tokens (hours)

4. **Audit Log Viewer**
   - Recent redactions
   - Timestamp, category, count
   - Export to CSV

---

## 🔐 Security Considerations

### 1. Token Storage
- Encrypted with user-provided master password
- Auto-expire after configured duration
- Never sent to external servers

### 2. Local LLM Only
- Verification happens entirely locally
- No sensitive data sent to cloud
- Fallback: Skip verification if local LLM unavailable

### 3. Permissions
- Request minimal permissions
- Explain each permission in installation
- Optional: Allow user to grant/deny per-domain

### 4. Audit Trail
- Log all redactions (encrypted)
- Log all verifications
- Export for compliance review

---

## 📊 Performance Requirements

### 1. Redaction Performance
- **Latency**: < 50ms added to request
- **Throughput**: Handle 100+ messages/minute
- **Memory**: < 10MB RAM for token storage

### 2. Verification Performance
- **Async**: Don't block response rendering
- **Timeout**: 5s max for verification
- **Fallback**: Show original if timeout
- **Caching**: Cache verification results

---

## 🧪 Testing Requirements

### 1. Unit Tests
- Redaction pattern matching
- Token generation/mapping
- Encryption/decryption
- Claim extraction

### 2. Integration Tests
- Request interception
- Response modification
- Local LLM communication
- Storage operations

### 3. Manual Testing
- Test on chat.openai.com
- Test on claude.ai
- Test on gemini.google.com
- Test with streaming responses
- Test with large messages

---

## 📚 Dependencies

### Required:
- **Manifest V3** (Chrome Extension API)
- **Web Crypto API** (encryption)
- **Local LLM Server** (Ollama, LM Studio, or compatible)

### Optional:
- **Chart.js** (statistics visualization in popup)
- **Highlight.js** (syntax highlighting for logs)

---

## 🚀 Development Roadmap

### Phase 1: MVP (Week 1-2)
- ✅ Basic manifest and structure
- ✅ Request/response interception
- ✅ PII redaction (SSN, email, phone)
- ✅ Token storage
- ✅ Basic popup UI

### Phase 2: Advanced Redaction (Week 3)
- ✅ IP redaction (API keys, internal URLs)
- ✅ Custom pattern configuration
- ✅ Detokenization logic
- ✅ Encrypted storage

### Phase 3: Local LLM Integration (Week 4)
- ✅ Ollama integration
- ✅ Claim extraction
- ✅ Verification logic
- ✅ Response annotation

### Phase 4: Polish (Week 5)
- ✅ Statistics dashboard
- ✅ Audit log viewer
- ✅ Settings panel
- ✅ Export functionality

### Phase 5: Testing & Release (Week 6)
- ✅ Comprehensive testing
- ✅ Documentation
- ✅ Chrome Web Store submission
- ✅ User guide

---

## 📝 Installation & Usage

### For Users:

1. **Install Extension**
   - Download from Chrome Web Store
   - Or load unpacked (developer mode)

2. **Configure Local LLM**
   - Install Ollama: `curl https://ollama.ai/install.sh | sh`
   - Pull model: `ollama pull llama3`
   - Start server: `ollama serve`

3. **Set Master Password**
   - Open extension popup
   - Set password for encryption
   - Password never leaves your computer

4. **Use Normally**
   - Chat with OpenAI/Claude/Gemini as usual
   - Extension automatically redacts sensitive info
   - See verification warnings inline

### For Developers:

```bash
# Clone repository
git clone https://github.com/yourorg/mcp-chrome-extension

# Install dependencies (if any build step needed)
npm install

# Load in Chrome
# 1. Open chrome://extensions
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select extension directory

# Development
npm run build     # If using bundler
npm run test      # Run tests
```

---

## 🆘 Support & Troubleshooting

### Common Issues:

1. **"Local LLM not responding"**
   - Check Ollama is running: `ollama list`
   - Verify endpoint: `curl http://localhost:11434/api/tags`

2. **"Redaction not working"**
   - Check extension is enabled
   - Verify permissions granted
   - Check browser console for errors

3. **"Tokens not detokenizing"**
   - Check master password is set
   - Verify tokens haven't expired
   - Check storage quota not exceeded

---

## 📄 License

MIT License - See LICENSE file

---

## 🤝 Contributing

Contributions welcome! See CONTRIBUTING.md for guidelines.

---

**This specification provides a complete blueprint for implementing the MCP Redaction & Compliance Chrome Extension.** 🚀
