// src/components/chat/MessageBubble.tsx
import React from 'react';
import styled, { keyframes } from 'styled-components';
import { Code2, FileText, BarChart, ExternalLink, Copy, Check } from 'lucide-react';
import type { Message } from '../../types/chat';

interface MessageBubbleProps {
    message: Message;
    onArtifactClick?: () => void;
}

const slideIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const MessageContainer = styled.div<{ $isUser: boolean }>`
    width: 100%;
    display: flex;
    flex-direction: ${props => props.$isUser ? 'row-reverse' : 'row'};
    align-items: flex-end;
    gap: 8px;
    animation: ${slideIn} 0.3s ease-out;
`;

const AvatarUtilsContainer = styled.div`
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-start;
    gap: 6px;
`;

const Avatar = styled.div<{ $isUser: boolean }>`
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: ${props => props.$isUser
        ? `linear-gradient(135deg, ${props.theme.accent}, ${props.theme.accentHover})`
        : `linear-gradient(135deg, ${props.theme.textSecondary}, ${props.theme.textPrimary})`
    };
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
    order: ${props => props.$isUser ? 1 : 0};
`;

const MessageBubbleContainer = styled.div<{ $isUser: boolean }>`
    width: fit-content;
    align-self: ${props => props.$isUser ? 'flex-end' : 'flex-start'};
    justify-self: ${props => props.$isUser ? 'flex-end' : 'flex-start'};
    max-width: 70%;
    min-width: 120px;
    padding: 12px 16px;
    border-radius: ${props => props.$isUser ? '18px 18px 6px 18px' : '18px 18px 18px 6px'};
    background: ${props => props.$isUser
        ? `linear-gradient(135deg, ${props.theme.accent}, ${props.theme.accentHover})`
        : props.theme.glassBackground
    };
    backdrop-filter: ${props => props.$isUser ? 'none' : 'blur(8px)'};
    border: ${props => props.$isUser ? 'none' : `1px solid ${props.theme.glassBorder}`};
    color: ${props => props.$isUser ? 'white' : props.theme.textPrimary};
    box-shadow: ${props => props.$isUser
        ? `0 4px 12px ${props.theme.accent}40`
        : `0 2px 8px ${props.theme.glassBorder}60`
    };
    word-wrap: break-word;
    line-height: 1.5;
    position: relative;
    transition: all 0.2s ease;

    &:hover {
        transform: translateY(-1px);
        box-shadow: ${props => props.$isUser
        ? `0 6px 20px ${props.theme.accent}50`
        : `0 4px 12px ${props.theme.glassBorder}80`
    };
    }
`;

const MessageText = styled.div<{ hasArtifact?: boolean }>`
  font-size: 14px;
  margin-bottom: ${props => props.hasArtifact ? '12px' : '0'};
`;

const MessageTime = styled.div<{ $isUser: boolean }>`
  font-size: 11px;
  color: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.7)' : props.theme.textSecondary};
  margin-top: 4px;
  text-align: ${props => props.$isUser ? 'right' : 'left'};
`;

const ArtifactPreview = styled.div`
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent);
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
    
    &::before {
      opacity: 1;
    }
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
  color: rgba(255, 255, 255, 0.8);
`;

const ArtifactTitle = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  flex: 1;
`;

const ArtifactAction = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
`;

const CodePreview = styled.pre`
  font-size: 11px;
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
  overflow: hidden;
  white-space: pre-wrap;
  line-height: 1.4;
  max-height: 60px;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 20px;
    background: linear-gradient(transparent, rgba(0, 0, 0, 0.3));
  }
`;

