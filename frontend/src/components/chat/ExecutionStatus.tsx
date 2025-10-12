// src/components/chat/ExecutionStatus.tsx
import React from 'react';
import styled from 'styled-components';
import { ChevronDown, Play, CheckCircle, X, Code2, Terminal, AlertCircle, Wrench, Info, FileText, BarChart } from 'lucide-react';
import type { Message, Artifact } from '../../types/chat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type StepKind =
  | 'tool-call'
  | 'status'
  | 'stdout'
  | 'stderr'
  | 'code'
  | 'todo'
  | 'artifact'
  | 'thought'
  | 'other';

interface ExecutionStep {
  id: string;
  message: Message;
  stepNumber: number;
  kind: StepKind;
}

interface ExecutionStatusProps {
  groupId: string;
  steps: ExecutionStep[];
  artifacts: Artifact[];
  isExpanded: boolean;
  onToggle: (groupId: string) => void;
  onArtifactClick?: (artifactId: string) => void;
  currentNode?: string | null;
  isRunning?: boolean;
}

const ExecutionContainer = styled.div`
  overflow-y: auto;
  overflow-x: hidden;
  border-radius: 12px;

`;

const ExecutionHeader = styled.div<{ $isExpanded: boolean }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: ${props => props.theme.glassBackground};
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: ${props => props.$isExpanded ? '12px 12px 0 0' : '12px'};
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: ${props => props.theme.glassHover};
    border-color: ${props => props.theme.accent}60;
  }
