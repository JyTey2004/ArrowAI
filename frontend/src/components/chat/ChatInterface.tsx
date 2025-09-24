// src/components/chat/ChatInterface.tsx
import React, { useState, useRef, useEffect } from 'react';
import styled from 'styled-components';
import { Send, Code2, FileText, BarChart, Maximize2, Minimize2, AlertCircle, Paperclip, X } from 'lucide-react';
import { useChat } from '../../contexts/ChatContext';
import { MessageBubble } from './MessageBubble';
import { ArtifactPanel } from './ArtifactPanel';
import { FileUpload } from './FileUpload';
import { ExecutionStatus } from './ExecutionStatus';

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
  flex-direction: column;
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

const HeaderTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
`;

const ChatTitle = styled.div`
  h1 {
    font-size: 18px;
    font-weight: 600;
    line-height: 1.2;
    color: ${props => props.theme.textPrimary};
    margin: 0;
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

const StatusBar = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
`;

const ConnectionStatus = styled.div<{ $status: string }>`
  display: flex;
  align-items: center;
  gap: 4px;
  
  &::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${props => {
    switch (props.$status) {
      case 'connected': return '#22c55e';
      case 'connecting': return '#f59e0b';
      case 'error': return '#ef4444';
      default: return '#6b7280';
    }
  }};
  }
`;

const CurrentNode = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  color: ${props => props.theme.accent};
  font-weight: 500;
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

const FinalMessageContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ArtifactsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const ArtifactPreview = styled.div`
  background: ${props => props.theme.glassBackground};
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.theme.glassHover};
    border-color: ${props => props.theme.accent}60;
    transform: translateY(-1px);
  }
`;

const ArtifactHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
`;

const ArtifactIcon = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${props => props.theme.accent};
`;

const ArtifactTitle = styled.div`
  font-size: 13px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary};
  flex: 1;
`;

const ArtifactMeta = styled.div`
  font-size: 11px;
  color: ${props => props.theme.textSecondary};
`;

const InputContainer = styled.div`
  padding: 20px 24px;
  border-top: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(8px);
`;

const FileUploadSection = styled.div<{ $isVisible: boolean }>`
  max-height: ${props => props.$isVisible ? '300px' : '0'};
  opacity: ${props => props.$isVisible ? 1 : 0};
  overflow: hidden;
  transition: all 0.3s ease;
  margin-bottom: ${props => props.$isVisible ? '16px' : '0'};
`;

const InputWrapper = styled.div`
  display: flex;
  gap: 12px;
  align-items: flex-end;
  max-width: 800px;
  margin: 0 auto;
`;

const InputSection = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const TextInput = styled.textarea`
  width: 100%;
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
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const InputActions = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
`;

const FileButton = styled.button<{ $hasFiles: boolean }>`
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: ${props => props.$hasFiles ? props.theme.accent : props.theme.glassBackground};
  border: 1px solid ${props => props.$hasFiles ? props.theme.accent : props.theme.glassBorder};
  color: ${props => props.$hasFiles ? 'white' : props.theme.textSecondary};
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  
  &:hover {
    border-color: ${props => props.theme.accent};
    background: ${props => props.$hasFiles ? props.theme.accentHover : props.theme.accent}20;
    transform: translateY(-1px);
  }
`;

const FileCount = styled.div`
  position: absolute;
  top: -6px;
  right: -6px;
  background: ${props => props.theme.accent};
  color: white;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
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

