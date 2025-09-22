// src/components/layout/MainLayout.tsx
import React from 'react';
import styled from 'styled-components';
import { Background } from './Background';
import { Sidebar } from '../sidebar/Sidebar';
import { ChatInterface } from '../chat/ChatInterface';
import { useChat } from '../../contexts/ChatContext';

const Container = styled.div`
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: ${props => props.theme.background};
`;

const MainContent = styled.div`
  flex: 1;
  display: flex;
  height: 100vh;
  overflow: hidden;
`;

const WelcomeScreen = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 24px;
  padding: 40px;
  text-align: center;
`;

const WelcomeIcon = styled.div`
  font-size: 64px;
  opacity: 0.6;
  margin-bottom: 8px;
`;

const WelcomeTitle = styled.h2`
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, ${props => props.theme.accent}, ${props => props.theme.accentHover});
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
`;

const WelcomeText = styled.p`
  font-size: 16px;
  color: ${props => props.theme.textSecondary};
  max-width: 480px;
  line-height: 1.6;
  margin: 0;
`;

const WelcomeCard = styled.div`
  background: ${props => props.theme.glassBackground};
  backdrop-filter: blur(12px);
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: 16px;
  padding: 32px;
  max-width: 500px;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, 
      ${props => props.theme.accent}10 0%, 
      transparent 100%
    );
    border-radius: 16px;
    pointer-events: none;
  }
`;

const QuickActions = styled.div`
  display: flex;
  gap: 12px;
  margin-top: 24px;
  justify-content: center;
`;

const QuickActionButton = styled.button`
  padding: 12px 20px;
  background: ${props => props.theme.glassBackground};
  border: 1px solid ${props => props.theme.glassBorder};
  border-radius: 8px;
  color: ${props => props.theme.textPrimary};
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 8px;

  &:hover {
    background: ${props => props.theme.glassHover};
    border-color: ${props => props.theme.accent};
    transform: translateY(-1px);
  }
`;

export const MainLayout: React.FC = () => {
  const { activeChat, addNewChat, chats } = useChat();

  return (
    <Container>
      <Background />
      <Sidebar />
      <MainContent>
        {activeChat ? (
          <ChatInterface />
        ) : (
          <WelcomeScreen>
            <WelcomeCard>
              <WelcomeIcon>🚀</WelcomeIcon>
              <WelcomeTitle>Welcome to ArrowAI</WelcomeTitle>
              <WelcomeText>
                Your intelligent conversation partner is ready to help with coding,
                creative projects, analysis, and much more. Start a new conversation
                or select an existing chat to continue.
              </WelcomeText>

              <QuickActions>
                <QuickActionButton onClick={addNewChat}>
                  ➕ New Chat
                </QuickActionButton>
                <QuickActionButton disabled={chats.length === 0}>
                  📚 Browse Chats ({chats.length})
                </QuickActionButton>
              </QuickActions>
            </WelcomeCard>
          </WelcomeScreen>
        )}
      </MainContent>
    </Container>
  );
};