// src/contexts/ChatContext.tsx
import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { Chat, Message, Artifact } from '../types/chat';
import { AIWebSocketService, type FileUpload } from '../services/websocketService';
import { v4 as uuidv4 } from 'uuid';

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
  addNewChat: () => string;
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
  sendMessage: (text: string, files?: File[]) => Promise<void>;
  isConnected: boolean;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  currentNode: string | null;
  clarificationQuestion: string | null;
  sendClarification: (text: string) => void;
  todos: string | null;
  executionStep: number;
  fileUploads: FileUploadState[];
  clearCompletedUploads: () => void;
  getSupportedFileTypes: () => string[];
  validateFile: (file: File) => { valid: boolean; error?: string };
  getMaxFileSize: () => number;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const initialChats: Chat[] = [];

interface ChatContextProviderProps {
  children: ReactNode;
  websocketUrl?: string;
}

export const ChatContextProvider: React.FC<ChatContextProviderProps> = ({
  children,
  websocketUrl = 'ws://localhost:8000'
}) => {
  const [chats, setChats] = useState<Chat[]>(initialChats);
  const [activeChat, setActiveChat] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<'home' | 'all-chats'>('home');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [todos, setTodos] = useState<string | null>(null);
  const [executionStep, setExecutionStep] = useState(0);
  const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);

  const wsService = useRef<AIWebSocketService | null>(null);

  // Initialize WebSocket service (don't connect yet)
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
        addMessage({
          text: `📋 **Todo List Generated:**\n\n${markdown}`,
          isUser: false,
          hasArtifact: true,
          artifactType: 'document',
          artifactContent: markdown,
        });
      },

      onCode: (text, filename) => {
        addMessage({
          text: filename ? `💻 **Code Generated:** ${filename}` : '💻 **Code Generated:**',
          isUser: false,
          hasArtifact: true,
          artifactType: 'code',
          artifactContent: text,
          artifactLanguage: detectLanguageFromFilename(filename) || 'python',
          artifactFilename: filename,
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
            const filename = item.filename || item.name;
            const language = detectLanguageFromFilename(filename) || item.language;

            addMessage({
              text: `📎 **Artifact ${index + 1}:** ${filename || 'Generated Artifact'}`,
              isUser: false,
              hasArtifact: true,
              artifactType: item.type || 'document',
              artifactContent: item.content || JSON.stringify(item, null, 2),
              artifactLanguage: language,
              artifactFilename: filename,
            });
          });
        }
      },

      onAnswer: (text) => {
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

    return () => {
      wsService.current?.disconnect();
    };
  }, [websocketUrl]);

  // Connect WebSocket when activeChat changes
  useEffect(() => {
    const connectToChat = async () => {
      if (!wsService.current || !activeChat) return;

      // Disconnect any existing connection
      if (wsService.current.isConnected()) {
        wsService.current.disconnect();
      }

      setConnectionStatus('connecting');
      try {
        // Connect with the active chat UUID
        await wsService.current.connect(activeChat);
        console.log('Connected to chat:', activeChat);
      } catch (error) {
        console.error('Failed to connect:', error);
        setConnectionStatus('error');
      }
    };

    connectToChat();
  }, [activeChat]);

  const addNewChat = (): string => {
    const newChatId = uuidv4();
    const newChat: Chat = {
      id: newChatId,
      title: 'New Chat',
      preview: 'Start a new conversation...',
      timestamp: new Date(),
    };

    setChats(prev => [newChat, ...prev]);
    setActiveChat(newChatId); // This triggers WebSocket connection
    setMessages([]);
    setClarificationQuestion(null);
    setTodos(null);
    setCurrentNode(null);
    setExecutionStep(0);
    setCurrentView('home');
    setFileUploads([]);

    return newChatId;
  };

  const addMessage = (messageData: Omit<Message, 'id' | 'timestamp'>) => {
    const newMessage: Message = {
      ...messageData,
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, newMessage]);

    if (newMessage.hasArtifact && newMessage.artifactContent) {
      const artifactTitle = newMessage.artifactFilename ||
        `${newMessage.artifactType || 'Code'} from message`;

      const newArtifact: Artifact = {
        id: `artifact-${Date.now()}`,
        type: newMessage.artifactType || 'code',
        title: artifactTitle,
        content: newMessage.artifactContent,
        language: newMessage.artifactLanguage,
        filename: newMessage.artifactFilename,
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

    if (files.length > 0) {
      for (const file of files) {
        const validation = wsService.current.validateFile(file);
        if (!validation.valid) {
          throw new Error(validation.error);
        }
      }

      const newUploads: FileUploadState[] = files.map(file => ({
        id: `${Date.now()}_${file.name}`,
        file,
        progress: 0,
        status: 'uploading' as const
      }));

      setFileUploads(prev => [...prev, ...newUploads]);

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

  const handleSetActiveChat = (chatId: string) => {
    setActiveChat(chatId);

    const existingChat = chats.find(chat => chat.id === chatId);

    if (existingChat && messages.length === 0) {
      setMessages([]);
      setClarificationQuestion(null);
      setTodos(null);
      setCurrentNode(null);
      setExecutionStep(0);
    }

    setFileUploads([]);
  };

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
        sendMessage,
        isConnected,
        connectionStatus,
        currentNode,
        clarificationQuestion,
        sendClarification,
        todos,
        executionStep,
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

const detectLanguageFromFilename = (filename?: string): string | undefined => {
  if (!filename) return undefined;

  const extension = filename.split('.').pop()?.toLowerCase();

  const languageMap: Record<string, string> = {
    'py': 'python',
    'js': 'javascript',
    'ts': 'typescript',
    'jsx': 'javascript',
    'tsx': 'typescript',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'r': 'r',
    'sql': 'sql',
    'sh': 'bash',
    'bash': 'bash',
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'xml': 'xml',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'md': 'markdown',
    'txt': 'text',
  };

  return extension ? languageMap[extension] : undefined;
};