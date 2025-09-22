// src/components/chat/ArtifactPanel.tsx
import React, { useState } from 'react';
import styled from 'styled-components';
import { X, Copy, Download, Maximize2, Minimize2, Code2, FileText, BarChart, Check } from 'lucide-react';
import type { Artifact } from '../../types/chat';

interface ArtifactPanelProps {
  artifact?: Artifact;
  isExpanded: boolean;
  onClose: () => void;
  onToggleExpand: () => void;
}

const PanelContainer = styled.div<{ $isExpanded: boolean }>`
  width: ${props => props.$isExpanded ? '100%' : '50%'};
  height: 100vh;
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(16px) saturate(120%);
  border-left: 1px solid ${props => props.theme.glassBorder};
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  /* Glass effect overlay */
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, 
      rgba(255, 255, 255, 0.1) 0%,
      transparent 30%,
      transparent 70%,
      rgba(255, 255, 255, 0.05) 100%
    );
    pointer-events: none;
  }
`;

const PanelHeader = styled.div`
  padding: 16px 20px;
  border-bottom: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;

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

const HeaderInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const IconContainer = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, ${props => props.theme.accent}, ${props => props.theme.accentHover});
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
`;

const HeaderText = styled.div`
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: ${props => props.theme.textPrimary};
    margin: 0 0 2px 0;
  }

  p {
    font-size: 12px;
    color: ${props => props.theme.textSecondary};
    margin: 0;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ActionButton = styled.button<{ $variant?: 'danger' }>`
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: ${props => props.$variant === 'danger'
    ? 'rgba(239, 68, 68, 0.1)'
    : props.theme.glassBackground
  };
  border: 1px solid ${props => props.$variant === 'danger'
    ? 'rgba(239, 68, 68, 0.3)'
    : props.theme.glassBorder
  };
  color: ${props => props.$variant === 'danger'
    ? '#ef4444'
    : props.theme.textPrimary
  };
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: ${props => props.$variant === 'danger'
    ? 'rgba(239, 68, 68, 0.2)'
    : props.theme.glassHover
  };
    border-color: ${props => props.$variant === 'danger'
    ? 'rgba(239, 68, 68, 0.5)'
    : props.theme.accent
  };
    transform: translateY(-1px);
  }
`;

const ContentArea = styled.div`
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
`;

const CodeContainer = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

const CodeHeader = styled.div`
  padding: 12px 20px;
  background: ${props => props.theme.glassHover};
  border-bottom: 1px solid ${props => props.theme.glassBorder};
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
`;

const LanguageBadge = styled.span`
  padding: 4px 8px;
  background: ${props => props.theme.accent}20;
  border: 1px solid ${props => props.theme.accent}40;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: ${props => props.theme.accent};
  text-transform: uppercase;
`;

const CopyButton = styled.button<{ $copied: boolean }>`
  padding: 6px 12px;
  background: ${props => props.$copied ? '#10b981' : props.theme.glassBackground};
  border: 1px solid ${props => props.$copied ? '#10b981' : props.theme.glassBorder};
  border-radius: 6px;
  color: ${props => props.$copied ? 'white' : props.theme.textPrimary};
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;

  &:hover {
    background: ${props => props.$copied ? '#059669' : props.theme.glassHover};
    border-color: ${props => props.$copied ? '#059669' : props.theme.accent};
  }
`;

const CodeBlock = styled.pre`
  flex: 1;
  margin: 0;
  padding: 20px;
  background: ${props => props.theme.background};
  color: ${props => props.theme.textPrimary};
  font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow: auto;
  white-space: pre-wrap;
  word-wrap: break-word;

  &::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  
  &::-webkit-scrollbar-track {
    background: ${props => props.theme.glassBackground};
    border-radius: 4px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.glassBorder};
    border-radius: 4px;
  }
  
  &::-webkit-scrollbar-thumb:hover {
    background: ${props => props.theme.accent};
  }
`;

const DocumentContainer = styled.div`
  flex: 1;
  padding: 20px;
  overflow: auto;
  font-size: 14px;
  line-height: 1.6;
  color: ${props => props.theme.textPrimary};

  &::-webkit-scrollbar {
    width: 8px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.glassBorder};
    border-radius: 4px;
  }
`;

const EmptyState = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: ${props => props.theme.textSecondary};
  gap: 16px;

  div {
    font-size: 48px;
    opacity: 0.5;
  }

  h3 {
    font-size: 18px;
    margin: 0;
    color: ${props => props.theme.textPrimary};
  }

  p {
    margin: 0;
    font-size: 14px;
  }
`;

const getArtifactIcon = (type: string) => {
  switch (type) {
    case 'code':
      return <Code2 size={18} />;
    case 'document':
      return <FileText size={18} />;
    case 'chart':
      return <BarChart size={18} />;
    default:
      return <Code2 size={18} />;
  }
};

const getArtifactTypeLabel = (type: string) => {
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

export const ArtifactPanel: React.FC<ArtifactPanelProps> = ({
  artifact,
  isExpanded,
  onClose,
  onToggleExpand,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!artifact?.content) return;

    try {
      await navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy content:', err);
    }
  };

  const handleDownload = () => {
    if (!artifact?.content) return;

    const blob = new Blob([artifact.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${artifact.title.toLowerCase().replace(/\s+/g, '-')}.${artifact.language || 'txt'
      }`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!artifact) {
    return (
      <PanelContainer $isExpanded={isExpanded}>
        <PanelHeader>
          <HeaderInfo>
            <IconContainer>
              <FileText size={18} />
            </IconContainer>
            <HeaderText>
              <h3>No Artifact</h3>
              <p>Select a message with an artifact to view</p>
            </HeaderText>
          </HeaderInfo>
          <HeaderActions>
            <ActionButton onClick={onClose} $variant="danger">
              <X size={16} />
            </ActionButton>
          </HeaderActions>
        </PanelHeader>

        <ContentArea>
          <EmptyState>
            <div>📄</div>
            <h3>No Artifact Selected</h3>
            <p>Click on an artifact in a message to view it here</p>
          </EmptyState>
        </ContentArea>
      </PanelContainer>
    );
  }

  return (
    <PanelContainer $isExpanded={isExpanded}>
      <PanelHeader>
        <HeaderInfo>
          <IconContainer>
            {getArtifactIcon(artifact.type)}
          </IconContainer>
          <HeaderText>
            <h3>{artifact.title}</h3>
            <p>{getArtifactTypeLabel(artifact.type)}</p>
          </HeaderText>
        </HeaderInfo>

        <HeaderActions>
          <ActionButton onClick={handleDownload} title="Download">
            <Download size={14} />
          </ActionButton>
          <ActionButton onClick={onToggleExpand} title={isExpanded ? 'Split View' : 'Full Screen'}>
            {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </ActionButton>
          <ActionButton onClick={onClose} $variant="danger" title="Close">
            <X size={14} />
          </ActionButton>
        </HeaderActions>
      </PanelHeader>

      <ContentArea>
        {artifact.type === 'code' ? (
          <CodeContainer>
            <CodeHeader>
              <LanguageBadge>{artifact.language || 'text'}</LanguageBadge>
              <CopyButton onClick={handleCopy} $copied={copied}>
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? 'Copied!' : 'Copy Code'}
              </CopyButton>
            </CodeHeader>
            <CodeBlock>{artifact.content}</CodeBlock>
          </CodeContainer>
        ) : (
          <DocumentContainer>
            {artifact.content}
          </DocumentContainer>
        )}
      </ContentArea>
    </PanelContainer>
  );
};