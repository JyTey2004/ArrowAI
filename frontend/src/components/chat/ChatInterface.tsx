// src/components/chat/ChatInterface.tsx
import React, { useState, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { Send, Code2, FileText, BarChart, Maximize2, Minimize2 } from 'lucide-react';
import { useChat } from '../../contexts/ChatContext';
import { MessageBubble } from './MessageBubble';
import { ArtifactPanel } from './ArtifactPanel';

const ChatContainer = styled.div<{ $hasArtifact: boolean }>`
  display: flex;
  height: 100vh;
  width: 100%;
  background: ${props => props.theme.background};
`;

const ChatPanel = styled.div<{ $hasArtifact: boolean }>`
  width: ${props => props.$hasArtifact ? '50%' : '100%'};
  display: flex;
  flex-direction: column;
  height: 100vh;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: ${props => props.$hasArtifact ? `1px solid ${props.theme.glassBorder}` : 'none'};
`;

const ChatHeader = styled.div`
  padding: 16px;
  border-bottom: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, 
      transparent 0%, 
      ${props => props.theme.accent}40 50%, 
      transparent 100%
    );
  }
`;

const ChatTitle = styled.div`
  h1 {
    font-size: 18px;
    font-weight: 600;\
    line-height: 1.2;
    color: ${props => props.theme.textPrimary};
    margin: 0 0 0 0;
  }
`;

const ChatActions = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ActionButton = styled.button<{ $isActive?: boolean }>`
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: ${props => props.$isActive ? props.theme.accent : props.theme.glassBackground};
  border: 1px solid ${props => props.$isActive ? props.theme.accent : props.theme.glassBorder};
  color: ${props => props.$isActive ? 'white' : props.theme.textPrimary};
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: ${props => props.$isActive ? props.theme.accentHover : props.theme.glassHover};
    border-color: ${props => props.theme.accent};
    transform: translateY(-1px);
  }
`;

const MessagesContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: ${props => props.theme.background};
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.glassBorder};
    border-radius: 3px;
  }
`;

const InputContainer = styled.div`
  padding: 20px 24px;
  border-top: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(8px);
`;

const InputWrapper = styled.div`
  display: flex;
  gap: 12px;
  align-items: flex-end;
  max-width: 800px;
  margin: 0 auto;
`;

const TextInput = styled.textarea`
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 12px 16px;
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: 12px;
  background: ${props => props.theme.glassBackground};
  color: ${props => props.theme.textPrimary};
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  outline: none;
  transition: all 0.2s ease;
  
  &:focus {
    border-color: ${props => props.theme.accent};
    box-shadow: 0 0 0 3px ${props => props.theme.accent}20;
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary};
  }
`;

const SendButton = styled.button<{ $canSend: boolean }>`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: ${props => props.$canSend ? props.theme.accent : props.theme.glassBackground};
  border: 1px solid ${props => props.$canSend ? props.theme.accent : props.theme.glassBorder};
  color: ${props => props.$canSend ? 'white' : props.theme.textSecondary};
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ${props => props.$canSend ? 'pointer' : 'not-allowed'};
  transition: all 0.2s ease;
  
  &:hover {
    ${props => props.$canSend && `
      background: ${props.theme.accentHover};
      transform: translateY(-1px);
      box-shadow: 0 4px 12px ${props.theme.accent}40;
    `}
  }
  
  &:active {
    transform: translateY(0);
  }
`;

const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px;
  color: ${props => props.theme.textSecondary};
`;

const EmptyIcon = styled.div`
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
`;

const TypingIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  background: ${props => props.theme.glassBackground};
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: 18px;
  width: fit-content;
  
  span {
    width: 6px;
    height: 6px;
    background: ${props => props.theme.textSecondary};
    border-radius: 50%;
    animation: typing 1.4s ease-in-out infinite;
    
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
  
  @keyframes typing {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-10px); }
  }
