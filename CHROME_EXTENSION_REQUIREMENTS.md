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
- **Verify** using company-hosted local LLM (FastAPI endpoint)
- **Annotate** response with warnings
- **Support** streaming verification (async)

#### Local LLM Integration:
- **Default**: Company-hosted FastAPI endpoint (OpenAI-compatible)
  - **API Endpoint**: `http://llm.internal.company.com/v1/chat/completions`
  - Centrally managed by IT/ML team
  - Consistent model versions across organization
  - Optional authentication via API key or OAuth
- **Alternative Options**:
  - **Ollama**: `http://localhost:11434/api/chat` (user-installed)
  - **LM Studio**: `http://localhost:1234/v1/chat/completions`
  - **vLLM**: Any OpenAI-compatible endpoint
- **Models**: Company-approved models or user-selected (llama3, mistral, phi-3, etc.)
- **Fallback**: Skip verification if LLM endpoint unavailable

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
    "http://llm.internal.company.com/*",
    "https://llm.internal.company.com/*",
    "http://localhost:*"
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
  constructor(config = {}) {
    // Default: Company-hosted FastAPI endpoint (OpenAI-compatible)
    this.endpoint = config.endpoint || 'http://llm.internal.company.com/v1/chat/completions';
    this.model = config.model || 'company-approved-model';
    this.apiKey = config.apiKey || null;  // Optional for internal endpoints
    this.endpointType = config.type || 'openai-compatible';  // or 'ollama'
  }
  
  // Verify claims in text using local/company LLM
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
    const headers = { 'Content-Type': 'application/json' };
    
    // Add API key if configured (for authenticated endpoints)
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }
    
    // Build request body based on endpoint type
    const requestBody = this.endpointType === 'ollama' 
      ? {
          model: this.model,
          messages: [{ role: 'user', content: prompt }],
          stream: false
        }
      : {
          // OpenAI-compatible format (FastAPI default)
          model: this.model,
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.3,
          max_tokens: 500
        };
    
    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      throw new Error(`LLM API error: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // Parse response based on endpoint type
    if (this.endpointType === 'ollama') {
      return data.message.content;
    } else {
      // OpenAI-compatible format
      return data.choices[0].message.content;
    }
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

## 📖 **VERIFIER MODULE - Complete Standalone Specification**

> **This section provides complete specifications for developing the Verifier module as a standalone component**

### Module Overview

The Claim Verifier is a self-contained module that uses an LLM to extract and verify factual claims in text responses. It can be used standalone or integrated into the Chrome extension.

---

### System Requirements

#### Dependencies:
```json
{
  "required": [
    "fetch API (native)",
    "JSON.parse/stringify (native)"
  ],
  "optional": [
    "TypeScript for type safety",
    "Jest for testing"
  ]
}
```

#### LLM Requirements:
- **Model Type**: Any instruction-following LLM (7B+ parameters recommended)
- **Context Window**: Minimum 4096 tokens
- **API Format**: OpenAI-compatible or Ollama
- **Capabilities**: JSON output, instruction following, reasoning

#### Recommended Models:
- **Production**: Llama 3 70B, Mixtral 8x7B, GPT-4
- **Development**: Llama 3 8B, Mistral 7B, Phi-3 Medium
- **Testing**: Llama 3 8B, GPT-3.5-turbo

---

### Configuration Schema

```javascript
const VerifierConfig = {
  // LLM Endpoint Configuration
  endpoint: {
    type: 'string',
    required: true,
    default: 'http://llm.internal.company.com/v1/chat/completions',
    description: 'LLM API endpoint URL'
  },
  
  // Endpoint Type
  endpointType: {
    type: 'enum',
    values: ['openai-compatible', 'ollama'],
    default: 'openai-compatible',
    description: 'API format type'
  },
  
  // Model Name
  model: {
    type: 'string',
    required: true,
    default: 'company-approved-model',
    description: 'LLM model identifier'
  },
  
  // Authentication
  apiKey: {
    type: 'string',
    required: false,
    default: null,
    description: 'API key for authenticated endpoints'
  },
  
  // Verification Thresholds
  confidenceThreshold: {
    type: 'number',
    min: 0,
    max: 100,
    default: 70,
    description: 'Minimum confidence to skip warning'
  },
  
  // Timeouts
  timeout: {
    type: 'number',
    default: 5000,
    description: 'Request timeout in milliseconds'
  },
  
  // LLM Parameters
  temperature: {
    type: 'number',
    min: 0,
    max: 1,
    default: 0.3,
    description: 'LLM temperature (lower = more deterministic)'
  },
  
  maxTokens: {
    type: 'number',
    default: 500,
    description: 'Maximum tokens in LLM response'
  },
  
  // Retry Configuration
  maxRetries: {
    type: 'number',
    default: 2,
    description: 'Maximum retry attempts on failure'
  },
  
  retryDelay: {
    type: 'number',
    default: 1000,
    description: 'Delay between retries in milliseconds'
  }
};
```

---

### System Prompts

#### 1. Claim Extraction Prompt

**Purpose**: Extract factual claims from text that can be verified

**System Prompt**:
```
You are a precise claim extraction system. Your task is to identify factual claims in text that can be objectively verified or assessed.

A factual claim is a statement that:
1. Makes a specific assertion about the world
2. Can be evaluated as true, false, or uncertain
3. Is not purely subjective opinion
4. Contains verifiable information

Extract ONLY factual claims. Ignore:
- Subjective opinions ("this is beautiful")
- Questions
- Commands
- Greetings or pleasantries
- Obvious tautologies

For each claim:
1. Extract the exact text of the claim
2. Note its character position in the original text
3. Classify the claim type (statistical, historical, technical, current_event, etc.)

Return ONLY valid JSON, no other text.
```

**User Prompt Template**:
```javascript
const claimExtractionPrompt = (text) => `Extract all factual claims from the following text.

Text: """
${text}
"""

Return a JSON array of objects with this exact format:
[
  {
    "claim": "exact claim text",
    "position": {
      "start": 0,
      "end": 50
    },
    "type": "statistical|historical|technical|current_event|general",
    "context": "surrounding context if needed for clarity"
  }
]

If no factual claims are found, return an empty array: []

JSON output:`;
```

**Example Input**:
```
"The Earth has a population of 8 billion people. Paris is the capital of France. 
I think the weather is nice today."
```

**Expected Output**:
```json
[
  {
    "claim": "The Earth has a population of 8 billion people",
    "position": {"start": 0, "end": 48},
    "type": "statistical",
    "context": "global population"
  },
  {
    "claim": "Paris is the capital of France",
    "position": {"start": 50, "end": 80},
    "type": "general",
    "context": "geography fact"
  }
]
```

---

#### 2. Claim Verification Prompt

**Purpose**: Assess the verifiability and confidence level of a claim

**System Prompt**:
```
You are a rigorous claim verification system. Your task is to assess the verifiability of factual claims.

For each claim, evaluate:

1. VERIFIABILITY (0-100%):
   - 90-100%: Well-established, widely documented facts
   - 70-89%: Likely accurate, can be verified with standard sources
   - 50-69%: Uncertain, conflicting sources or limited information
   - 30-49%: Questionable, likely incorrect or outdated
   - 0-29%: False or highly misleading

2. REASONING:
   - Explain your confidence assessment briefly (1-2 sentences)
   - Mention key factors affecting verifiability
   - Note if claim requires time-sensitive or context-specific validation

Important guidelines:
- Be conservative: when uncertain, lower the confidence score
- Consider recency: older claims may be outdated
- Note specificity: vague claims get lower confidence
- Flag impossibility: claims that violate known facts get very low scores

Return ONLY valid JSON, no other text.
```

**User Prompt Template**:
```javascript
const claimVerificationPrompt = (claim) => `Assess the verifiability of this claim.

Claim: "${claim.claim}"
Type: ${claim.type}
Context: ${claim.context || 'general'}

Evaluate:
1. How verifiable is this claim? (0-100%)
2. What factors affect its verifiability?
3. What would be needed to verify it?

Return JSON in this exact format:
{
  "confidence": <number 0-100>,
  "reasoning": "<brief explanation>",
  "verifiability_factors": [
    "<factor 1>",
    "<factor 2>"
  ],
  "suggested_sources": [
    "<source type 1>",
    "<source type 2>"
  ],
  "red_flags": [
    "<concern if any>"
  ],
  "requires_update_check": <boolean>
}

JSON output:`;
```

**Example Input**:
```json
{
  "claim": "The Earth has a population of 8 billion people",
  "type": "statistical",
  "context": "global population"
}
```

**Expected Output**:
```json
{
  "confidence": 85,
  "reasoning": "Global population estimates are well-documented by UN and other international organizations. The 8 billion milestone was reached in late 2022. This is a recent, verifiable statistic.",
  "verifiability_factors": [
    "Official UN population data available",
    "Multiple international organizations track this",
    "Recently crossed 8 billion threshold (Nov 2022)"
  ],
  "suggested_sources": [
    "UN Population Division",
    "World Bank population data",
    "National census bureaus"
  ],
  "red_flags": [],
  "requires_update_check": true
}
```

---

### Complete Implementation

```javascript
/**
 * ClaimVerifier - Standalone claim verification module
 * 
 * @class ClaimVerifier
 * @description Extracts and verifies factual claims using an LLM
 */
class ClaimVerifier {
  /**
   * @param {Object} config - Configuration object
   * @param {string} config.endpoint - LLM API endpoint URL
   * @param {string} config.model - Model identifier
   * @param {string} [config.apiKey] - Optional API key
   * @param {string} [config.endpointType='openai-compatible'] - API format
   * @param {number} [config.confidenceThreshold=70] - Minimum confidence (0-100)
   * @param {number} [config.timeout=5000] - Request timeout (ms)
   * @param {number} [config.temperature=0.3] - LLM temperature
   * @param {number} [config.maxTokens=500] - Max response tokens
   * @param {number} [config.maxRetries=2] - Max retry attempts
   * @param {number} [config.retryDelay=1000] - Retry delay (ms)
   */
  constructor(config = {}) {
    // Validate required configuration
    if (!config.endpoint) {
      throw new Error('ClaimVerifier: endpoint is required');
    }
    if (!config.model) {
      throw new Error('ClaimVerifier: model is required');
    }
    
    // LLM Configuration
    this.endpoint = config.endpoint;
    this.model = config.model;
    this.apiKey = config.apiKey || null;
    this.endpointType = config.endpointType || 'openai-compatible';
    
    // Verification Parameters
    this.confidenceThreshold = config.confidenceThreshold || 70;
    this.timeout = config.timeout || 5000;
    this.temperature = config.temperature || 0.3;
    this.maxTokens = config.maxTokens || 500;
    
    // Retry Configuration
    this.maxRetries = config.maxRetries || 2;
    this.retryDelay = config.retryDelay || 1000;
    
    // Statistics
    this.stats = {
      claimsExtracted: 0,
      claimsVerified: 0,
      warnings: Issued: 0,
      errors: 0,
      avgConfidence: 0
    };
  }
  
  /**
   * Main entry point: Verify all claims in text
   * @param {string} text - Text to analyze
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} Verification result
   */
  async verifyResponse(text, options = {}) {
    const startTime = Date.now();
    
    try {
      // 1. Extract claims from text
      const claims = await this.extractClaims(text);
      this.stats.claimsExtracted += claims.length;
      
      if (claims.length === 0) {
        return {
          original: text,
          annotated: text,
          claims: [],
          warnings: [],
          metadata: {
            processingTime: Date.now() - startTime,
            claimCount: 0
          }
        };
      }
      
      // 2. Verify each claim
      const verifications = [];
      for (const claim of claims) {
        const verification = await this.verifyClaim(claim);
        verifications.push({
          ...claim,
          verification
        });
        this.stats.claimsVerified++;
      }
      
      // 3. Calculate statistics
      const avgConfidence = verifications.reduce((sum, v) => 
        sum + v.verification.confidence, 0) / verifications.length;
      this.stats.avgConfidence = avgConfidence;
      
      // 4. Identify warnings (low confidence claims)
      const warnings = verifications.filter(v => 
        v.verification.confidence < this.confidenceThreshold
      );
      this.stats.warningsIssued += warnings.length;
      
      // 5. Annotate text with warnings
      const annotated = this.annotateText(text, verifications);
      
      return {
        original: text,
        annotated,
        claims: verifications,
        warnings: warnings.map(w => ({
          claim: w.claim,
          confidence: w.verification.confidence,
          reasoning: w.verification.reasoning,
          position: w.position
        })),
        metadata: {
          processingTime: Date.now() - startTime,
          claimCount: claims.length,
          warningCount: warnings.length,
          avgConfidence: Math.round(avgConfidence)
        }
      };
      
    } catch (error) {
      this.stats.errors++;
      console.error('ClaimVerifier: Verification failed:', error);
      
      // Return original text on error
      return {
        original: text,
        annotated: text,
        claims: [],
        warnings: [],
        error: error.message,
        metadata: {
          processingTime: Date.now() - startTime,
          claimCount: 0
        }
      };
    }
  }
  
  /**
   * Extract factual claims from text
   * @param {string} text - Text to analyze
   * @returns {Promise<Array>} Array of claim objects
   */
  async extractClaims(text) {
    const systemPrompt = `You are a precise claim extraction system. Extract factual claims that can be objectively verified.

A factual claim:
- Makes a specific assertion
- Can be evaluated as true/false/uncertain
- Is not purely subjective opinion
- Contains verifiable information

Return ONLY valid JSON array, no other text.`;

    const userPrompt = `Extract all factual claims from this text:

"""
${text}
"""

Return JSON array:
[
  {
    "claim": "exact claim text",
    "position": {"start": 0, "end": 50},
    "type": "statistical|historical|technical|current_event|general",
    "context": "surrounding context"
  }
]

If no claims, return: []

JSON output:`;

    try {
      const response = await this.queryLLM(systemPrompt, userPrompt);
      const claims = this.parseJSON(response);
      
      if (!Array.isArray(claims)) {
        throw new Error('LLM did not return an array');
      }
      
      return claims;
    } catch (error) {
      console.warn('ClaimVerifier: Claim extraction failed:', error);
      return [];
    }
  }
  
  /**
   * Verify a single claim
   * @param {Object} claim - Claim object
   * @returns {Promise<Object>} Verification result
   */
  async verifyClaim(claim) {
    const systemPrompt = `You are a rigorous claim verification system. Assess verifiability of claims.

Scoring (0-100%):
- 90-100%: Well-established facts
- 70-89%: Likely accurate
- 50-69%: Uncertain
- 30-49%: Questionable
- 0-29%: False or misleading

Be conservative: when uncertain, lower the score.

Return ONLY valid JSON, no other text.`;

    const userPrompt = `Assess this claim:

Claim: "${claim.claim}"
Type: ${claim.type}
Context: ${claim.context || 'general'}

Return JSON:
{
  "confidence": <0-100>,
  "reasoning": "<brief explanation>",
  "verifiability_factors": ["<factor>"],
  "suggested_sources": ["<source>"],
  "red_flags": ["<concern if any>"],
  "requires_update_check": <boolean>
}

JSON output:`;

    try {
      const response = await this.queryLLM(systemPrompt, userPrompt);
      const verification = this.parseJSON(response);
      
      // Validate verification structure
      if (typeof verification.confidence !== 'number') {
        throw new Error('Invalid confidence score');
      }
      
      return verification;
    } catch (error) {
      console.warn('ClaimVerifier: Verification failed for claim:', claim.claim, error);
      
      // Return default verification on error
      return {
        confidence: 50,
        reasoning: 'Verification failed - treating as uncertain',
        verifiability_factors: [],
        suggested_sources: [],
        red_flags: ['Verification system error'],
        requires_update_check: false
      };
    }
  }
  
  /**
   * Query the LLM with retry logic
   * @param {string} systemPrompt - System prompt
   * @param {string} userPrompt - User prompt
   * @returns {Promise<string>} LLM response
   */
  async queryLLM(systemPrompt, userPrompt) {
    let lastError;
    
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const headers = { 'Content-Type': 'application/json' };
        
        // Add API key if configured
        if (this.apiKey) {
          headers['Authorization'] = `Bearer ${this.apiKey}`;
        }
        
        // Build request body
        const requestBody = this.endpointType === 'ollama'
          ? {
              model: this.model,
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt }
              ],
              stream: false,
              options: {
                temperature: this.temperature
              }
            }
          : {
              model: this.model,
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt }
              ],
              temperature: this.temperature,
              max_tokens: this.maxTokens
            };
        
        // Make request with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        
        const response = await fetch(this.endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify(requestBody),
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Extract content based on endpoint type
        const content = this.endpointType === 'ollama'
          ? data.message.content
          : data.choices[0].message.content;
        
        return content;
        
      } catch (error) {
        lastError = error;
        
        // Don't retry on certain errors
        if (error.name === 'AbortError') {
          throw new Error(`Request timeout after ${this.timeout}ms`);
        }
        
        // Wait before retry
        if (attempt < this.maxRetries) {
          await this.sleep(this.retryDelay * (attempt + 1));
        }
      }
    }
    
    throw new Error(`LLM request failed after ${this.maxRetries} retries: ${lastError.message}`);
  }
  
  /**
   * Parse JSON with error handling
   * @param {string} text - JSON string
   * @returns {Object|Array} Parsed JSON
   */
  parseJSON(text) {
    // Try to extract JSON from markdown code blocks
    const jsonMatch = text.match(/```(?:json)?\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*```/);
    const jsonText = jsonMatch ? jsonMatch[1] : text;
    
    try {
      return JSON.parse(jsonText.trim());
    } catch (error) {
      // Try to find JSON object/array in the text
      const objMatch = jsonText.match(/\{[\s\S]*\}/);
      const arrMatch = jsonText.match(/\[[\s\S]*\]/);
      
      if (objMatch) {
        return JSON.parse(objMatch[0]);
      } else if (arrMatch) {
        return JSON.parse(arrMatch[0]);
      }
      
      throw new Error(`Failed to parse JSON: ${error.message}`);
    }
  }
  
  /**
   * Annotate text with verification warnings
   * @param {string} text - Original text
   * @param {Array} verifications - Verification results
   * @returns {string} Annotated text
   */
  annotateText(text, verifications) {
    // Sort by position (reverse order for insertion)
    const sorted = [...verifications].sort((a, b) => 
      b.position.start - a.position.start
    );
    
    let annotated = text;
    
    for (const item of sorted) {
      if (item.verification.confidence < this.confidenceThreshold) {
        const warning = `\n\n⚠️ [Confidence: ${item.verification.confidence}%] ${item.verification.reasoning}\n`;
        
        // Insert warning after the claim
        const insertPos = item.position.end;
        annotated = annotated.slice(0, insertPos) + warning + annotated.slice(insertPos);
      }
    }
    
    return annotated;
  }
  
  /**
   * Get verification statistics
   * @returns {Object} Statistics object
   */
  getStats() {
    return { ...this.stats };
  }
  
  /**
   * Reset statistics
   */
  resetStats() {
    this.stats = {
      claimsExtracted: 0,
      claimsVerified: 0,
      warningsIssued: 0,
      errors: 0,
      avgConfidence: 0
    };
  }
  
  /**
   * Sleep utility
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise}
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export for standalone use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ClaimVerifier;
}
```

---

### Usage Examples

#### Basic Usage:
```javascript
// Initialize verifier
const verifier = new ClaimVerifier({
  endpoint: 'http://llm.internal.company.com/v1/chat/completions',
  model: 'llama3-70b',
  confidenceThreshold: 70
});

// Verify text
const text = "The Earth has 8 billion people. The Moon is made of cheese.";
const result = await verifier.verifyResponse(text);

console.log(result.annotated);
console.log(`Found ${result.warnings.length} warnings`);
```

#### With Authentication:
```javascript
const verifier = new ClaimVerifier({
  endpoint: 'https://api.company.com/llm/v1/chat/completions',
  model: 'gpt-4',
  apiKey: process.env.LLM_API_KEY,
  confidenceThreshold: 80
});
```

#### Using Ollama:
```javascript
const verifier = new ClaimVerifier({
  endpoint: 'http://localhost:11434/api/chat',
  model: 'llama3',
  endpointType: 'ollama',
  confidenceThreshold: 70
});
```

#### Batch Verification:
```javascript
const texts = [
  "Paris is in France.",
  "The sun revolves around the Earth.",
  "Water boils at 100°C at sea level."
];

const results = await Promise.all(
  texts.map(text => verifier.verifyResponse(text))
);

console.log('Statistics:', verifier.getStats());
```

---

### Error Handling

```javascript
try {
  const result = await verifier.verifyResponse(text);
  
  if (result.error) {
    console.error('Verification failed:', result.error);
    // Use original text
    displayText(result.original);
  } else {
    // Use annotated text with warnings
    displayText(result.annotated);
  }
} catch (error) {
  console.error('Fatal error:', error);
  // Fallback to original text
  displayText(text);
}
```

---

### Testing

#### Unit Tests:
```javascript
describe('ClaimVerifier', () => {
  let verifier;
  
  beforeEach(() => {
    verifier = new ClaimVerifier({
      endpoint: 'http://test-llm.local/v1/chat/completions',
      model: 'test-model'
    });
  });
  
  test('should extract claims from text', async () => {
    const text = "The Earth is round. Water is wet.";
    const claims = await verifier.extractClaims(text);
    
    expect(claims).toBeInstanceOf(Array);
    expect(claims.length).toBeGreaterThan(0);
  });
  
  test('should verify claim confidence', async () => {
    const claim = {
      claim: "The Earth is round",
      type: "general",
      position: { start: 0, end: 18 }
    };
    
    const verification = await verifier.verifyClaim(claim);
    
    expect(verification.confidence).toBeGreaterThanOrEqual(0);
    expect(verification.confidence).toBeLessThanOrEqual(100);
    expect(verification.reasoning).toBeTruthy();
  });
  
  test('should annotate low-confidence claims', async () => {
    const text = "The Moon is made of cheese.";
    const result = await verifier.verifyResponse(text);
    
    expect(result.warnings.length).toBeGreaterThan(0);
    expect(result.annotated).toContain('⚠️');
  });
  
  test('should handle verification errors gracefully', async () => {
    // Simulate network error
    const badVerifier = new ClaimVerifier({
      endpoint: 'http://invalid-endpoint',
      model: 'test'
    });
    
    const result = await badVerifier.verifyResponse("Test text");
    
    expect(result.original).toBe("Test text");
    expect(result.error).toBeTruthy();
  });
});
```

---

### Standalone Deployment

#### As Node.js Module:
```javascript
// verifier.js
const ClaimVerifier = require('./claim-verifier');

const verifier = new ClaimVerifier({
  endpoint: process.env.LLM_ENDPOINT,
  model: process.env.LLM_MODEL,
  apiKey: process.env.LLM_API_KEY
});

module.exports = verifier;
```

#### As REST API:
```javascript
// server.js
const express = require('express');
const ClaimVerifier = require('./claim-verifier');

const app = express();
app.use(express.json());

const verifier = new ClaimVerifier({
  endpoint: process.env.LLM_ENDPOINT,
  model: process.env.LLM_MODEL
});

app.post('/verify', async (req, res) => {
  try {
    const { text } = req.body;
    const result = await verifier.verifyResponse(text);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/stats', (req, res) => {
  res.json(verifier.getStats());
});

app.listen(3000, () => {
  console.log('Verifier API running on port 3000');
});
```

---

### Performance Optimization

#### Caching:
```javascript
class CachedClaimVerifier extends ClaimVerifier {
  constructor(config) {
    super(config);
    this.cache = new Map();
    this.cacheTimeout = config.cacheTimeout || 3600000; // 1 hour
  }
  
  async verifyClaim(claim) {
    const cacheKey = claim.claim.toLowerCase();
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.result;
    }
    
    const result = await super.verifyClaim(claim);
    this.cache.set(cacheKey, {
      result,
      timestamp: Date.now()
    });
    
    return result;
  }
}
```

#### Parallel Verification:
```javascript
async verifyResponseParallel(text) {
  const claims = await this.extractClaims(text);
  
  // Verify all claims in parallel
  const verifications = await Promise.all(
    claims.map(claim => this.verifyClaim(claim))
  );
  
  // Continue with annotation...
}
```

---

**End of Standalone Verifier Specification**

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
   - **LLM Configuration**:
     - Endpoint URL (default: company FastAPI server)
     - Endpoint type: OpenAI-compatible (default) or Ollama
     - Model name
     - API key (optional, for authenticated endpoints)
   - Verification confidence threshold (0-100%)
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

### 2. Company/Local LLM Only
- Verification uses company-hosted or local LLM
- No sensitive data sent to public cloud
- Options: Company FastAPI endpoint (default) or user-installed Ollama
- Fallback: Skip verification if LLM endpoint unavailable

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
- **LLM Endpoint**: Company-hosted FastAPI server (default) or Ollama/LM Studio

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

### Phase 3: LLM Integration (Week 4)
- ✅ Company FastAPI endpoint integration (primary)
- ✅ Ollama support (alternative)
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

2. **Configure LLM Endpoint**
   
   **Option A: Company FastAPI Server (Default - Recommended)**
   - URL: `http://llm.internal.company.com/v1/chat/completions`
   - Pre-configured in extension settings
   - Centrally managed by IT team
   - No additional setup needed
   - May require company VPN connection
   
   **Option B: Ollama (Alternative - User-managed)**
   - Install Ollama: `curl https://ollama.ai/install.sh | sh`
   - Pull model: `ollama pull llama3`
   - Start server: `ollama serve`
   - Change endpoint in settings to: `http://localhost:11434/api/chat`
   - Change type to: "Ollama"

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

1. **"LLM endpoint not responding"**
   
   **If using company FastAPI server:**
   - Check VPN connection (if required)
   - Verify endpoint URL: `curl http://llm.internal.company.com/health`
   - Contact IT if endpoint is down
   
   **If using Ollama:**
   - Check Ollama is running: `ollama list`
   - Verify endpoint: `curl http://localhost:11434/api/tags`
   - Restart: `ollama serve`

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
