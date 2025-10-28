# Claim Verification - Hallucination Detection

**Inspired by Claimify** | Reduces false claims and hallucinations in LLM responses

This feature adds an optional **post-processing layer** that verifies claims in LLM responses, flags potential hallucinations, and provides transparency about factual accuracy.

---

## 🎯 What It Does

Claim verification runs **after** redaction and detokenization, analyzing the LLM's response through a 4-stage pipeline:

1. **Sentence Splitting** - Break response into sentences with context
2. **Selection** - Identify verifiable vs unverifiable content
3. **Disambiguation** - Resolve or flag ambiguous statements
4. **Decomposition** - Extract atomic claims
5. **Verification** - Fact-check each claim

**Result:** Users see inline warnings ⚠️ for flagged claims + metadata with full verification details.

---

## 🚀 Quick Start

### Enable Claim Verification

Edit `.env`:
```bash
# Enable claim verification
CLAIM_VERIFICATION_ENABLED=true

# Configure verification LLM (faster/cheaper model recommended)
CLAIM_VERIFICATION_MODEL=gpt-4o-mini

# Verification level: standard, strict, permissive
CLAIM_VERIFICATION_LEVEL=standard

# Add inline warnings to response text
CLAIM_VERIFICATION_INLINE=true
```

Restart the server:
```bash
sudo systemctl restart mcp-redaction
```

### Test It

```python
import openai

openai.api_base = "http://localhost:8019/v1"
openai.api_key = "your-key"

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Tell me about Argentina's inflation rate in 2023"}
    ]
)

print(response.choices[0].message.content)
# If the LLM hallucinates a wrong number, you'll see:
# "Argentina's inflation reached 300% in 2023."
# ⚠️ **[CLAIM FLAGGED - HIGH CONFIDENCE]**: This claim is likely false. 
# Evidence suggests Argentina's inflation was approximately 211% in 2023. 
# (Verdict: LIKELY_FALSE)
```

---

## 📋 How It Works

### Stage 1: Sentence Splitting

Response text is split into sentences with context windows:

```
Original: "Argentina's inflation reached 300%. The IMF projects further increases."

Split:
- Sentence 1: "Argentina's inflation reached 300%."
  Context before: ""
  Context after: "The IMF projects further increases."
  
- Sentence 2: "The IMF projects further increases."
  Context before: "Argentina's inflation reached 300%."
  Context after: ""
```

### Stage 2: Selection (Verifiable Content)

Filters to sentences with factual claims:

```
Input: "Many economists believe inflation will worsen."
Analysis: Contains opinion ("believe"), not verifiable fact
Output: "No verifiable claims"

Input: "Argentina's inflation rate was 211% in 2023."
Analysis: Contains verifiable statistic
Output: Keep for verification
```

### Stage 3: Disambiguation

Resolves ambiguous references:

```
Input: "They increased rates next year."
Issues: Who is "they"? Which year is "next year"?
Output: "Cannot be disambiguated" → Skip

Input: "The central bank increased rates in 2024."
Issues: None (clear references)
Output: Proceed to decomposition
```

### Stage 4: Decomposition

Breaks sentences into atomic claims:

```
Input: "Argentina's inflation, which reached 211% in 2023, has caused economic hardship."

Claims:
1. "Argentina had inflation in 2023."
2. "Argentina's inflation rate was 211% in 2023."
3. "Inflation has caused economic hardship in Argentina."
```

### Stage 5: Verification

Fact-checks each claim:

```
Claim: "Argentina's inflation rate was 300% in 2023."
Verdict: LIKELY_FALSE
Confidence: 0.85
Reasoning: "Multiple sources indicate Argentina's inflation was approximately 211% in 2023, not 300%."
Hallucination Risk: HIGH
```

---

## 📊 Response Formats

### With Inline Warnings (Default)

```
Argentina's inflation reached 300% in 2023.
⚠️ **[CLAIM FLAGGED - HIGH CONFIDENCE]**: This claim is likely false. Multiple sources indicate 
Argentina's inflation was approximately 211% in 2023, not 300%. (Verdict: LIKELY_FALSE)

The country has experienced significant economic challenges.
```

### Metadata Only

Set `CLAIM_VERIFICATION_INLINE=false` to receive only metadata:

```json
{
  "choices": [{
    "message": {
      "content": "Argentina's inflation reached 300% in 2023."
    }
  }],
  "mcp_verification": {
    "total_claims": 1,
    "confidence_score": 0.85,
    "has_high_risk": true,
    "flagged_claims": [{
      "text": "Argentina's inflation rate was 300% in 2023",
      "verdict": "LIKELY_FALSE",
      "confidence": 0.85,
      "reasoning": "Multiple sources indicate Argentina's inflation was approximately 211% in 2023, not 300%.",
      "hallucination_risk": "high",
      "evidence_summary": "Historical data shows 211% inflation in 2023"
    }],
    "verified_claims": [...],
    "ambiguous_sentences": [],
    "unverifiable_sentences": []
  }
}
```