`;

export const ChatInterface: React.FC = () => {
  const {
    activeChat,
    chats,
    messages,
    addMessage,
    isLoading,
    setIsLoading,
    activeArtifact,
    setActiveArtifact,
    artifacts
  } = useChat();

  const [inputValue, setInputValue] = useState('');
  const [isArtifactExpanded, setIsArtifactExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeChatData = chats.find(chat => chat.id === activeChat);
  const hasArtifact = activeArtifact !== null;
  const currentArtifact = artifacts.find(a => a.id === activeArtifact);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);

    // Auto-resize textarea
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessageText = inputValue.trim();
    setInputValue('');
    setIsLoading(true);

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    // Add user message
    addMessage({
      text: userMessageText,
      isUser: true,
    });

    // Simulate AI response
    setTimeout(() => {
      const responses = [
        {
          text: `I understand you're asking about "${userMessageText}". Let me help you with that.`,
          hasArtifact: Math.random() > 0.6,
        },
        {
          text: `That's a great question about "${userMessageText}". Here's what I can tell you:`,
          hasArtifact: Math.random() > 0.7,
        },
        {
          text: `I'll help you with "${userMessageText}". Let me create something for you.`,
          hasArtifact: Math.random() > 0.4,
        },
      ];

      const randomResponse = responses[Math.floor(Math.random() * responses.length)];

      addMessage({
        text: randomResponse.text,
        isUser: false,
        hasArtifact: randomResponse.hasArtifact,
        artifactType: randomResponse.hasArtifact ? 'code' : undefined,
        artifactContent: randomResponse.hasArtifact ? `// Sample code for: ${userMessageText}
import React from 'react';

const ExampleComponent: React.FC = () => {
  return (
    <div>
      <h2>Sample Component</h2>
      <p>This is related to: ${userMessageText}</p>
    </div>
  );
};

export default ExampleComponent;` : undefined,
        artifactLanguage: randomResponse.hasArtifact ? 'typescript' : undefined,
      });

      setIsLoading(false);
    }, 1000 + Math.random() * 2000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleArtifactView = () => {
    if (hasArtifact) {
      setActiveArtifact(null);
    }
  };

  const canSend = inputValue.trim().length > 0 && !isLoading;

  return (
    <ChatContainer $hasArtifact={hasArtifact && !isArtifactExpanded}>
      <ChatPanel $hasArtifact={hasArtifact && !isArtifactExpanded}>
        <ChatHeader>
          <ChatTitle>
            <h1>{activeChatData?.title || 'New Chat'}</h1>
          </ChatTitle>

          <ChatActions>
            {hasArtifact && (
              <>
                <ActionButton
                  onClick={() => setIsArtifactExpanded(!isArtifactExpanded)}
                  title={isArtifactExpanded ? 'Split View' : 'Full Screen'}
                >
                  {isArtifactExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </ActionButton>
                <ActionButton
                  onClick={toggleArtifactView}
                  $isActive={hasArtifact}
                  title="Toggle Artifact"
                >
                  {currentArtifact?.type === 'code' && <Code2 size={16} />}
                  {currentArtifact?.type === 'document' && <FileText size={16} />}
                  {currentArtifact?.type === 'chart' && <BarChart size={16} />}
                </ActionButton>
              </>
            )}
          </ChatActions>
        </ChatHeader>

        <MessagesContainer>
          {messages.length === 0 ? (
            <EmptyState>
              <EmptyIcon>💬</EmptyIcon>
              <h3 style={{ margin: '0 0 8px 0', color: 'inherit' }}>Start a conversation</h3>
              <p style={{ margin: 0 }}>Ask me anything! I can help with code, explanations, and more.</p>
            </EmptyState>
          ) : (
            <>
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onArtifactClick={() => {
                    if (message.hasArtifact && message.artifactContent) {
                      // Find or create artifact for this message
                      const existingArtifact = artifacts.find(a => a.messageId === message.id);
                      if (existingArtifact) {
                        setActiveArtifact(existingArtifact.id);
                      }
                    }
                  }}
                />
              ))}

              {isLoading && (
                <TypingIndicator>
                  <span></span>
                  <span></span>
                  <span></span>
                </TypingIndicator>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </MessagesContainer>

        <InputContainer>
          <InputWrapper>
            <TextInput
              ref={inputRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder="Type your message here... (Shift+Enter for new line)"
              disabled={isLoading}
            />
            <SendButton
              onClick={handleSendMessage}
              $canSend={canSend}
              disabled={!canSend}
              title="Send message"
            >
              <Send size={18} />
            </SendButton>
          </InputWrapper>
        </InputContainer>
      </ChatPanel>

      {/* Artifact Panel */}
      {hasArtifact && (
        <ArtifactPanel
          artifact={currentArtifact}
          isExpanded={isArtifactExpanded}
          onClose={() => setActiveArtifact(null)}
          onToggleExpand={() => setIsArtifactExpanded(!isArtifactExpanded)}
        />
      )}
    </ChatContainer>
  );
};