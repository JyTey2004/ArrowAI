// src/components/sidebar/ChatItem.tsx
import React from 'react';
import styled, { keyframes } from 'styled-components';
import type { Chat } from '../../types/chat';

interface ChatItemProps {
    chat: Chat;
    isActive?: boolean;
    onClick: () => void;
}

const pulse = keyframes`
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
`;

const slideIn = keyframes`
  from { transform: translateX(-10px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
`;

const Container = styled.div<{ $isActive?: boolean }>`
  padding: 16px 18px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: ${props => props.$isActive ? props.theme.glassActive : props.theme.glassBackground};
  backdrop-filter: blur(8px) saturate(120%);
  border: 1px solid ${props => props.$isActive ? props.theme.accent : props.theme.glassBorder};
  position: relative;
  overflow: hidden;
  animation: ${slideIn} 0.4s ease-out;
  
  /* Active indicator */
  ${props => props.$isActive && `
    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 0;
      width: 3px;
      height: 100%;
      background: linear-gradient(180deg, ${props.theme.accent}, ${props.theme.accentHover});
      border-radius: 0 2px 2px 0;
    }
  `}
  
  /* Hover glow effect */
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, 
      ${props => props.theme.accent}10 0%, 
      transparent 50%, 
      ${props => props.theme.accent}05 100%
    );
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
  }
  
  &:hover {
    transform: translateX(6px) translateY(-2px);
    background: ${props => props.theme.glassHover};
    border-color: ${props => props.theme.accent};
    box-shadow: 
      0 8px 25px ${props => props.theme.accent}20,
      0 4px 12px rgba(0, 0, 0, 0.1);
    
    &::after {
      opacity: 1;
    }
  }
`;

const Title = styled.h3`
  font-size: 15px;
  font-weight: 600;
  color: ${props => props.theme.textPrimary};
  margin: 0 0 6px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
  letter-spacing: 0.3px;
`;

const Preview = styled.p`
  font-size: 13px;
  color: ${props => props.theme.textSecondary};
  margin: 0 0 8px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
  opacity: 0.8;
`;

const Timestamp = styled.span<{ $isActive?: boolean }>`
  font-size: 11px;
  color: ${props => props.$isActive ? props.theme.accent : props.theme.textSecondary};
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  animation: ${props => props.$isActive ? pulse : 'none'} 2s ease-in-out infinite;
`;

const formatTimestamp = (date: Date): string => {
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));

    if (diffInMinutes < 1) return 'Now';
    if (diffInMinutes < 60) return `${diffInMinutes}m`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h`;
    return `${Math.floor(diffInMinutes / 1440)}d`;
};

export const ChatItem: React.FC<ChatItemProps> = ({ chat, isActive, onClick }) => {
    return (
        <Container $isActive={isActive} onClick={onClick}>
            <Title>{chat.title}</Title>
            <Preview>{chat.preview}</Preview>
            <Timestamp $isActive={isActive}>{formatTimestamp(chat.timestamp)}</Timestamp>
        </Container>
    );
};