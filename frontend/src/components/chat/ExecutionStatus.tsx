// src/components/chat/ExecutionStatus.tsx
import React from 'react';
import styled from 'styled-components';
import { ChevronDown, Play, CheckCircle, X, Code2, Terminal, AlertCircle } from 'lucide-react';
import type { Message } from '../../types/chat';

interface ExecutionStep {
  id: string;
  message: Message;
  stepNumber: number;
}

interface ExecutionStatusProps {
  groupId: string;
  steps: ExecutionStep[];
  isExpanded: boolean;
  onToggle: (groupId: string) => void;
  currentNode?: string | null;
  isRunning?: boolean;
}

const ExecutionContainer = styled.div`
  overflow-y: auto;
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
  max-height: ${props => props.$isExpanded ? '400px' : '0'};
  opacity: ${props => props.$isExpanded ? 1 : 0};
  overflow-y: auto;
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

const StepIcon = styled.div<{ $status: 'pending' | 'running' | 'completed' | 'error' }>`
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

const StepTimestamp = styled.div`
  font-size: 10px;
  color: ${props => props.theme.textSecondary};
  opacity: 0.7;
  margin-top: 4px;
`;

// Utility functions
const getStepIcon = (message: Message) => {
  if (message.text.includes('❌ **Error:**')) return <X size={10} />;
  if (message.text.includes('✅ **Output:**')) return <CheckCircle size={10} />;
  if (message.text.includes('💻 **Code Generated:**')) return <Code2 size={10} />;
  if (message.text.includes('📋 **Todo List Generated:**')) return <Terminal size={10} />;
  if (message.text.includes('📎 **Artifact')) return <Terminal size={10} />;
  return <Terminal size={10} />;
};

const getStepStatus = (message: Message): 'completed' | 'error' => {
  return message.text.includes('❌ **Error:**') ? 'error' : 'completed';
};

const getStepTitle = (message: Message, stepNumber: number): string => {
  if (message.text.includes('✅ **Output:**')) return `Step ${stepNumber}: Command Output`;
  if (message.text.includes('❌ **Error:**')) return `Step ${stepNumber}: Error Occurred`;
  if (message.text.includes('💻 **Code Generated:**')) return `Step ${stepNumber}: Code Generated`;
  if (message.text.includes('📋 **Todo List Generated:**')) return `Step ${stepNumber}: Todo List Created`;
  if (message.text.includes('📎 **Artifact')) return `Step ${stepNumber}: Artifact Created`;
  return `Step ${stepNumber}: Process Step`;
};

const getStepDescription = (message: Message): string => {
  // Remove markdown formatting and get first line
  const cleanText = message.text
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

  const hasErrors = steps.some(step => getStepStatus(step.message) === 'error');
  return hasErrors ? 'error' : 'completed';
};

const formatTimestamp = (timestamp: Date): string => {
  return timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

export const ExecutionStatus: React.FC<ExecutionStatusProps> = ({
  groupId,
  steps,
  isExpanded,
  onToggle,
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
        {steps.map((step) => {
          const codeBlock = extractCodeBlock(step.message);
          const status = getStepStatus(step.message);

          return (
            <ExecutionStep key={step.id} $isActive={false}>
              <StepIcon $status={status}>
                {getStepIcon(step.message)}
              </StepIcon>
              <StepContent>
                <h5>{getStepTitle(step.message, step.stepNumber)}</h5>
                <p>{getStepDescription(step.message)}</p>
                {codeBlock && (
                  <pre>{codeBlock.length > 200 ? codeBlock.substring(0, 200) + '\n...' : codeBlock}</pre>
                )}
                <StepTimestamp>
                  {formatTimestamp(step.message.timestamp)}
                </StepTimestamp>
              </StepContent>
            </ExecutionStep>
          );
        })}
      </ExecutionSteps>
    </ExecutionContainer>
  );
};