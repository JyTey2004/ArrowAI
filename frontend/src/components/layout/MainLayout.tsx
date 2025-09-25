// src/components/layout/MainLayout.tsx
import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { Sidebar } from '../sidebar/Sidebar';
import { ChatInterface } from '../chat/ChatInterface';
import { useChat } from '../../contexts/ChatContext';

const LayoutContainer = styled.div`
  display: flex;
  height: 100vh;
  width: 100%;
  background: ${props => props.theme.background};
`;

const ContentArea = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

// Wrapper component to handle chat loading by UUID
const ChatWrapper: React.FC = () => {
  const { chatId } = useParams<{ chatId: string }>();
  const navigate = useNavigate();
  const { setActiveChat, chats } = useChat();
  const [isInitialized, setIsInitialized] = React.useState(false);

  useEffect(() => {
    if (!chatId || isInitialized) return;

    // Check if chat exists
    const chatExists = chats.find(chat => chat.id === chatId);

    if (chatExists) {
      setActiveChat(chatId);
      setIsInitialized(true);
    } else {
      // Chat doesn't exist - check if it's a valid UUID format
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

      if (uuidRegex.test(chatId)) {
        // It's a valid UUID that doesn't exist - create a new chat with this ID
        // Or redirect to home if you don't want to preserve the UUID
        console.warn(`Chat ${chatId} not found, redirecting to home`);
        navigate('/', { replace: true });
      } else {
        // Invalid UUID format - redirect to home
        navigate('/', { replace: true });
      }
    }
  }, [chatId, chats, setActiveChat, navigate, isInitialized]);

  // Only render if initialized
  if (!isInitialized && chatId) {
    return null; // or a loading spinner
  }

  return <ChatInterface />;
};

// Home page component
const HomePage: React.FC = () => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      flexDirection: 'column',
      gap: '20px',
      padding: '40px'
    }}>
      <h1 style={{ fontSize: '32px', fontWeight: 600 }}>Welcome to ArrowAI</h1>
      <p style={{ fontSize: '16px', color: '#64748b', textAlign: 'center', maxWidth: '500px' }}>
        Start a new conversation or select a recent chat from the sidebar.
      </p>
    </div>
  );
};

// Archive page component
const ArchivePage: React.FC = () => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      flexDirection: 'column',
      gap: '20px',
      padding: '40px'
    }}>
      <h1 style={{ fontSize: '32px', fontWeight: 600 }}>Chat Archive</h1>
      <p style={{ fontSize: '16px', color: '#64748b', textAlign: 'center', maxWidth: '500px' }}>
        View all your conversations in the sidebar.
      </p>
    </div>
  );
};

// Profile page placeholder
const ProfilePage: React.FC = () => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      flexDirection: 'column',
      gap: '20px',
      padding: '40px'
    }}>
      <h1 style={{ fontSize: '32px', fontWeight: 600 }}>User Profile</h1>
      <p style={{ fontSize: '16px', color: '#64748b', textAlign: 'center', maxWidth: '500px' }}>
        Profile settings coming soon...
      </p>
    </div>
  );
};

// Settings page placeholder
const SettingsPage: React.FC = () => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      flexDirection: 'column',
      gap: '20px',
      padding: '40px'
    }}>
      <h1 style={{ fontSize: '32px', fontWeight: 600 }}>Settings</h1>
      <p style={{ fontSize: '16px', color: '#64748b', textAlign: 'center', maxWidth: '500px' }}>
        Application settings coming soon...
      </p>
    </div>
  );
};

export const MainLayout: React.FC = () => {
  return (
    <LayoutContainer>
      <Sidebar />
      <ContentArea>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/chat/:chatId" element={<ChatWrapper />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ContentArea>
    </LayoutContainer>
  );
};