const ErrorMessage = styled.div`
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

export const ChatInterface: React.FC = () => {
  const {
    activeChat,
    chats,
    messages,
    isLoading,
    activeArtifact,
    setActiveArtifact,
    artifacts,
    sendMessage,
    isConnected,
    connectionStatus,
    currentNode,
    clarificationQuestion,
    sendClarification,
    executionStep,
    fileUploads,
    clearCompletedUploads,
    addMessage,
  } = useChat();

  const [inputValue, setInputValue] = useState('');
  const [isArtifactExpanded, setIsArtifactExpanded] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [expandedExecutions, setExpandedExecutions] = useState<Set<string>>(new Set());
  const [pendingClarification, setPendingClarification] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeChatData = chats.find(chat => chat.id === activeChat);
  const hasArtifact = activeArtifact !== null;
  const currentArtifact = artifacts.find(a => a.id === activeArtifact);

  // Add clarification message to chat when clarificationQuestion changes
  useEffect(() => {
    if (clarificationQuestion && !pendingClarification) {
      setPendingClarification(true);
      addMessage({
        text: `**Clarification needed:** ${clarificationQuestion}`,
        isUser: false,
      });
    } else if (!clarificationQuestion && pendingClarification) {
      setPendingClarification(false);
    }
  }, [clarificationQuestion, addMessage, pendingClarification]);

  // Group messages into execution groups with real-time execution steps
  const groupedMessages = React.useMemo(() => {
    type ChatMessage = typeof messages[number];
    type ArtifactItem = typeof artifacts[number];

    type ExecutionGroup = {
      id: string;
      userMessage?: ChatMessage;
      executionSteps: ChatMessage[];
      finalMessage?: ChatMessage;
      artifacts: ArtifactItem[];
      isActive?: boolean;
    };

    const groups: ExecutionGroup[] = [];

    let currentGroup: ExecutionGroup = {
      id: '',
      userMessage: undefined,
      executionSteps: [],
      finalMessage: undefined,
      artifacts: [],
      isActive: false,
    };

    messages.forEach((message) => {
      if (message.isUser) {
        // Start new group
        if (currentGroup) {
          groups.push(currentGroup);
        }
        currentGroup = {
          id: `group-${message.id}`,
          userMessage: message,
          executionSteps: [],
          finalMessage: undefined,
          artifacts: [],
          isActive: false,
        };
      } else if (currentGroup) {
        // Check if this is an execution step or final message
        const isExecutionStep = message.text.includes('✅ **Output:**') ||
          message.text.includes('❌ **Error:**') ||
          message.text.includes('💻 **Code Generated:**') ||
          message.text.includes('📋 **Todo List Generated:**') ||
          message.text.includes('📎 **Artifact');

        const isClarificationMessage = message.text.includes('**Clarification needed:**');

        if (isExecutionStep) {
          currentGroup.executionSteps.push(message);
          currentGroup.isActive = true; // Mark as active when receiving execution steps
        } else if (!isClarificationMessage) {
          // This is the final message (not a clarification)
          currentGroup.finalMessage = message;
          currentGroup.isActive = false; // Mark as completed
          // Find artifacts related to this group
          currentGroup.artifacts = artifacts.filter(a =>
            currentGroup!.executionSteps.some(step => step.id === a.messageId) ||
            a.messageId === message.id
          );
        } else {
          // Handle clarification messages - they don't belong to groups, display separately
          const clarificationGroup = {
            id: `clarification-${message.id}`,
            userMessage: undefined,
            executionSteps: [],
            finalMessage: message,
            artifacts: [],
            isActive: false,
          };
          groups.push(clarificationGroup);
        }
      } else {
        // Message without a user message (like clarification) - create standalone group
        const standaloneGroup = {
          id: `standalone-${message.id}`,
          userMessage: undefined,
          executionSteps: [],
          finalMessage: message,
          artifacts: [],
          isActive: false,
        };
        groups.push(standaloneGroup);
      }
    });

    if (currentGroup && (currentGroup.userMessage || currentGroup.executionSteps.length > 0 || currentGroup.finalMessage)) {
      // If we have execution steps but no final message, mark as active
      if (currentGroup.executionSteps.length > 0 && !currentGroup.finalMessage) {
        currentGroup.isActive = true;
      }
      groups.push(currentGroup);
    }

    return groups;
  }, [messages, artifacts]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [groupedMessages]);

  useEffect(() => {
    if (connectionStatus === 'connected') {
      setSendError(null);
    }
  }, [connectionStatus]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);

    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  };

  const handleSendMessage = async () => {
    if ((!inputValue.trim() && selectedFiles.length === 0) || isLoading || !isConnected) return;

    const userMessageText = inputValue.trim() || 'File upload';
    const filesToSend = [...selectedFiles];

    setInputValue('');
    setSelectedFiles([]);
    setShowFileUpload(false);
    setSendError(null);

    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    try {
      if (clarificationQuestion) {
        await sendClarification(userMessageText);
      } else {
        await sendMessage(userMessageText, filesToSend);
      }

      setTimeout(() => clearCompletedUploads(), 2000);
    } catch (error) {
      console.error('Failed to send message:', error);
      setSendError(error instanceof Error ? error.message : 'Failed to send message');
      setInputValue(userMessageText === 'File upload' ? '' : userMessageText);
      setSelectedFiles(filesToSend);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleExecutionExpanded = (groupId: string) => {
    const newExpanded = new Set(expandedExecutions);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedExecutions(newExpanded);
  };

  const toggleArtifactView = () => {
    if (hasArtifact) {
      setActiveArtifact(null);
    }
  };

  const toggleFileUpload = () => {
    setShowFileUpload(!showFileUpload);
  };

  const canSend = (inputValue.trim().length > 0 || selectedFiles.length > 0) && !isLoading && isConnected;

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'error': return 'Connection error';
      default: return 'Disconnected';
    }
  };

  const getInputPlaceholder = () => {
    if (!isConnected) return 'Connecting to AI service...';
    if (clarificationQuestion) return 'Please provide clarification...';
    if (isLoading) return 'AI is thinking...';
    if (selectedFiles.length > 0) return 'Add a message about these files (optional)...';
    return 'Type your message here... (Shift+Enter for new line)';
  };

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case 'code': return <Code2 size={16} />;
      case 'document': return <FileText size={16} />;
      case 'chart': return <BarChart size={16} />;
      default: return <Code2 size={16} />;
    }
  };

  return (
    <ChatContainer $hasArtifact={hasArtifact && !isArtifactExpanded}>
      <ChatPanel $hasArtifact={hasArtifact && !isArtifactExpanded}>
        <ChatHeader>
          <HeaderTop>
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
          </HeaderTop>

          <StatusBar>
            <ConnectionStatus $status={connectionStatus}>
              {getConnectionStatusText()}
            </ConnectionStatus>

            {currentNode && (
              <CurrentNode>
                Processing: {currentNode} {executionStep > 0 && `(Step ${executionStep})`}
              </CurrentNode>
            )}
          </StatusBar>
        </ChatHeader>

        <MessagesContainer>
          {groupedMessages.length === 0 ? (
            <EmptyState>
              <EmptyIcon>💬</EmptyIcon>
              <h3 style={{ margin: '0 0 8px 0', color: 'inherit' }}>Start a conversation</h3>
              <p style={{ margin: 0 }}>Ask me anything! I can help with code, analysis, and creative projects. You can also upload files for me to analyze.</p>
              {!isConnected && (
                <p style={{ margin: '16px 0 0 0', color: '#f59e0b' }}>
                  Connecting to AI service...
                </p>
              )}
            </EmptyState>
          ) : (
            <>
              {groupedMessages.map((group) => (
                <FinalMessageContainer key={group.id}>
                  {/* User Message */}
                  {group.userMessage && (
                    <MessageBubble
                      message={group.userMessage}
                      onArtifactClick={() => { }}
                    />
                  )}

                  {/* Execution Process Dropdown - Show immediately when steps arrive */}
                  {group.executionSteps.length > 0 && (
                    <ExecutionStatus
                      groupId={group.id}
                      steps={group.executionSteps.map((step, index) => ({
                        id: step.id,
                        message: step,
                        stepNumber: index + 1
                      }))}
                      isExpanded={expandedExecutions.has(group.id)}
                      onToggle={toggleExecutionExpanded}
                      currentNode={currentNode}
                      isRunning={(isLoading && group.isActive) || (group.isActive && !group.finalMessage)}
                    />
                  )}

                  {/* Final AI Response - Only show when available */}
                  {group.finalMessage && (
                    <MessageBubble
                      message={group.finalMessage}
                      onArtifactClick={() => {
                        if (group.finalMessage?.hasArtifact && group.finalMessage?.artifactContent) {
                          const existingArtifact = artifacts.find(a => a.messageId === group.finalMessage!.id);
                          if (existingArtifact) {
                            setActiveArtifact(existingArtifact.id);
                          }
                        }
                      }}
                    />
                  )}

                  {/* Artifacts List */}
                  {group.artifacts.length > 0 && (
                    <ArtifactsList>
                      {group.artifacts.map((artifact) => (
                        <ArtifactPreview
                          key={artifact.id}
                          onClick={() => setActiveArtifact(artifact.id)}
                        >
                          <ArtifactHeader>
                            <ArtifactIcon>
                              {getArtifactIcon(artifact.type)}
                            </ArtifactIcon>
                            <ArtifactTitle>{artifact.title}</ArtifactTitle>
                            <ArtifactMeta>{artifact.language || artifact.type}</ArtifactMeta>
                          </ArtifactHeader>
                        </ArtifactPreview>
                      ))}
                    </ArtifactsList>
                  )}
                </FinalMessageContainer>
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
          {sendError && (
            <ErrorMessage>
              <AlertCircle size={16} />
              {sendError}
            </ErrorMessage>
          )}

          <FileUploadSection $isVisible={showFileUpload}>
            <FileUpload
              onFilesSelected={setSelectedFiles}
              disabled={isLoading || !isConnected}
              maxFiles={5}
            />
          </FileUploadSection>

          <InputWrapper>
            <InputSection>
              <TextInput
                ref={inputRef}
                value={inputValue}
                onChange={handleInputChange}
                onKeyPress={handleKeyPress}
                placeholder={getInputPlaceholder()}
                disabled={isLoading || !isConnected}
              />
            </InputSection>

            <InputActions>
              <FileButton
                onClick={toggleFileUpload}
                $hasFiles={selectedFiles.length > 0 || showFileUpload}
                title="Upload files"
                disabled={isLoading || !isConnected}
              >
                {showFileUpload ? <X size={18} /> : <Paperclip size={18} />}
                {selectedFiles.length > 0 && (
                  <FileCount>{selectedFiles.length}</FileCount>
                )}
              </FileButton>

              <SendButton
                onClick={handleSendMessage}
                $canSend={canSend}
                disabled={!canSend}
                title={clarificationQuestion ? "Send clarification" : "Send message"}
              >
                <Send size={18} />
              </SendButton>
            </InputActions>
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