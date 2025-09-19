// src/contexts/ChatContext.tsx
import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { Chat } from '../types/chat'

interface ChatContextType {
    chats: Chat[];
    activeChat: string | null;
    setActiveChat: (chatId: string) => void;
    addNewChat: () => void;
    currentView: 'home' | 'all-chats';
    setCurrentView: (view: 'home' | 'all-chats') => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

// Sample chats data
const initialChats: Chat[] = [
    {
        id: '1',
        title: 'Getting Started',
        preview: 'How to use this AI chat interface...',
        timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
    },
    {
        id: '2',
        title: 'React Development',
        preview: 'Best practices for React components...',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    },
    {
        id: '3',
        title: 'TypeScript Tips',
        preview: 'Advanced TypeScript techniques...',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    },
];

interface ChatContextProviderProps {
    children: ReactNode;
}

export const ChatContextProvider: React.FC<ChatContextProviderProps> = ({ children }) => {
    const [chats, setChats] = useState<Chat[]>(initialChats);
    const [activeChat, setActiveChat] = useState<string | null>('1');
    const [currentView, setCurrentView] = useState<'home' | 'all-chats'>('home');

    const addNewChat = () => {
        const newChat: Chat = {
            id: Date.now().toString(),
            title: 'New Chat',
            preview: 'Start a new conversation...',
            timestamp: new Date(),
        };

        setChats(prev => [newChat, ...prev]);
        setActiveChat(newChat.id);
        setCurrentView('home');
    };

    return (
        <ChatContext.Provider
            value={{
                chats,
                activeChat,
                setActiveChat,
                addNewChat,
                currentView,
                setCurrentView
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