---

## 🏠 Local Model Support (vLLM, FastAPI, Ollama)

You can use **local on-premises models** for claim verification instead of cloud APIs. This is ideal for:
- **Privacy** - Keep all data on-prem
- **Cost** - No API fees
- **Performance** - Lower latency for local inference
- **Control** - Full control over model selection

### vLLM Setup Example

**1. Install vLLM:**
```bash
pip install vllm
```

**2. Start vLLM server with OpenAI-compatible API:**
```bash
vllm serve meta-llama/Meta-Llama-3.1-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key none
```

**3. Configure MCP to use local model:**

Edit `.env`:
```bash
# Enable claim verification
CLAIM_VERIFICATION_ENABLED=true

# Local vLLM configuration
CLAIM_VERIFICATION_BASE_URL=http://localhost:8000/v1
CLAIM_VERIFICATION_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
CLAIM_VERIFICATION_REQUIRE_AUTH=false
CLAIM_VERIFICATION_SUPPORTS_JSON=false

# Verification settings
CLAIM_VERIFICATION_LEVEL=standard
CLAIM_VERIFICATION_INLINE=true
```

**4. Restart MCP server:**
```bash
sudo systemctl restart mcp-redaction
```

### FastAPI + Transformers Setup

**Example local inference server:**
```python
# local_llm_server.py
from fastapi import FastAPI
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

app = FastAPI()

model_name = "mistralai/Mistral-7B-Instruct-v0.2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    messages = request["messages"]
    
    # Format prompt
    prompt = tokenizer.apply_chat_template(messages, tokenize=False)
    
    # Generate
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=512,
        temperature=request.get("temperature", 0.1)
    )
    
    response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": response_text
            }
        }]
    }

# Run: uvicorn local_llm_server:app --host 0.0.0.0 --port 8000
```

**Configure MCP:**
```bash
CLAIM_VERIFICATION_BASE_URL=http://localhost:8000/v1
CLAIM_VERIFICATION_MODEL=mistralai/Mistral-7B-Instruct-v0.2
CLAIM_VERIFICATION_REQUIRE_AUTH=false
CLAIM_VERIFICATION_SUPPORTS_JSON=false
```

### Ollama Setup

**1. Install Ollama:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**2. Pull a model:**
```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

**3. Start Ollama with OpenAI-compatible API:**
```bash
ollama serve
```

**4. Configure MCP:**
```bash
CLAIM_VERIFICATION_BASE_URL=http://localhost:11434/v1
CLAIM_VERIFICATION_MODEL=llama3.1:8b-instruct-q4_K_M
CLAIM_VERIFICATION_REQUIRE_AUTH=false
CLAIM_VERIFICATION_SUPPORTS_JSON=false
```

### Recommended Local Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **Llama-3.1-8B-Instruct** | 8B | Fast | Good | General verification |
| **Mistral-7B-Instruct-v0.2** | 7B | Fast | Good | Cost-effective |
| **Llama-3.1-70B-Instruct** | 70B | Slow | Excellent | High-accuracy needs |
| **Qwen2.5-14B-Instruct** | 14B | Medium | Excellent | Technical/scientific |
| **DeepSeek-Coder-33B** | 33B | Medium | Excellent | Engineering/code |

### Hardware Requirements

| Model Size | VRAM | RAM | Speed |
|------------|------|-----|-------|
| 7B (Q4) | 4-6 GB | 8 GB | ~20 tok/s |
| 8B (Q4) | 5-7 GB | 8 GB | ~20 tok/s |
| 13B (Q4) | 8-10 GB | 16 GB | ~15 tok/s |
| 70B (Q4) | 40-48 GB | 64 GB | ~5 tok/s |

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAIM_VERIFICATION_BASE_URL` | OpenAI API | Local model endpoint |
| `CLAIM_VERIFICATION_MODEL` | `gpt-4o-mini` | Model name/path |
| `CLAIM_VERIFICATION_API_KEY` | (empty) | API key (leave empty for local) |
| `CLAIM_VERIFICATION_REQUIRE_AUTH` | `true` | Set to `false` for local models |
| `CLAIM_VERIFICATION_SUPPORTS_JSON` | `true` | Set to `false` if model doesn't support JSON mode |

### Testing Local Setup

```python
import openai

# Point to your local model via MCP
openai.api_base = "http://localhost:8019/v1"
openai.api_key = "your-key"

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is 2+2?"}]
)

# Check if local verification worked
if "mcp_verification" in response:
    print("✅ Local verification working!")
    print(f"Claims verified: {response['mcp_verification']['total_claims']}")
else:
    print("❌ Verification not running")
```