`;

const ExecutionInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const ExecutionIcon = styled.div<{ $status: 'running' | 'completed' | 'error' }>`
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${props => {
    switch (props.$status) {
      case 'running': return props.theme.accent + '20';
      case 'completed': return '#22c55e20';
      case 'error': return '#ef444420';
      default: return props.theme.glassBorder + '20';
    }
  }};
  color: ${props => {
    switch (props.$status) {
      case 'running': return props.theme.accent;
      case 'completed': return '#22c55e';
      case 'error': return '#ef4444';
      default: return props.theme.textSecondary;
    }
  }};

  ${props => props.$status === 'running' && `
    animation: pulse 2s infinite;
  `}

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`;

const ExecutionText = styled.div`
  h4 {
    font-size: 14px;
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

const ExecutionToggle = styled.div<{ $isExpanded: boolean }>`
  display: flex;
  align-items: center;
  gap: 8px;
  color: ${props => props.theme.textSecondary};
  font-size: 12px;
  transition: transform 0.2s ease;
  
  svg {
    transform: ${props => props.$isExpanded ? 'rotate(180deg)' : 'rotate(0deg)'};
    transition: transform 0.2s ease;
  }
`;

const ExecutionSteps = styled.div<{ $isExpanded: boolean }>`
  border: 1px solid ${props => props.theme.glassBorder};
  border-top: none;
  border-radius: 0 0 12px 12px;
  background: ${props => props.theme.background};
  max-height: ${props => props.$isExpanded ? '560px' : '0'};
  opacity: ${props => props.$isExpanded ? 1 : 0};
  overflow-y: auto;
  overflow-x: hidden;
  transition: all 0.3s ease;

  /* Custom scrollbar */
  &::-webkit-scrollbar {
    width: 4px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.glassBorder};
    border-radius: 4px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
  }  
`;

const ExecutionStep = styled.div<{ $isActive: boolean }>`
  padding: 12px 20px;
  border-bottom: 1px solid ${props => props.theme.glassBorder};
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: ${props => props.$isActive ? props.theme.accent + '10' : 'transparent'};
  
  &:last-child {
    border-bottom: none;
  }
`;

const StepIcon = styled.div<{ $status: 'pending' | 'running' | 'completed' | 'error' | 'info' }>`
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
  flex-shrink: 0;
  
  ${props => {
    switch (props.$status) {
      case 'running':
        return `
          background: ${props.theme.accent};
          color: white;
          animation: pulse 2s infinite;
        `;
      case 'completed':
        return `
          background: #22c55e;
          color: white;
        `;
      case 'error':
        return `
          background: #ef4444;
          color: white;
        `;
      case 'info':
        return `
          background: ${props.theme.glassBorder};
          color: ${props.theme.accent};
        `;
      default:
        return `
          background: ${props.theme.glassBorder};
          color: ${props.theme.textSecondary};
        `;
    }
  }}
`;

const StepContent = styled.div`
  flex: 1;
  width: 0; /* For text truncation */
  
  h5 {
    font-size: 13px;
    font-weight: 600;
    color: ${props => props.theme.textPrimary};
    margin: 0 0 4px 0;
  }
  
  p {
    font-size: 12px;
    color: ${props => props.theme.textSecondary};
    margin: 0;
    line-height: 1.4;
  }
  
  pre {
    font-size: 11px;
    background: ${props => props.theme.glassBackground};
    border: 1px solid ${props => props.theme.glassBorder};
    border-radius: 4px;
    padding: 8px;
    margin: 8px 0 0 0;
    overflow-x: auto;
    color: ${props => props.theme.textPrimary};
    font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
    line-height: 1.3;
    
    &::-webkit-scrollbar {
      height: 4px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: ${props => props.theme.glassBorder};
      border-radius: 2px;
    }
  }
`;

const StepMarkdown = styled.div`
  font-size: 12px;
  color: ${props => props.theme.textSecondary};
  line-height: 1.45;
  margin-top: 4px;

  strong {
    color: ${props => props.theme.textPrimary};
  }

  code {
    background: ${props => props.theme.glassBackground};
    border: 1px solid ${props => props.theme.glassBorder};
    border-radius: 4px;
    padding: 2px 4px;
    font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
  }

  pre {
    font-size: 11px;
    background: ${props => props.theme.glassBackground};
    border: 1px solid ${props => props.theme.glassBorder};
    border-radius: 4px;
    padding: 8px;
    overflow-x: auto;
    color: ${props => props.theme.textPrimary};
    margin-top: 8px;
    line-height: 1.4;
  }
`;

const StepTimestamp = styled.div`
  font-size: 10px;
  color: ${props => props.theme.textSecondary};
  opacity: 0.7;
  margin-top: 4px;
`;

const ArtifactsSection = styled.div`
  padding: 12px 20px 20px;
  border-top: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.glassBackground};
`;

const ArtifactsHeading = styled.div`
  font-size: 12px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary};
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ArtifactList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const ArtifactItem = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid ${props => props.theme.glassBorder};
  background: ${props => props.theme.background};
  color: ${props => props.theme.textPrimary};
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: ${props => props.theme.glassHover};
    border-color: ${props => props.theme.accent}60;
    transform: translateY(-1px);
  }
`;

const ArtifactInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;

  span:first-child {
    font-size: 12px;
    font-weight: 600;
    color: ${props => props.theme.textPrimary};
  }

  span:last-child {
    font-size: 11px;
    color: ${props => props.theme.textSecondary};
  }
`;

// Utility functions
const getStepIcon = (step: ExecutionStep) => {
  switch (step.kind) {
    case 'tool-call':
      return <Wrench size={10} />;
    case 'status':
      return <Info size={10} />;
    case 'stdout':
      return <CheckCircle size={10} />;
    case 'stderr':
      return <X size={10} />;
    case 'code':
      return <Code2 size={10} />;
    case 'todo':
    case 'artifact':
    case 'thought':
      return <Terminal size={10} />;
    default:
      if (step.message.text.includes('❌ **Error:**')) return <X size={10} />;
      if (step.message.text.includes('✅ **Output:**')) return <CheckCircle size={10} />;
      return <Terminal size={10} />;
  }
};

const getStepStatus = (step: ExecutionStep): 'pending' | 'running' | 'completed' | 'error' | 'info' => {
  if (step.kind === 'tool-call') return 'info';
  if (step.kind === 'stderr') return 'error';
  if (step.kind === 'status' && step.message.text.toLowerCase().includes('error')) {
    return 'error';
  }
  if (step.message.text.includes('❌ **Error:**')) return 'error';
  return 'completed';
};

const getStepTitle = (step: ExecutionStep): string => {
  const { message, stepNumber, kind } = step;
  if (kind === 'tool-call') {
    const explicitStep = typeof message.toolStep === 'number' ? message.toolStep : stepNumber;
    const toolMatch = message.text.match(/\*\*(.*?)\*\*/);
    const toolName = toolMatch ? toolMatch[1] : '';
    return `Tool Call • Step ${explicitStep}${toolName ? ` – ${toolName}` : ''}`;
  }
  if (kind === 'status') {
    return message.text.split('\n')[0].replace('🚧 ', '') || `Step ${stepNumber}: Status Update`;
  }
  if (kind === 'stdout') return `Step ${stepNumber}: Command Output`;
  if (kind === 'stderr') return `Step ${stepNumber}: Error Output`;
  if (kind === 'code') return `Step ${stepNumber}: Code Generated`;
  if (kind === 'todo') return `Step ${stepNumber}: TODO Update`;
  if (kind === 'artifact') return `Step ${stepNumber}: Artifact Created`;
  if (kind === 'thought') return `Step ${stepNumber}: Thought`;
  return `Step ${stepNumber}: Process Step`;
};

const getStepDescription = (step: ExecutionStep): string | null => {
  if (step.kind === 'tool-call' || step.kind === 'thought') {
    return null;
  }

  // Remove markdown formatting and get first line
  const cleanText = step.message.text
    .replace(/[✅❌💻📋📎]\s\*\*[^*]+\*\*:\s?/g, '')
    .replace(/\n/g, ' ')
    .replace(/```[\s\S]*?```/g, '[code block]')
    .trim();

  return cleanText.length > 100 ? cleanText.substring(0, 100) + '...' : cleanText;
};

const extractCodeBlock = (message: Message): string | null => {
  const codeMatch = message.text.match(/```[\w]*\n?([\s\S]*?)\n?```/);
  if (codeMatch && codeMatch[1]) {
    return codeMatch[1].trim();
  }

  // Also check for output blocks
  const outputMatch = message.text.match(/Output:\s*```[\w]*\n?([\s\S]*?)\n?```/);
  if (outputMatch && outputMatch[1]) {
    return outputMatch[1].trim();
  }

  // Check for simple output after "Output:"
  const simpleOutputMatch = message.text.match(/Output:\s*(.+)/);
  if (simpleOutputMatch && simpleOutputMatch[1]) {
    return simpleOutputMatch[1].trim();
  }

  return null;
};

const getOverallStatus = (steps: ExecutionStep[], isRunning: boolean): 'running' | 'completed' | 'error' => {
  if (isRunning) return 'running';

  const hasErrors = steps.some(step => getStepStatus(step) === 'error');
  return hasErrors ? 'error' : 'completed';
};

const formatTimestamp = (timestamp: Date): string => {
  return timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const getArtifactIcon = (artifact: Artifact) => {
  switch (artifact.type) {
    case 'chart':
      return <BarChart size={16} />;
    case 'code':
      return <Code2 size={16} />;
    case 'document':
    default:
      return <FileText size={16} />;
  }
};

export const ExecutionStatus: React.FC<ExecutionStatusProps> = ({
  groupId,
  steps,
  artifacts = [],
  isExpanded,
  onToggle,
  onArtifactClick,
  currentNode,
  isRunning = false
}) => {
  const overallStatus = getOverallStatus(steps, isRunning);

  const getStatusText = () => {
    if (isRunning && currentNode) {
      return `Processing: ${currentNode}`;
    }
    if (isRunning) {
      return 'Processing...';
    }
    if (overallStatus === 'error') {
      return `${steps.length} steps completed with errors`;
    }
    return `${steps.length} steps completed successfully`;
  };

  const getHeaderIcon = () => {
    if (isRunning) return <Play size={12} />;
    if (overallStatus === 'error') return <AlertCircle size={12} />;
    return <CheckCircle size={12} />;
  };

  return (
    <ExecutionContainer>
      <ExecutionHeader
        $isExpanded={isExpanded}
        onClick={() => onToggle(groupId)}
      >
        <ExecutionInfo>
          <ExecutionIcon $status={overallStatus}>
            {getHeaderIcon()}
          </ExecutionIcon>
          <ExecutionText>
            <h4>
              {isRunning ? 'Execution In Progress' : 'Execution Process'}
            </h4>
            <p>{getStatusText()}</p>
          </ExecutionText>
        </ExecutionInfo>
        <ExecutionToggle $isExpanded={isExpanded}>
          <span>{isExpanded ? 'Hide steps' : 'View steps'}</span>
          <ChevronDown size={14} />
        </ExecutionToggle>
      </ExecutionHeader>

      <ExecutionSteps $isExpanded={isExpanded}>
        {steps.length === 0 ? (
          <ExecutionStep $isActive={false}>
            <StepIcon $status="info">
              <Info size={10} />
            </StepIcon>
            <StepContent>
              <h5>No execution steps yet</h5>
              <p>Steps will appear here as the agent makes progress.</p>
            </StepContent>
          </ExecutionStep>
        ) : (
          steps.map((step, index) => {
            const codeBlock = extractCodeBlock(step.message);
            const status = getStepStatus(step);
            const description = getStepDescription(step);
            const shouldRenderMarkdown = step.kind === 'tool-call' || step.kind === 'thought';

            return (
              <ExecutionStep
                key={step.id}
                $isActive={isRunning && index === steps.length - 1}
              >
                <StepIcon $status={status}>
                  {getStepIcon(step)}
                </StepIcon>
                <StepContent>
                  <h5>{getStepTitle(step)}</h5>
                  {shouldRenderMarkdown ? (
                    <StepMarkdown>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {step.message.text}
                      </ReactMarkdown>
                    </StepMarkdown>
                  ) : (
                    <>
                      {description && <p>{description}</p>}
                      {codeBlock && (
                        <pre>{codeBlock.length > 500 ? codeBlock.substring(0, 500) + '\n...' : codeBlock}</pre>
                      )}
                    </>
                  )}
                  <StepTimestamp>
                    {formatTimestamp(step.message.timestamp)}
                  </StepTimestamp>
                </StepContent>
              </ExecutionStep>
            );
          })
        )}

        {artifacts.length > 0 && (
          <ArtifactsSection>
            <ArtifactsHeading>
              <FileText size={14} />
              Generated Artifacts ({artifacts.length})
            </ArtifactsHeading>
            <ArtifactList>
              {artifacts.map(artifact => (
                <ArtifactItem
                  key={artifact.id}
                  type="button"
                  onClick={() => onArtifactClick?.(artifact.id)}
                >
                  {getArtifactIcon(artifact)}
                  <ArtifactInfo>
                    <span>{artifact.filename || artifact.title || 'Unnamed artifact'}</span>
                    <span>{artifact.language || artifact.type || 'artifact'}</span>
                  </ArtifactInfo>
                </ArtifactItem>
              ))}
            </ArtifactList>
          </ArtifactsSection>
        )}
      </ExecutionSteps>
    </ExecutionContainer>
  );
};
