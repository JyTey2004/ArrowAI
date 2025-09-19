// src/components/layout/MainLayout.tsx
import React from 'react';
import styled from 'styled-components';
import { Background } from './Background';
import { Sidebar } from '../sidebar/Sidebar';
import { useChat } from '../../contexts/ChatContext';

const Container = styled.div`
  display: flex;
  height: 100vh;
  width: 100vw;
  position: relative;
  overflow: hidden;
`;

const MainContent = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 24px;
  padding: 40px;
  z-index: 1;
  min-height: 100vh;
  background: ${props => props.theme.background};
`;

const Title = styled.h1`
  font-size: 3rem;
  background: linear-gradient(135deg, ${props => props.theme.accent || '#3b82f6'}, ${props => props.theme.accentHover || '#2563eb'});
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-align: center;
  margin-bottom: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 2px;
`;

const Subtitle = styled.p`
  font-size: 1.3rem;
  color: ${props => props.theme.textSecondary || '#64748b'};
  text-align: center;
  margin-bottom: 30px;
  font-weight: 400;
`;

const ChatInfo = styled.div`
  background: ${props => props.theme.glassBackground || 'rgba(255, 255, 255, 0.7)'};
  backdrop-filter: blur(15px) saturate(180%);
  border: 1px solid ${props => props.theme.glassBorder || 'rgba(59, 130, 246, 0.2)'};
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  max-width: 500px;
  position: relative;
  
  /* Blue accent border */
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, ${props => props.theme.accent || '#3b82f6'}20, transparent);
    border-radius: 16px;
    padding: 1px;
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask-composite: xor;
    -webkit-mask-composite: xor;
  }
`;

const InfoTitle = styled.h3`
  font-size: 1.2rem;
  color: ${props => props.theme.accent || '#3b82f6'};
  margin: 0 0 20px 0;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
`;

const InfoItem = styled.p`
  margin: 0 0 12px 0;
  font-size: 1rem;
  color: ${props => props.theme.textPrimary || '#1e293b'};
  
  strong {
    color: ${props => props.theme.accent || '#3b82f6'};
    font-weight: 600;
  }
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 20px;
`;

const StatCard = styled.div`
  background: ${props => props.theme.glassHover || 'rgba(59, 130, 246, 0.1)'};
  border: 1px solid ${props => props.theme.glassBorder || 'rgba(59, 130, 246, 0.2)'};
  border-radius: 12px;
  padding: 16px;
  text-align: center;
`;

const StatNumber = styled.div`
  font-size: 1.8rem;
  font-weight: 700;
  color: ${props => props.theme.accent || '#3b82f6'};
  margin-bottom: 4px;
`;

const StatLabel = styled.div`
  font-size: 0.9rem;
  color: ${props => props.theme.textSecondary || '#64748b'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const Description = styled.p`
  text-align: center;
  font-size: 1.1rem;
  color: ${props => props.theme.textSecondary || '#64748b'};
  max-width: 500px;
  line-height: 1.6;
  background: ${props => props.theme.glassBackground || 'rgba(255, 255, 255, 0.7)'};
  backdrop-filter: blur(8px);
  border: 1px solid ${props => props.theme.glassBorder || 'rgba(59, 130, 246, 0.2)'};
  border-radius: 12px;
  padding: 20px;
`;

export const MainLayout: React.FC = () => {
    const { activeChat, chats, currentView } = useChat();

    const activeChatData = chats.find(chat => chat.id === activeChat);

    return (
        <Container>
            <Background />
            <Sidebar />
            <MainContent>
                <Title>ArrowAI</Title>
                <Subtitle>Next-Generation Intelligent Conversation Interface</Subtitle>

                <ChatInfo>
                    <InfoTitle>System Status</InfoTitle>
                    <InfoItem>
                        <strong>Active View:</strong> {currentView === 'home' ? 'Home Dashboard' : 'All Conversations'}
                    </InfoItem>
                    <InfoItem>
                        <strong>Current Chat:</strong> {activeChatData ? activeChatData.title : 'None Selected'}
                    </InfoItem>

                    <StatsGrid>
                        <StatCard>
                            <StatNumber>{chats.length}</StatNumber>
                            <StatLabel>Total Chats</StatLabel>
                        </StatCard>
                        <StatCard>
                            <StatNumber>{activeChatData ? '1' : '0'}</StatNumber>
                            <StatLabel>Active Session</StatLabel>
                        </StatCard>
                    </StatsGrid>
                </ChatInfo>

                <Description>
                    Experience the future of AI conversation with our advanced glass-morphism interface.
                    Navigate seamlessly through your chat history, create new conversations, and customize
                    your experience with our dynamic theme system.
                </Description>
            </MainContent>
        </Container>
    );
};