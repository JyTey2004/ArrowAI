// src/contexts/ChatContext.tsx
import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { Chat, Message, Artifact } from '../types/chat';

interface ChatContextType {
    chats: Chat[];
    activeChat: string | null;
    setActiveChat: (chatId: string) => void;
    addNewChat: () => void;
    currentView: 'home' | 'all-chats';
    setCurrentView: (view: 'home' | 'all-chats') => void;
    messages: Message[];
    addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;
    artifacts: Artifact[];
    activeArtifact: string | null;
    setActiveArtifact: (artifactId: string | null) => void;
    addArtifact: (artifact: Omit<Artifact, 'id'>) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

// Sample chats data
const initialChats: Chat[] = [
    {
        id: 'chat-1',
        title: 'React Component Design',
        preview: 'Creating a custom button component with TypeScript...',
        timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
    },
    {
        id: 'chat-2',
        title: 'API Integration Guide',
        preview: 'Setting up REST API calls with error handling...',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    },
    {
        id: 'chat-3',
        title: 'Data Visualization',
        preview: 'Building interactive charts with D3.js...',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    },
];

// Sample messages for active chat
const sampleMessages: Message[] = [
    {
        id: 'msg-1',
        text: 'Hi! I need help creating a React component. Can you help me build a custom button?',
        isUser: true,
        timestamp: new Date(Date.now() - 1000 * 60 * 15),
    },
    {
        id: 'msg-2',
        text: 'Absolutely! I\'ll help you create a custom React button component with TypeScript. Let me build that for you.',
        isUser: false,
        timestamp: new Date(Date.now() - 1000 * 60 * 14),
        hasArtifact: true,
        artifactType: 'code',
        artifactContent: `import React from 'react';
import styled from 'styled-components';

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
}

const StyledButton = styled.button<ButtonProps>\`
  padding: \${props => {
    switch(props.size) {
      case 'sm': return '8px 16px';
      case 'lg': return '16px 32px';
      default: return '12px 24px';
    }
  }};
  
  background: \${props => {
    switch(props.variant) {
      case 'primary': return '#3b82f6';
      case 'outline': return 'transparent';
      default: return '#6b7280';
    }
  }};
  
  color: \${props => props.variant === 'outline' ? '#3b82f6' : 'white'};
  border: \${props => props.variant === 'outline' ? '2px solid #3b82f6' : 'none'};
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
\`;

export const CustomButton: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  disabled = false,
  children,
  onClick
}) => {
  return (
    <StyledButton
      variant={variant}
      size={size}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </StyledButton>
  );
};`,
        artifactLanguage: 'typescript',
    },
    {
        id: 'msg-3',
        text: 'Perfect! This looks great. Can you also show me how to use this component?',
        isUser: true,
        timestamp: new Date(Date.now() - 1000 * 60 * 12),
    },
    {
        id: 'msg-4',
        text: 'Of course! Here\'s how you can use the CustomButton component in your app:',
        isUser: false,
        timestamp: new Date(Date.now() - 1000 * 60 * 11),
        hasArtifact: true,
        artifactType: 'code',
        artifactContent: `import React from 'react';
import { CustomButton } from './CustomButton';

const App: React.FC = () => {
  const handleClick = () => {
    alert('Button clicked!');
  };

  return (
    <div style={{ padding: '20px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
      <h1>Custom Button Examples</h1>
      
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <CustomButton variant="primary" onClick={handleClick}>
          Primary Button
        </CustomButton>
        
        <CustomButton variant="secondary" onClick={handleClick}>
          Secondary Button
        </CustomButton>
        
        <CustomButton variant="outline" onClick={handleClick}>
          Outline Button
        </CustomButton>
      </div>
      
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <CustomButton size="sm" onClick={handleClick}>
          Small
        </CustomButton>
        
        <CustomButton size="md" onClick={handleClick}>
          Medium
        </CustomButton>
        
        <CustomButton size="lg" onClick={handleClick}>
          Large
        </CustomButton>
      </div>
      
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <CustomButton onClick={handleClick}>
          Enabled
        </CustomButton>
        
        <CustomButton disabled>
          Disabled
        </CustomButton>
      </div>
    </div>
  );
};

export default App;`,
        artifactLanguage: 'typescript',
    }
];

interface ChatContextProviderProps {
    children: ReactNode;
}

export const ChatContextProvider: React.FC<ChatContextProviderProps> = ({ children }) => {
    const [chats, setChats] = useState<Chat[]>(initialChats);
    const [activeChat, setActiveChat] = useState<string | null>('chat-1');
    const [currentView, setCurrentView] = useState<'home' | 'all-chats'>('home');
    const [messages, setMessages] = useState<Message[]>(sampleMessages);
    const [isLoading, setIsLoading] = useState(false);
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [activeArtifact, setActiveArtifact] = useState<string | null>(null);

    const addNewChat = () => {
        const newChatId = `chat-${Date.now()}`;
        const newChat: Chat = {
            id: newChatId,
            title: 'New Chat',
            preview: 'Start a new conversation...',
            timestamp: new Date(),
        };

        setChats(prev => [newChat, ...prev]);
        setActiveChat(newChatId);
        setMessages([]); // Clear messages for new chat
        setCurrentView('home');
    };

    const addMessage = (messageData: Omit<Message, 'id' | 'timestamp'>) => {
        const newMessage: Message = {
            ...messageData,
            id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, newMessage]);

        // If message has an artifact, create it
        if (newMessage.hasArtifact && newMessage.artifactContent) {
            const newArtifact: Artifact = {
                id: `artifact-${Date.now()}`,
                type: newMessage.artifactType || 'code',
                title: `${newMessage.artifactType || 'Code'} from message`,
                content: newMessage.artifactContent,
                language: newMessage.artifactLanguage,
                messageId: newMessage.id,
            };
            addArtifact(newArtifact);
            setActiveArtifact(newArtifact.id);
        }
    };

    const addArtifact = (artifactData: Omit<Artifact, 'id'>) => {
        const newArtifact: Artifact = {
            ...artifactData,
            id: `artifact-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        };
        setArtifacts(prev => [...prev, newArtifact]);
    };

    // When active chat changes, load its messages
    const handleSetActiveChat = (chatId: string) => {
        setActiveChat(chatId);
        // In a real app, you'd load messages for this chat from an API
        if (chatId === 'chat-1') {
            setMessages(sampleMessages);
        } else {
            setMessages([
                {
                    id: 'welcome',
                    text: 'Hello! How can I help you today?',
                    isUser: false,
                    timestamp: new Date(),
                }
            ]);
        }
    };

    return (
        <ChatContext.Provider
            value={{
                chats,
                activeChat,
                setActiveChat: handleSetActiveChat,
                addNewChat,
                currentView,
                setCurrentView,
                messages,
                addMessage,
                isLoading,
                setIsLoading,
                artifacts,
                activeArtifact,
                setActiveArtifact,
                addArtifact
            }}
        >
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) {
        throw new Error('useChat must be used within ChatContextProvider');
    }
    return context;
};