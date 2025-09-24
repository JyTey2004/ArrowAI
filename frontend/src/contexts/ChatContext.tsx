// src/contexts/ChatContext.tsx
import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { Chat, Message, Artifact } from '../types/chat';
import { AIWebSocketService, type FileUpload } from '../services/websocketService';

interface FileUploadState {
  id: string;
  file: File;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
}

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
  // WebSocket related
  sendMessage: (text: string, files?: File[]) => Promise<void>;
  isConnected: boolean;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  currentNode: string | null;
  clarificationQuestion: string | null;
  sendClarification: (text: string) => void;
  todos: string | null;
  executionStep: number;
  // File upload related
  fileUploads: FileUploadState[];
  clearCompletedUploads: () => void;
  getSupportedFileTypes: () => string[];
  validateFile: (file: File) => { valid: boolean; error?: string };
  getMaxFileSize: () => number;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

// Sample chats data
const initialChats: Chat[] = [
  {
    id: 'chat-1',
    title: 'Getting Started',
    preview: 'Welcome to the AI assistant...',
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
  },
];

interface ChatContextProviderProps {
  children: ReactNode;
  websocketUrl?: string;
}

export const ChatContextProvider: React.FC<ChatContextProviderProps> = ({
  children,
  websocketUrl = 'ws://localhost:8000'
}) => {
  const [chats, setChats] = useState<Chat[]>(initialChats);
  const [activeChat, setActiveChat] = useState<string | null>('chat-1');
  const [currentView, setCurrentView] = useState<'home' | 'all-chats'>('home');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);

  // WebSocket related state
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [todos, setTodos] = useState<string | null>(null);
  const [executionStep, setExecutionStep] = useState(0);

  // File upload state
  const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);

  const wsService = useRef<AIWebSocketService | null>(null);

  // Initialize WebSocket service
  useEffect(() => {
    wsService.current = new AIWebSocketService(websocketUrl);

    wsService.current.setCallbacks({
      onConnect: () => {
        console.log('Connected to AI WebSocket');
        setIsConnected(true);
        setConnectionStatus('connected');
      },

      onDisconnect: () => {
        console.log('Disconnected from AI WebSocket');
        setIsConnected(false);
        setConnectionStatus('disconnected');
      },

      onNode: (name, step) => {
        setCurrentNode(name);
        if (typeof step === 'number') {
          setExecutionStep(step);
        }
      },

      onClarify: (question) => {
        setClarificationQuestion(question);
        setIsLoading(false);
      },

      onTodos: (markdown) => {
        setTodos(markdown);
        // Add todos as a system message
        addMessage({
          text: `📋 **Todo List Generated:**\n\n${markdown}`,
          isUser: false,
          hasArtifact: true,
          artifactType: 'document',
          artifactContent: markdown,
        });
      },

      onCode: (text) => {
        // Add code as an artifact
        addMessage({
          text: '💻 **Code Generated:**',
          isUser: false,
          hasArtifact: true,
          artifactType: 'code',
          artifactContent: text,
          artifactLanguage: 'python', // Assuming Python based on your backend
        });
      },

      onStdout: (text) => {
        if (text.trim()) {
          addMessage({
            text: `✅ **Output:**\n\`\`\`\n${text}\n\`\`\``,
            isUser: false,
          });
        }
      },

      onStderr: (text) => {
        if (text.trim()) {
          addMessage({
            text: `❌ **Error:**\n\`\`\`\n${text}\n\`\`\``,
            isUser: false,
          });
        }
      },

      onArtifacts: (items) => {
        if (items && items.length > 0) {
          items.forEach((item, index) => {
            addMessage({
              text: `📎 **Artifact ${index + 1}:** ${item.name || 'Generated Artifact'}`,
              isUser: false,
              hasArtifact: true,
              artifactType: item.type || 'document',
              artifactContent: item.content || JSON.stringify(item, null, 2),
            });
          });
        }
      },

      onAnswer: (text) => {
        // Add the final answer
        addMessage({
          text,
          isUser: false,
        });
        setIsLoading(false);
        setCurrentNode(null);
      },

      onError: (detail) => {
        console.error('WebSocket error:', detail);
        addMessage({
          text: `⚠️ **Error:** ${detail}`,
          isUser: false,
        });
        setIsLoading(false);
        setCurrentNode(null);
      },

      // File upload callbacks
      onFileUploadProgress: (progress, fileName) => {
        setFileUploads(prev => prev.map(upload =>
          upload.file.name === fileName
            ? { ...upload, progress, status: 'uploading' as const }
            : upload
        ));
      },

      onFileUploadComplete: (fileName) => {
        setFileUploads(prev => prev.map(upload =>
          upload.file.name === fileName
            ? { ...upload, progress: 100, status: 'completed' as const }
            : upload
        ));
      },

      onFileUploadError: (error, fileName) => {
        setFileUploads(prev => prev.map(upload =>
          upload.file.name === fileName
            ? { ...upload, status: 'error' as const, error }
            : upload
        ));
      }
    });

    // Connect on mount
    connectWebSocket();

    return () => {
      wsService.current?.disconnect();
    };
  }, [websocketUrl]);

  const connectWebSocket = async () => {
    if (!wsService.current) return;

    setConnectionStatus('connecting');
    try {
      await wsService.current.connect();
    } catch (error) {
      console.error('Failed to connect:', error);
      setConnectionStatus('error');
    }
  };

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
    setMessages([]);
    setClarificationQuestion(null);
    setTodos(null);
    setCurrentNode(null);
    setExecutionStep(0);
    setCurrentView('home');
    setFileUploads([]);

    // Create new WebSocket session
    if (wsService.current) {
      wsService.current.newConversation();
    }
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

  const sendMessage = async (text: string, files: File[] = []) => {
    if (!wsService.current || !wsService.current.isConnected()) {
      throw new Error('Not connected to AI service');
    }

    // Validate files if provided
    if (files.length > 0) {
      for (const file of files) {
        const validation = wsService.current.validateFile(file);
        if (!validation.valid) {
          throw new Error(validation.error);
        }
      }

      // Add file upload states
      const newUploads: FileUploadState[] = files.map(file => ({
        id: `${Date.now()}_${file.name}`,
        file,
        progress: 0,
        status: 'uploading' as const
      }));

      setFileUploads(prev => [...prev, ...newUploads]);

      // Add a message showing the files being uploaded
      if (files.length > 0) {
        const fileList = files.map(f => `📎 ${f.name} (${(f.size / 1024).toFixed(1)} KB)`).join('\n');
        addMessage({
          text: `${text}\n\n**Uploaded files:**\n${fileList}`,
          isUser: true,
        });
      } else {
        addMessage({
          text,
          isUser: true,
        });
      }
    } else {
      // Add user message immediately
      addMessage({
        text,
        isUser: true,
      });
    }

    setIsLoading(true);
    setClarificationQuestion(null);

    try {
      wsService.current.sendMessage(text, files);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsLoading(false);
      addMessage({
        text: `⚠️ Failed to send message: ${error}`,
        isUser: false,
      });
    }
  };

  const sendClarification = (text: string) => {
    if (!wsService.current || !wsService.current.isConnected()) {
      throw new Error('Not connected to AI service');
    }

    // Add clarification as user message
    addMessage({
      text: `**Clarification:** ${text}`,
      isUser: true,
    });

    setClarificationQuestion(null);
    setIsLoading(true);

    try {
      wsService.current.sendClarification(text);
    } catch (error) {
      console.error('Failed to send clarification:', error);
      setIsLoading(false);
    }
  };

  const clearCompletedUploads = () => {
    setFileUploads(prev => prev.filter(upload => upload.status !== 'completed'));
  };

  // When active chat changes, load its messages
  const handleSetActiveChat = (chatId: string) => {
    setActiveChat(chatId);
    // In a real app, you'd load messages for this chat from storage/API
    setMessages([
      {
        id: 'welcome',
        text: 'Hello! I\'m your AI assistant. I can help you with coding, analysis, and creative projects. You can also upload files for me to analyze. What would you like to work on?',
        isUser: false,
        timestamp: new Date(),
      }
    ]);
    setFileUploads([]);
  };

  // File utility functions
  const getSupportedFileTypes = (): string[] => {
    return wsService.current?.getSupportedFileTypes() || [];
  };

  const validateFile = (file: File) => {
    return wsService.current?.validateFile(file) || { valid: false, error: 'Service not available' };
  };

  const getMaxFileSize = (): number => {
    return wsService.current?.getMaxFileSize() || 0;
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
        addArtifact,
        // WebSocket methods
        sendMessage,
        isConnected,
        connectionStatus,
        currentNode,
        clarificationQuestion,
        sendClarification,
        todos,
        executionStep,
        // File upload methods
        fileUploads,
        clearCompletedUploads,
        getSupportedFileTypes,
        validateFile,
        getMaxFileSize,
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