const ActionButton = styled.button<{ $isUser: boolean }>`
    padding: 8px;
    background: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.2)' : props.theme.glassBackground};
    border: 1px solid ${props => props.$isUser ? 'rgba(0, 0, 0, 0.2)' : props.theme.glassBorder};
    border-radius: 4px;
    color: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.8)' : props.theme.textSecondary};
    font-size: 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.2s ease;
    opacity: 0;

    &:hover {
        background: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.3)' : props.theme.glassHover};
        border-color: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.5)' : props.theme.accent};
    }

    svg {
        width: 14px;
        height: 14px;
        color: ${props => props.$isUser ? 'grey' : props.theme.textSecondary};
    }

    ${MessageContainer}:hover & {
        opacity: 1;
    }
`;

const formatTime = (timestamp: Date): string => {
    return timestamp.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
};

const getArtifactIcon = (type?: string) => {
    switch (type) {
        case 'code':
            return <Code2 size={14} />;
        case 'document':
            return <FileText size={14} />;
        case 'chart':
            return <BarChart size={14} />;
        default:
            return <Code2 size={14} />;
    }
};

const getArtifactTitle = (type?: string) => {
    switch (type) {
        case 'code':
            return 'Code Artifact';
        case 'document':
            return 'Document';
        case 'chart':
            return 'Chart';
        default:
            return 'Artifact';
    }
};

export const MessageBubble: React.FC<MessageBubbleProps> = ({
    message,
    onArtifactClick
}) => {
    const [copied, setCopied] = React.useState(false);

    const handleCopyText = async () => {
        try {
            await navigator.clipboard.writeText(message.text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy text:', err);
        }
    };

    const handleCopyCode = async () => {
        if (message.artifactContent) {
            try {
                await navigator.clipboard.writeText(message.artifactContent);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } catch (err) {
                console.error('Failed to copy code:', err);
            }
        }
    };

    const getCodePreview = (content: string) => {
        const lines = content.split('\n');
        const preview = lines.slice(0, 3).join('\n');
        return lines.length > 3 ? preview + '\n...' : preview;
    };

    return (
        <MessageContainer $isUser={message.isUser}>
            <AvatarUtilsContainer>
                <ActionButton
                    $isUser={message.isUser}
                    onClick={handleCopyText}
                    title="Copy message"
                >
                    {copied ? <Check size={10} /> : <Copy size={10} />}
                </ActionButton>

                {message.hasArtifact && (
                    <ActionButton
                        $isUser={message.isUser}
                        onClick={handleCopyCode}
                        title="Copy code"
                    >
                        <Code2 size={10} />
                    </ActionButton>
                )}
                <Avatar $isUser={message.isUser}>
                    {message.isUser ? 'U' : 'AI'}
                </Avatar>
            </AvatarUtilsContainer>
            <div style={{ flex: 1, maxWidth: '70%' }}>
                <MessageBubbleContainer $isUser={message.isUser}>
                    <MessageText hasArtifact={message.hasArtifact}>
                        {message.text}
                    </MessageText>

                    {message.hasArtifact && message.artifactContent && (
                        <ArtifactPreview onClick={onArtifactClick}>
                            <ArtifactHeader>
                                <ArtifactIcon>
                                    {getArtifactIcon(message.artifactType)}
                                </ArtifactIcon>
                                <ArtifactTitle>
                                    {getArtifactTitle(message.artifactType)}
                                </ArtifactTitle>
                                <ArtifactAction>
                                    <ExternalLink size={12} />
                                    View
                                </ArtifactAction>
                            </ArtifactHeader>

                            {message.artifactType === 'code' && (
                                <CodePreview>
                                    {getCodePreview(message.artifactContent)}
                                </CodePreview>
                            )}

                            {message.artifactType === 'document' && (
                                <div style={{
                                    fontSize: '11px',
                                    color: 'rgba(255, 255, 255, 0.8)',
                                    fontStyle: 'italic'
                                }}>
                                    Click to view document content
                                </div>
                            )}
                        </ArtifactPreview>
                    )}

                    <MessageTime $isUser={message.isUser}>
                        {formatTime(message.timestamp)}
                    </MessageTime>
                </MessageBubbleContainer>
            </div>
        </MessageContainer>
    );
};