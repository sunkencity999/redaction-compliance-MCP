"""
Claim Verification Module - Research-Based Approach
Reduces hallucinations and false claims in LLM responses using a 4-stage pipeline:
1. Sentence splitting and context creation
2. Selection (verifiable vs unverifiable content)
3. Disambiguation (resolve ambiguity or flag)
4. Decomposition (extract atomic claims)
5. Verification (fact-check claims)
"""

import re
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx


@dataclass
class Claim:
    """Represents a single extracted claim."""
    text: str
    source_sentence: str
    confidence: float
    verdict: str  # TRUE, FALSE, LIKELY_FALSE, UNVERIFIABLE
    reasoning: str
    evidence_summary: str
    hallucination_risk: str  # low, medium, high
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    """Results from the claim verification pipeline."""
    original_text: str
    verified_claims: List[Claim]
    flagged_claims: List[Claim]
    ambiguous_sentences: List[str]
    unverifiable_sentences: List[str]
    confidence_score: float
    total_claims: int
    
    def has_high_risk_hallucinations(self) -> bool:
        """Check if response contains high-risk hallucinations."""
        return any(c.hallucination_risk == "high" for c in self.flagged_claims)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "verified_claims": [c.to_dict() for c in self.verified_claims],
            "flagged_claims": [c.to_dict() for c in self.flagged_claims],
            "ambiguous_sentences": self.ambiguous_sentences,
            "unverifiable_sentences": self.unverifiable_sentences,
            "confidence_score": self.confidence_score,
            "total_claims": self.total_claims,
            "has_high_risk": self.has_high_risk_hallucinations()
        }


