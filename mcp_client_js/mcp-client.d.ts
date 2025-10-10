/**
 * MCP Redaction Client - TypeScript Definitions
 * Version 2.0.0
 */

export interface MCPConfig {
    serverUrl: string;
    caller: string;
    region?: string;
    env?: string;
    timeout?: number;
}

export interface MCPContext {
    caller: string;
    region: string;
    env: string;
}

export interface MCPClassificationResult {
    ok: boolean;
    categories: Array<{
        type: string;
        confidence: number;
        spans?: Array<{ start: number; end: number; text: string }>;
    }>;
    decision: {
        action: string;
        reason: string;
        requires_redaction?: boolean;
        target?: string;
    };
    suggested_action: string;
}

export interface MCPRedactResult {
    sanitized: string;
    tokenHandle: string;
}

export interface MCPHealthStatus {
    status: string;
    version: string;
    token_backend: string;
    policy_version: number;
    siem_enabled: boolean;
}

export declare class MCPClient {
    serverUrl: string;
    caller: string;
    region: string;
    env: string;
    timeout: number;

    constructor(config: MCPConfig);

    classify(payload: string): Promise<MCPClassificationResult>;
    
    redact(payload: string): Promise<MCPRedactResult>;
    
    detokenize(
        payload: string,
        tokenHandle: string,
        allowCategories?: string[]
    ): Promise<string>;
    
    safeLLMCall(
        userInput: string,
        llmFunction: (sanitized: string) => Promise<string>,
        shouldDetokenize?: boolean,
        allowCategories?: string[]
    ): Promise<string>;
    
    isSafe(payload: string): Promise<boolean>;
    
    health(): Promise<MCPHealthStatus>;
}

export declare class MCPError extends Error {
    constructor(message: string);
}

export declare class MCPBlockedError extends MCPError {
    decision: any;
    constructor(message: string, decision?: any);
}

export declare class MCPAuthError extends MCPError {
    constructor(message: string);
}

export declare class MCPConnectionError extends MCPError {
    constructor(message: string);
}
