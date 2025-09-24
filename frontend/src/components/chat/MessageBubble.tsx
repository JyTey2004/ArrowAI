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
    animation: ${slideIn} 0.3s ease-out;
`;

const AvatarUtilsContainer = styled.div`
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-start;
    gap: 6px;
    margin-left: 8px;
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
    max-width: ${props => props.$isUser ? '70%' : '100%'};
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

const MarkdownContent = styled.div<{ $isUser: boolean; hasArtifact?: boolean }>`
  font-size: 14px;
  margin-bottom: ${props => props.hasArtifact ? '12px' : '0'};
  
  /* Headings */
  h1, h2, h3, h4, h5, h6 {
    margin: 8px 0 4px 0;
    font-weight: 600;
    line-height: 1.3;
    color: ${props => props.$isUser ? 'rgba(255, 255, 255, 0.95)' : props.theme.textPrimary};
    
    &:first-child {
      margin-top: 0;
    }
  }
  
  h1 { font-size: 18px; }
  h2 { font-size: 16px; }
  h3 { font-size: 15px; }
  h4, h5, h6 { font-size: 14px; }
  
  /* Paragraphs */
  p {
    margin: 0 0 8px 0;
    line-height: 1.5;
    
    &:last-child {
      margin-bottom: 0;
    }
  }
  
  /* Lists */
  ul, ol {
    margin: 8px 0;
    padding-left: 20px;
    
    li {
      margin: 2px 0;
      line-height: 1.4;
    }
    
    ul, ol {
      margin: 4px 0;
    }
  }
  
  /* Code */
  code {
    background: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.2)'
        : props.theme.glassBackground
    };
    border: 1px solid ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.3)'
        : props.theme.glassBorder
    };
    border-radius: 4px;
    padding: 2px 6px;
    font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
    font-size: 13px;
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.9)'
        : props.theme.textPrimary
    };
    word-break: break-word;
  }
  
  /* Code blocks */
  pre {
    background: ${props => props.$isUser
        ? 'rgba(0, 0, 0, 0.2)'
        : props.theme.glassBackground
    };
    border: 1px solid ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.3)'
        : props.theme.glassBorder
    };
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    overflow-x: auto;
    font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
    font-size: 13px;
    line-height: 1.4;
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.9)'
        : props.theme.textPrimary
    };
    
    code {
      background: none;
      border: none;
      padding: 0;
      color: inherit;
    }
    
    &::-webkit-scrollbar {
      height: 6px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.3)'
        : props.theme.glassBorder
    };
      border-radius: 3px;
    }
  }
  
  /* Links */
  a {
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.9)'
        : props.theme.accent
    };
    text-decoration: underline;
    
    &:hover {
      text-decoration: none;
      opacity: 0.8;
    }
  }
  
  /* Emphasis */
  strong, b {
    font-weight: 600;
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.95)'
        : props.theme.textPrimary
    };
  }
  
  em, i {
    font-style: italic;
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.85)'
        : props.theme.textSecondary
    };
  }
  
  /* Blockquotes */
  blockquote {
    border-left: 3px solid ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.4)'
        : props.theme.accent
    };
    margin: 8px 0;
    padding: 8px 0 8px 16px;
    background: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.1)'
        : props.theme.glassBackground
    };
    border-radius: 0 4px 4px 0;
    color: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.8)'
        : props.theme.textSecondary
    };
    font-style: italic;
    
    p {
      margin: 0;
    }
  }
  
  /* Tables */
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
    font-size: 13px;
  }
  
  th, td {
    border: 1px solid ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.3)'
        : props.theme.glassBorder
    };
    padding: 6px 8px;
    text-align: left;
  }
  
  th {
    background: ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.2)'
        : props.theme.glassBackground
    };
    font-weight: 600;
  }
  
  /* Horizontal rules */
  hr {
    border: none;
    border-top: 1px solid ${props => props.$isUser
        ? 'rgba(255, 255, 255, 0.3)'
        : props.theme.glassBorder
    };
    margin: 16px 0;
  }
  
  /* Checkboxes for task lists */
  input[type="checkbox"] {
    margin-right: 8px;
  }
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
    margin-top: 6px;
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

// Simple markdown parser
const parseMarkdown = (text: string): string => {
    let html = text;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // html = html.replace(/_(.*?)_/g, '<em>$1</em>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Code blocks
    html = html.replace(/```(\w+)?\n([\s\S]*?)\n```/g, '<pre><code>$2</code></pre>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraphs if not already wrapped
    if (!html.startsWith('<') || (!html.includes('<p>') && !html.includes('<h'))) {
        html = '<p>' + html + '</p>';
    }

    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>\s*<\/p>/g, '');

    // Lists
    html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
    html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/^(\d+)\. (.*$)/gim, '<li>$1</li>');

    // Wrap consecutive list items
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    html = html.replace(/<\/li>\s*<li>/g, '</li><li>');

    // Blockquotes
    html = html.replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>');

    // Horizontal rules
    html = html.replace(/^---$/gim, '<hr>');

    return html;
};

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

    const renderedMarkdown = parseMarkdown(message.text);

    return (
        <MessageContainer $isUser={message.isUser}>
            {message.isUser &&

                <AvatarUtilsContainer>
                    <Avatar $isUser={message.isUser}>
                        AC
                    </Avatar>
                </AvatarUtilsContainer>
            }
            <div style={{ flex: 1, maxWidth: `${message.isUser ? '70%' : '100%'}` }}>
                <MessageBubbleContainer $isUser={message.isUser}>
                    <MarkdownContent
                        $isUser={message.isUser}
                        hasArtifact={message.hasArtifact}
                        dangerouslySetInnerHTML={{ __html: renderedMarkdown }}
                    />
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
                {message.hasArtifact && !message.isUser && (
                    <>
                        <ActionButton
                            $isUser={message.isUser}
                            onClick={handleCopyText}
                            title="Copy message"
                        >
                            {copied ? <Check size={10} /> : <Copy size={10} />}
                        </ActionButton>
                        <ActionButton
                            $isUser={message.isUser}
                            onClick={handleCopyCode}
                            title="Copy code"
                        >
                            <Code2 size={10} />
                        </ActionButton>
                    </>
                )}
            </div>
        </MessageContainer>
    );
};