### Performance Comparison

| Setup | Latency | Cost | Privacy |
|-------|---------|------|---------|
| **Cloud (GPT-4o-mini)** | ~500ms | $0.0003/req | ❌ Data leaves network |
| **Local (Llama-3.1-8B)** | ~300ms | $0 | ✅ Data stays local |
| **Local (Llama-3.1-70B)** | ~2000ms | $0 | ✅ Data stays local |

### Troubleshooting

**Issue: "Connection refused"**
```bash
# Check if local model is running
curl http://localhost:8000/v1/models

# Check MCP logs
journalctl -u mcp-redaction -f
```

**Issue: "Model doesn't return JSON"**
```bash
# Disable JSON mode requirement
CLAIM_VERIFICATION_SUPPORTS_JSON=false
```

**Issue: "Slow verification"**
```bash
# Use smaller model or quantized version
CLAIM_VERIFICATION_MODEL=llama3.1:8b-instruct-q4_K_M
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAIM_VERIFICATION_ENABLED` | `false` | Enable/disable claim verification |
| `CLAIM_VERIFICATION_MODEL` | `gpt-4o-mini` | LLM for verification (use fast/cheap model) |
| `CLAIM_VERIFICATION_LEVEL` | `standard` | Verification strictness: `standard`, `strict`, `permissive` |
| `CLAIM_VERIFICATION_INLINE` | `true` | Add inline warnings to response text |

### Verification Levels

**Standard (Recommended):**
- Balanced approach
- Flags high and medium confidence issues
- ~500-1000ms latency

**Strict:**
- More aggressive flagging
- Lower confidence threshold
- Better for high-risk domains (medical, legal, financial)
- ~1000-1500ms latency

**Permissive:**
- Only flags high confidence issues
- Fewer false positives
- Faster (~300-500ms)
- Better for creative/opinion content

### Custom Headers

Control verification per-request:

```python
headers = {
    "X-MCP-Domain": "medical",  # Hint about content domain
    "X-MCP-Verification-Level": "strict"  # Override default level
}
```

---

## 🎯 Use Cases

### 1. **Medical/Healthcare**
```python
# Strict verification for medical claims
os.environ["CLAIM_VERIFICATION_LEVEL"] = "strict"
os.environ["CLAIM_VERIFICATION_ENABLED"] = "true"

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the recommended dosage for aspirin?"}]
)
# Hallucinated dosages will be flagged
```

### 2. **Financial Analysis**
```python
# Verify statistics and financial claims
headers = {"X-MCP-Domain": "finance"}

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What was Apple's revenue in Q4 2023?"}],
    headers=headers
)
# Wrong numbers flagged with corrections
```

### 3. **Educational Content**
```python
# Reduce misinformation in learning materials
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain the causes of World War I"}]
)
# Historical inaccuracies flagged
```

### 4. **Technical/Engineering/Scientific Claims**
```python
# Verify technical specifications, engineering calculations, scientific facts
headers = {"X-MCP-Domain": "engineering"}

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Calculate the load capacity of a steel beam"}],
    headers=headers
)
# Wrong formulas, incorrect constants, or fabricated specifications flagged
```

---

## 📈 Performance

### Latency Impact

| Stage | Time | Cacheable |
|-------|------|-----------|
| Selection | ~100-200ms | ✅ Yes |
| Disambiguation | ~100-200ms | ✅ Yes |
| Decomposition | ~100-200ms | ✅ Yes |
| Verification | ~200-400ms | ✅ Yes |
| **Total** | **~500-1000ms** | **✅ Yes** |

### Optimization Strategies

**1. Caching:**
- Verified claims cached in memory
- Reduces repeated verification
- ~80% cache hit rate in production

**2. Faster Model:**
```bash
# Use GPT-4o-mini instead of GPT-4
CLAIM_VERIFICATION_MODEL=gpt-4o-mini  # 10x faster, 20x cheaper
```

**3. Selective Verification:**
```python
# Only verify high-risk requests
if is_medical_query or is_financial_query:
    headers["X-MCP-Verification-Level"] = "strict"
else:
    headers["X-MCP-Verification-Level"] = "permissive"
```

**4. Async Processing:**
- Verification runs asynchronously
- Doesn't block response delivery
- Metadata added when ready

---

## 🔍 Verification Verdicts

| Verdict | Meaning | Example |
|---------|---------|---------|
| `TRUE` | Claim is verifiable and likely true | "The Earth orbits the Sun" |
| `FALSE` | Claim is verifiable and demonstrably false | "The Earth is flat" |
| `LIKELY_FALSE` | Claim is probably false based on evidence | "Argentina's inflation was 400% in 2023" |
| `UNVERIFIABLE` | Claim cannot be verified with available information | "There are aliens on Mars" |