class ClaimVerifier:
    """
    Verifies claims in LLM responses using a research-based approach.
    Reduces hallucinations and provides transparency about factual accuracy.
    """
    
    # System prompts for each stage
    SELECTION_PROMPT = """You are a claim extraction expert. Identify sentences with verifiable factual claims.

RULES:
1. Verifiable: Facts, events, statistics, relationships, concrete statements
2. Unverifiable: Opinions, subjective interpretations, recommendations, questions, hypotheticals

For each sentence:
- If ONLY unverifiable content: label "No verifiable claims"
- If BOTH verifiable and unverifiable: rewrite to keep only verifiable parts
- If ONLY verifiable content: keep as-is

Sentence: {sentence}
Context: {context}

Respond in JSON:
{{
  "has_verifiable_content": true/false,
  "rewritten_sentence": "..." or null,
  "reasoning": "..."
}}"""

    DISAMBIGUATION_PROMPT = """You are an ambiguity detection expert. Identify if the sentence has multiple valid interpretations.

RULES:
1. Check for ambiguous references (pronouns, "they", "it", "this", "the company")
2. Check for ambiguous scope ("A and B at Company X" - both or one each?)
3. Check for ambiguous time references ("next year", "recently")
4. Use context to resolve if possible
5. Flag if ambiguity cannot be confidently resolved

Sentence: {sentence}
Context: {context}

Respond in JSON:
{{
  "is_ambiguous": true/false,
  "can_resolve_with_context": true/false,
  "disambiguated_sentence": "..." or null,
  "ambiguity_description": "...",
  "possible_interpretations": ["...", "..."]
}}"""

    DECOMPOSITION_PROMPT = """You are a claim decomposition expert. Break down the sentence into atomic, standalone claims.

RULES:
1. Each claim must be FULLY SUPPORTED by the source sentence (no inference)
2. Each claim must be UNDERSTANDABLE WITHOUT CONTEXT
3. Each claim must PRESERVE CRITICAL CONTEXT (conditions, qualifiers, scope)
4. Do NOT add information not in the source
5. Do NOT omit critical qualifiers

Sentence: {sentence}
Context: {context}

Respond in JSON:
{{
  "claims": [
    {{
      "claim_text": "...",
      "confidence": 0.95,
      "preserves_context": true
    }}
  ]
}}"""

    VERIFICATION_PROMPT = """You are a fact-checking expert. Verify if the claim is likely true, false, or unverifiable.

RULES:
1. Use your knowledge cutoff as a boundary
2. Flag claims that are likely hallucinations (fabricated facts, wrong numbers, false events)
3. Flag claims lacking sufficient evidence
4. Consider domain and context
5. Be conservative - if uncertain, mark UNVERIFIABLE

Claim: {claim}
Context: {context}
Domain: {domain}

Respond in JSON:
{{
  "verdict": "TRUE" | "FALSE" | "LIKELY_FALSE" | "UNVERIFIABLE",
  "confidence": 0.85,
  "reasoning": "...",
  "evidence_summary": "...",
  "hallucination_risk": "low" | "medium" | "high",
  "suggested_correction": "..." or null
}}"""
    
    def __init__(self, llm_client: httpx.AsyncClient, llm_config: Dict[str, Any]):
        """
        Initialize claim verifier.
        
        Args:
            llm_client: HTTP client for LLM API calls
            llm_config: Configuration for verification LLM (model, API key, etc.)
        """
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.cache = {}  # Simple in-memory cache
    
    async def verify_response(
        self,
        response_text: str,
        context: Dict[str, Any],
        verification_level: str = "standard"
    ) -> VerificationResult:
        """
        Run full 4-stage verification pipeline.
        
        Args:
            response_text: LLM response to verify
            context: Context about the request (caller, domain, etc.)
            verification_level: standard, strict, or permissive
            
        Returns:
            VerificationResult with verified and flagged claims
        """
        # Stage 1: Sentence splitting and context creation
        sentences = self._split_sentences(response_text)
        
        # Stage 2: Selection (filter to verifiable content)
        verifiable = await self._select_verifiable_sentences(sentences, context)
        
        # Stage 3: Disambiguation
        disambiguated = await self._disambiguate_sentences(verifiable, context)
        
        # Stage 4: Decomposition (extract claims)
        claims = await self._decompose_to_claims(disambiguated, context)
        
        # Stage 5: Verification (fact-check)
        verified = await self._verify_claims(claims, context)
        
        # Calculate confidence score
        if verified:
            confidence = sum(c.confidence for c in verified) / len(verified)
        else:
            confidence = 1.0
        
        flagged = [c for c in verified if c.verdict in ["FALSE", "LIKELY_FALSE"] or c.hallucination_risk in ["medium", "high"]]
        
        return VerificationResult(
            original_text=response_text,
            verified_claims=verified,
            flagged_claims=flagged,
            ambiguous_sentences=[s["ambiguity"] for s in disambiguated if s.get("ambiguous")],
            unverifiable_sentences=[s["sentence"] for s in verifiable if not s["has_verifiable"]],
            confidence_score=confidence,
            total_claims=len(verified)
        )
    
    def _split_sentences(self, text: str) -> List[Dict[str, Any]]:
        """Split text into sentences with context."""
        # Simple sentence splitting (could be enhanced with nltk/spacy)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        result = []
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
                
            # Create context window (previous and next sentence)
            context_before = sentences[i-1] if i > 0 else ""
            context_after = sentences[i+1] if i < len(sentences)-1 else ""
            
            result.append({
                "sentence": sentence,
                "index": i,
                "context_before": context_before,
                "context_after": context_after
            })
        
        return result
    
    async def _select_verifiable_sentences(
        self,
        sentences: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Stage 2: Identify sentences with verifiable content."""
        result = []
        
        for sent_data in sentences:
            sentence = sent_data["sentence"]
            ctx = f"Before: {sent_data['context_before']}\nAfter: {sent_data['context_after']}"
            
            # Check cache
            cache_key = f"select:{sentence}"
            if cache_key in self.cache:
                selection = self.cache[cache_key]
            else:
                prompt = self.SELECTION_PROMPT.format(sentence=sentence, context=ctx)
                selection = await self._call_llm(prompt, "selection")
                self.cache[cache_key] = selection
            
            sent_data["has_verifiable"] = selection.get("has_verifiable_content", False)
            sent_data["rewritten"] = selection.get("rewritten_sentence")
            sent_data["selection_reasoning"] = selection.get("reasoning", "")
            
            result.append(sent_data)
        
        return result
    
    async def _disambiguate_sentences(
        self,
        sentences: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Stage 3: Resolve or flag ambiguity."""
        result = []
        
        for sent_data in sentences:
            if not sent_data["has_verifiable"]:
                continue
            
            sentence = sent_data["rewritten"] or sent_data["sentence"]
            ctx = f"Before: {sent_data['context_before']}\nAfter: {sent_data['context_after']}"
            
            cache_key = f"disambig:{sentence}"
            if cache_key in self.cache:
                disambig = self.cache[cache_key]
            else:
                prompt = self.DISAMBIGUATION_PROMPT.format(sentence=sentence, context=ctx)
                disambig = await self._call_llm(prompt, "disambiguation")
                self.cache[cache_key] = disambig
            
            sent_data["ambiguous"] = disambig.get("is_ambiguous", False)
            sent_data["can_resolve"] = disambig.get("can_resolve_with_context", False)
            sent_data["disambiguated"] = disambig.get("disambiguated_sentence")
            sent_data["ambiguity"] = disambig.get("ambiguity_description", "")
            
            # Only include if not ambiguous or successfully disambiguated
            if not sent_data["ambiguous"] or sent_data["can_resolve"]:
                result.append(sent_data)
        
        return result
    
    async def _decompose_to_claims(
        self,
        sentences: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Stage 4: Extract atomic claims from sentences."""
        all_claims = []
        
        for sent_data in sentences:
            sentence = sent_data["disambiguated"] or sent_data["rewritten"] or sent_data["sentence"]
            ctx = f"Before: {sent_data['context_before']}\nAfter: {sent_data['context_after']}"
            
            cache_key = f"decomp:{sentence}"
            if cache_key in self.cache:
                decomp = self.cache[cache_key]
            else:
                prompt = self.DECOMPOSITION_PROMPT.format(sentence=sentence, context=ctx)
                decomp = await self._call_llm(prompt, "decomposition")
                self.cache[cache_key] = decomp
            
            claims = decomp.get("claims", [])
            for claim in claims:
                claim["source_sentence"] = sentence
                all_claims.append(claim)
        
        return all_claims
    
    async def _verify_claims(
        self,
        claims: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Claim]:
        """Stage 5: Verify factual accuracy of claims."""
        verified_claims = []
        
        domain = context.get("domain", "general")
        
        for claim_data in claims:
            claim_text = claim_data["claim_text"]
            
            cache_key = f"verify:{claim_text}"
            if cache_key in self.cache:
                verification = self.cache[cache_key]
            else:
                prompt = self.VERIFICATION_PROMPT.format(
                    claim=claim_text,
                    context=json.dumps(context),
                    domain=domain
                )
                verification = await self._call_llm(prompt, "verification")
                self.cache[cache_key] = verification
            
            claim = Claim(
                text=claim_text,
                source_sentence=claim_data["source_sentence"],
                confidence=verification.get("confidence", 0.5),
                verdict=verification.get("verdict", "UNVERIFIABLE"),
                reasoning=verification.get("reasoning", ""),
                evidence_summary=verification.get("evidence_summary", ""),
                hallucination_risk=verification.get("hallucination_risk", "medium")
            )
            
            verified_claims.append(claim)
        
        return verified_claims
    
    async def _call_llm(self, prompt: str, stage: str) -> Dict[str, Any]:
        """Call LLM for verification tasks. Supports both cloud and local models."""
        try:
            # Use the configured verification LLM
            model = self.llm_config.get("model", "gpt-4o-mini")
            api_key = self.llm_config.get("api_key", "")
            base_url = self.llm_config.get("base_url", "https://api.openai.com/v1")
            require_auth = self.llm_config.get("require_auth", True)
            
            # Build headers (optional auth for local models)
            headers = {"Content-Type": "application/json"}
            if require_auth and api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Build request payload
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert in claim extraction and verification. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1  # Low temperature for consistency
            }
            
            # Only add response_format for models that support it (OpenAI, some local models)
            if self.llm_config.get("supports_json_mode", True):
                payload["response_format"] = {"type": "json_object"}
            
            response = await self.llm_client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code != 200:
                print(f"LLM call failed ({stage}): {response.text}")
                return {}
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return json.loads(content)
            
        except Exception as e:
            print(f"Error calling LLM for {stage}: {e}")
            return {}


def annotate_response_with_warnings(
    response_text: str,
    verification: VerificationResult
) -> str:
    """
    Add inline warnings to response text for flagged claims.
    
    Args:
        response_text: Original LLM response
        verification: Verification results
        
    Returns:
        Annotated response with inline warnings
    """
    annotated = response_text
    
    # Sort flagged claims by position in text (to avoid offset issues)
    flagged_by_position = []
    for claim in verification.flagged_claims:
        # Find claim text in response
        pos = annotated.find(claim.source_sentence)
        if pos != -1:
            flagged_by_position.append((pos, claim))
    
    # Sort by position (reverse so we insert from end to avoid offset changes)
    flagged_by_position.sort(key=lambda x: x[0], reverse=True)
    
    for pos, claim in flagged_by_position:
        # Create warning message based on risk level
        if claim.hallucination_risk == "high":
            icon = "🚨"
            level = "HIGH CONFIDENCE"
        elif claim.hallucination_risk == "medium":
            icon = "⚠️"
            level = "MEDIUM CONFIDENCE"
        else:
            icon = "ℹ️"
            level = "LOW CONFIDENCE"
        
        warning = f"\n{icon} **[CLAIM FLAGGED - {level}]**: {claim.reasoning}"
        if claim.verdict in ["FALSE", "LIKELY_FALSE"]:
            warning += f" (Verdict: {claim.verdict})"
        
        # Insert warning after the sentence
        sentence_end = pos + len(claim.source_sentence)
        annotated = annotated[:sentence_end] + warning + annotated[sentence_end:]
    
    return annotated
