/**
 * React Component Example for MCP Client
 * 
 * Usage:
 * 1. npm install
 * 2. Copy mcp-client.js to your src/ directory
 * 3. Import MCPClient and use this component
 */

import React, { useState, useEffect } from 'react';
import { MCPClient, MCPBlockedError } from '../mcp-client.js';

const MCPChatExample = () => {
    const [mcpClient, setMcpClient] = useState(null);
    const [userInput, setUserInput] = useState('');
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(false);
    const [serverHealth, setServerHealth] = useState(null);

    // Initialize MCP client on component mount
    useEffect(() => {
        const client = new MCPClient({
            serverUrl: process.env.REACT_APP_MCP_SERVER || 'https://mcp.yourcompany.com',
            caller: 'react-chat-app',
            region: 'us',
            env: 'prod'
        });
        setMcpClient(client);

        // Check health
        client.health()
            .then(health => setServerHealth(health))
            .catch(err => console.error('Health check failed:', err));
    }, []);

    const handleSendMessage = async () => {
        if (!userInput.trim() || !mcpClient) return;

        const userMessage = userInput;
        setUserInput('');
        setLoading(true);

        // Add user message to chat
        setMessages(prev => [...prev, {
            role: 'user',
            content: userMessage,
            timestamp: new Date()
        }]);

        try {
            // Use MCP to safely call LLM
            const response = await mcpClient.safeLLMCall(
                userMessage,
                async (sanitizedInput) => {
                    // Replace this with actual OpenAI/Claude call
                    const llmResponse = await callYourLLM(sanitizedInput);
                    return llmResponse;
                }
            );

            // Add assistant response to chat
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: response,
                timestamp: new Date()
            }]);

        } catch (error) {
            let errorMessage = 'An error occurred';
            
            if (error instanceof MCPBlockedError) {
                errorMessage = '🚫 This request was blocked by security policy due to sensitive content.';
            } else {
                errorMessage = `Error: ${error.message}`;
            }

            setMessages(prev => [...prev, {
                role: 'error',
                content: errorMessage,
                timestamp: new Date()
            }]);
        } finally {
            setLoading(false);
        }
    };

    // Simulated LLM call (replace with real OpenAI/Claude)
    const callYourLLM = async (sanitizedInput) => {
        // Example: OpenAI API call
        // const response = await fetch('https://api.openai.com/v1/chat/completions', {
        //     method: 'POST',
        //     headers: {
        //         'Authorization': `Bearer ${process.env.REACT_APP_OPENAI_KEY}`,
        //         'Content-Type': 'application/json'
        //     },
        //     body: JSON.stringify({
        //         model: 'gpt-4',
        //         messages: [{ role: 'user', content: sanitizedInput }]
        //     })
        // });
        // const data = await response.json();
        // return data.choices[0].message.content;

        // For now, simulate response
        await new Promise(resolve => setTimeout(resolve, 1000));
        return `I received your sanitized input: "${sanitizedInput}". How can I help?`;
    };

    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h2>🛡️ MCP-Protected Chat</h2>
                {serverHealth && (
                    <div style={styles.healthBadge}>
                        ✓ MCP Server v{serverHealth.version} ({serverHealth.status})
                    </div>
                )}
            </div>

            <div style={styles.chatContainer}>
                {messages.map((msg, idx) => (
                    <div key={idx} style={{
                        ...styles.message,
                        ...(msg.role === 'user' ? styles.userMessage : 
                            msg.role === 'error' ? styles.errorMessage : 
                            styles.assistantMessage)
                    }}>
                        <div style={styles.messageRole}>
                            {msg.role === 'user' ? '👤 You' : 
                             msg.role === 'error' ? '⚠️ Error' : 
                             '🤖 Assistant'}
                        </div>
                        <div style={styles.messageContent}>{msg.content}</div>
                        <div style={styles.messageTime}>
                            {msg.timestamp.toLocaleTimeString()}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div style={styles.loadingMessage}>
                        <div>🔒 Checking for sensitive data...</div>
                        <div>⚙️ Processing request...</div>
                    </div>
                )}
            </div>

            <div style={styles.inputContainer}>
                <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type a message... (try: 'My AWS key is AKIAIOSFODNN7EXAMPLE')"
                    style={styles.input}
                    disabled={loading}
                />
                <button
                    onClick={handleSendMessage}
                    disabled={loading || !userInput.trim()}
                    style={styles.sendButton}
                >
                    {loading ? '...' : 'Send'}
                </button>
            </div>

            <div style={styles.info}>
                ℹ️ All messages are automatically scanned for sensitive data before being sent to the LLM.
                Secrets like API keys are blocked or redacted automatically.
            </div>
        </div>
    );
};

// Inline styles (or use your CSS framework)
const styles = {
    container: {
        maxWidth: '800px',
        margin: '20px auto',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '20px',
        background: '#f8f9fa',
        borderRadius: '8px 8px 0 0',
        borderBottom: '2px solid #007bff'
    },
    healthBadge: {
        background: '#28a745',
        color: 'white',
        padding: '6px 12px',
        borderRadius: '20px',
        fontSize: '12px'
    },
    chatContainer: {
        height: '500px',
        overflowY: 'auto',
        padding: '20px',
        background: 'white',
        border: '1px solid #ddd'
    },
    message: {
        marginBottom: '16px',
        padding: '12px',
        borderRadius: '8px',
        maxWidth: '80%'
    },
    userMessage: {
        background: '#007bff',
        color: 'white',
        marginLeft: 'auto'
    },
    assistantMessage: {
        background: '#f1f3f5',
        color: '#333'
    },
    errorMessage: {
        background: '#f8d7da',
        color: '#721c24',
        border: '1px solid #f5c6cb'
    },
    messageRole: {
        fontWeight: 'bold',
        fontSize: '12px',
        marginBottom: '4px'
    },
    messageContent: {
        lineHeight: '1.5'
    },
    messageTime: {
        fontSize: '10px',
        opacity: 0.7,
        marginTop: '4px'
    },
    loadingMessage: {
        textAlign: 'center',
        color: '#666',
        padding: '20px',
        fontStyle: 'italic'
    },
    inputContainer: {
        display: 'flex',
        padding: '20px',
        background: '#f8f9fa',
        borderRadius: '0 0 8px 8px',
        gap: '10px'
    },
    input: {
        flex: 1,
        padding: '12px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        fontSize: '14px'
    },
    sendButton: {
        padding: '12px 24px',
        background: '#007bff',
        color: 'white',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '14px',
        fontWeight: 'bold'
    },
    info: {
        marginTop: '16px',
        padding: '12px',
        background: '#e7f3ff',
        borderLeft: '4px solid #007bff',
        borderRadius: '4px',
        fontSize: '13px',
        color: '#0056b3'
    }
};

export default MCPChatExample;