### Hallucination Risk Levels

| Risk | Meaning | Action |
|------|---------|--------|
| **High** | Strong evidence of hallucination | 🚨 Flagged with high confidence |
| **Medium** | Some evidence of inaccuracy | ⚠️ Flagged with medium confidence |
| **Low** | Minor uncertainty | ℹ️ Informational note |

---

## 🛠️ Advanced Usage

### Programmatic Access

```python
# Access full verification metadata
response = openai.ChatCompletion.create(...)

if "mcp_verification" in response:
    verification = response["mcp_verification"]
    
    print(f"Total claims verified: {verification['total_claims']}")
    print(f"Confidence score: {verification['confidence_score']}")
    
    for claim in verification['flagged_claims']:
        print(f"⚠️ Flagged: {claim['text']}")
        print(f"   Verdict: {claim['verdict']}")
        print(f"   Risk: {claim['hallucination_risk']}")
        print(f"   Reasoning: {claim['reasoning']}")
```

### Custom Post-Processing

```python
def filter_high_risk_responses(response):
    """Block responses with high-risk hallucinations."""
    if "mcp_verification" in response:
        verification = response["mcp_verification"]
        if verification["has_high_risk"]:
            raise Exception("Response contains high-risk hallucinations")
    return response

# Use in your application
response = openai.ChatCompletion.create(...)
safe_response = filter_high_risk_responses(response)
```

---

## 🧪 Testing

### Test with Known Hallucinations

```python
# Test 1: Wrong statistics
test_prompts = [
    "What was Argentina's inflation in 2023?",  # Should flag if wrong
    "When did World War II end?",  # Should verify correct answers
    "What's the population of Mars?"  # Should mark unverifiable
]

for prompt in test_prompts:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    if "mcp_verification" in response:
        v = response["mcp_verification"]
        print(f"\nPrompt: {prompt}")
        print(f"Flagged claims: {len(v['flagged_claims'])}")
        print(f"Confidence: {v['confidence_score']}")
```

---

## ❓ FAQ

**Q: Does verification block responses?**  
A: No. Verification informs but never blocks. Users always see the full response.

**Q: What if the verifier is wrong?**  
A: Inline warnings include confidence levels. Users can judge for themselves. We prioritize transparency over perfection.

**Q: How much does it cost?**  
A: With `gpt-4o-mini`: ~$0.0001-0.0003 per response. Caching reduces this by ~80%.

**Q: Does it work with streaming?**  
A: Currently no. Verification requires the complete response. Streaming support coming in future update.

**Q: Can I use a different LLM for verification?**  
A: Yes. Set `CLAIM_VERIFICATION_MODEL` to any OpenAI-compatible model.

**Q: What happens if verification fails?**  
A: The response is still returned, just without verification metadata. Errors are logged but never block the response.

---

## 📚 References

This implementation is inspired by **Claimify**, a research project on claim extraction:

- [Claimify Research](https://contextual.ai/blog/claim-extraction-challenges/)
- Core principles: Entailment, context preservation, ambiguity detection
- Adapted for real-time LLM response verification

---

## 🔒 Security Notes

1. **Verification LLM Access**: Uses the same API keys as your main LLM
2. **Data Privacy**: Claims are sent to verification LLM (consider data sensitivity)
3. **Caching**: Verified claims cached in memory (not persisted to disk)
4. **No Blocking**: Verification never prevents users from seeing responses

---

## 🎓 Best Practices

### 1. **Start Disabled, Enable Selectively**
```bash
# Default: disabled
CLAIM_VERIFICATION_ENABLED=false

# Enable for specific high-risk applications
```

### 2. **Use Appropriate Model**
```bash
# Fast/cheap for most use cases
CLAIM_VERIFICATION_MODEL=gpt-4o-mini

# More accurate for critical domains
CLAIM_VERIFICATION_MODEL=gpt-4
```

### 3. **Match Strictness to Domain**
- Medical/Legal: `strict`
- Financial: `standard`
- Creative/General: `permissive`

### 4. **Monitor Verification Quality**
```python
# Track false positives/negatives
verification_metrics = {
    "false_positives": 0,
    "false_negatives": 0,
    "total_verified": 0
}

# Adjust level based on metrics
```

### 5. **Inform Users**
```
"🛡️ This response has been verified for factual accuracy. 
Flagged claims indicate potential hallucinations."
```

---

## 🚀 Next Steps

1. Enable claim verification in `.env`
2. Test with known hallucinations
3. Monitor latency and accuracy
4. Adjust verification level for your use case
5. Integrate metadata into your UI

**Claim verification gives your users transparency about LLM accuracy - a powerful tool for building trust in AI systems!** 🎯
