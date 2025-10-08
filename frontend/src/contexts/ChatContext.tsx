// src/contexts/ChatContext.tsx
import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { Chat, Message, Artifact } from '../types/chat';
import { AIWebSocketService, type FileUpload, type TodoFeedbackPayload } from '../services/websocketService';
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
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  artifacts: Artifact[];
  activeArtifact: string | null;
  setActiveArtifact: (artifactId: string | null) => void;
  celArtifactId: string | null;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => string;
  addArtifact: (artifact: Omit<Artifact, 'id'>) => string;
  sendMessage: (text: string, files?: File[]) => Promise<void>;
  isConnected: boolean;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  currentNode: string | null;
  clarificationQuestion: string | null;
  sendClarification: (text: string) => void;
  todos: string | null;
  awaitingTodoFeedback: boolean;
  submitTodoFeedback: (feedback: TodoFeedbackPayload) => Promise<void>;
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
  const [celArtifactId, setCelArtifactId] = useState<string | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [todos, setTodos] = useState<string | null>(null);
  const [awaitingTodoFeedback, setAwaitingTodoFeedback] = useState(false);
  const [executionStep, setExecutionStep] = useState(0);
  const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);

  const wsService = useRef<AIWebSocketService | null>(null);
  const toolStepCounter = useRef(0);
  const toolStepMessageMap = useRef<Record<number, string>>({});
  const lastToolStepRef = useRef(0);

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
        setAwaitingTodoFeedback(false);
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

      onTodos: (markdown, requiresFeedback = false, source) => {
        setTodos(markdown);
        if (requiresFeedback) {
          setAwaitingTodoFeedback(true);
          setIsLoading(false);
        } else {
          setAwaitingTodoFeedback(false);
        }

        if (requiresFeedback) {
          const intro = source === 'user'
            ? '📋 **Todo List Updated:**'
            : '📋 **Todo List Generated:**';
          addMessage({
            text: `${intro}\n\n${markdown}`,
            isUser: false,
            hasArtifact: true,
            artifactType: 'document',
            artifactContent: markdown,
          });
          addMessage({
            text: '✋ **Review the TODO list.**\nType `/approve` to accept as-is, or describe the changes you need and I will regenerate the plan automatically.',
            isUser: false,
          });
        } else {
          addMessage({
            text: source === 'approved'
              ? '✅ **Todo plan approved. Continuing execution.**'
              : '📋 **Todo list updated.**',
            isUser: false,
          });
        }
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

      onThought: (rawThought) => {
        let displayText = rawThought;
        try {
          const parsed = JSON.parse(rawThought);
          const tool = parsed.tool ? `**Tool:** ${parsed.tool}` : '';
          const args = parsed.args ? `\n\`\`\`json\n${JSON.stringify(parsed.args, null, 2)}\n\`\`\`` : '';
          displayText = `🤔 **Thought:** Preparing to call MCP.\n${tool}${args}`;
        } catch {
          displayText = `🤔 **Thought:** ${rawThought}`;
        }
        addMessage({
          text: displayText,
          isUser: false,
        });
      },

      onToolCall: ({ tool, description, args, server }) => {
        const step = toolStepCounter.current + 1;
        toolStepCounter.current = step;
        lastToolStepRef.current = step;

        const lines: string[] = [];
        const toolLabel = tool ? `**${tool}**` : 'Unknown tool';
        const serverTag = server ? ` _(via ${server})_` : '';
        lines.push(`🛠️ **Tool Call (Step ${step}):** ${toolLabel}${serverTag}`);
        if (description) {
          lines.push(description);
        }
        if (args && Object.keys(args).length > 0) {
          lines.push('');
          lines.push('**Arguments:**');
          lines.push('```json');
          lines.push(JSON.stringify(args, null, 2));
          lines.push('```');
        }

        const messageId = addMessage({
          text: lines.join('\n'),
          isUser: false,
          toolStep: step,
        });
        toolStepMessageMap.current[step] = messageId;
      },

      onStatus: (payload) => {
        const stepNumber = typeof payload.step === 'number' ? payload.step : (payload.step ?? '?');
        const statusText = typeof payload.status === 'string' ? payload.status.toUpperCase() : 'IN PROGRESS';
        const plan = typeof payload.plan === 'string' ? payload.plan : '';
        const summary = typeof payload.summary === 'string' ? payload.summary : '';

        let text = `🚧 **Step ${stepNumber}: ${statusText}**`;
        if (plan) {
          text += `\n${plan}`;
        }
        if (summary) {
          text += `\n\n${summary}`;
        }

        addMessage({
          text,
          isUser: false,
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
          items.forEach((item) => {
            const filename = item.filename || item.name;
            const language = detectLanguageFromFilename(filename) || item.language;
            const previewType = item.preview_type || item.previewType;
            const downloadUrl = item.download_url || item.view_url || item.url;
            const truncated = Boolean(item.truncated);
            const size = typeof item.size === 'number' ? item.size : undefined;
            const isLarge = Boolean(item.is_large ?? item.isLarge);
            const stepFromItem = typeof item.step === 'number' ? item.step : lastToolStepRef.current || toolStepCounter.current;
            const targetMessageId = stepFromItem ? toolStepMessageMap.current[stepFromItem] : undefined;

            let artifactType = item.type || 'document';
            if (!artifactType && previewType === 'image') {
              artifactType = 'image';
            }
            if (artifactType === 'image' && !downloadUrl && typeof item.content !== 'string') {
              artifactType = 'document';
            }

            let artifactContent: string;
            if (previewType === 'image' && downloadUrl) {
              artifactContent = `![${filename || 'image'}](${downloadUrl})`;
            } else if (typeof item.content === 'string' && item.content.trim().length > 0) {
              artifactContent = item.content;
            } else if (downloadUrl) {
              artifactContent = `Download the artifact here: ${downloadUrl}`;
            } else {
              artifactContent = JSON.stringify(item, null, 2);
            }

            if (isLarge && downloadUrl) {
              artifactContent += `\n\n_(Preview trimmed due to size. Download link provided.)_`;
            }

            const artifactPayload: Omit<Artifact, 'id'> = {
              type: artifactType,
              title: filename || 'Generated Artifact',
              content: artifactContent,
              language,
              filename,
              messageId: targetMessageId,
              downloadUrl,
              previewType,
              size,
              truncated,
              metadata: item,
              isLarge,
            };

            if (targetMessageId) {
              const artifactId = addArtifact(artifactPayload);
              setActiveArtifact(artifactId);
              const relatedArtifact: Artifact = { ...artifactPayload, id: artifactId };

              setMessages(prev =>
                prev.map(msg => {
                  if (msg.id !== targetMessageId) {
                    return msg;
                  }
                  const existing = msg.relatedArtifacts ?? [];
                  return {
                    ...msg,
                    hasArtifact: true,
                    relatedArtifacts: [...existing, relatedArtifact],
                  };
                })
              );
            } else {
              // No corresponding tool message; fall back to standalone artifact message
              addMessage({
                text: `📎 **Artifact:** ${filename || 'Generated Artifact'}`,
                isUser: false,
                hasArtifact: true,
                artifactType,
                artifactContent,
                artifactLanguage: language,
                artifactFilename: filename,
                artifactDownloadUrl: downloadUrl,
                artifactPreviewType: previewType,
                artifactSize: size,
                artifactTruncated: truncated,
                artifactMetadata: item,
              });
            }
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
        setAwaitingTodoFeedback(false);
      },

      onError: (detail) => {
        console.error('WebSocket error:', detail);
        addMessage({
          text: `⚠️ **Error:** ${detail}`,
          isUser: false,
        });
        setIsLoading(false);
        setCurrentNode(null);
        setAwaitingTodoFeedback(false);
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
      },

      onTodoStatus: (status) => {
        if (status === 'approved') {
          setAwaitingTodoFeedback(false);
          setIsLoading(false);
        } else if (status === 'updating') {
          setIsLoading(true);
          setAwaitingTodoFeedback(true);
        }
      },

      onCel: (celContent) => {
        let nextCelId = '';
        const normalized = typeof celContent === 'string' ? celContent : '';

        setArtifacts(prev => {
          const existingIndex = prev.findIndex(artifact =>
            (artifact.metadata && (artifact.metadata as Record<string, unknown>)?.isCel === true) ||
            (artifact.filename && artifact.filename.toLowerCase() === 'cel.md')
          );

          if (!normalized && existingIndex === -1) {
            return prev;
          }

          const baseFields: Omit<Artifact, 'id'> = {
            type: 'document',
            title: 'CEL.md',
            content: normalized,
            language: 'markdown',
            filename: 'CEL.md',
            previewType: 'text',
            truncated: false,
            metadata: { isCel: true },
            size: normalized.length,
          };

          if (existingIndex >= 0) {
            const existing = prev[existingIndex];
            nextCelId = existing.id;
            const updatedArtifact: Artifact = {
              ...existing,
              ...baseFields,
              id: existing.id,
              metadata: { ...(existing.metadata ?? {}), isCel: true },
              size: normalized.length,
            };

            const next = [...prev];
            next[existingIndex] = updatedArtifact;
            return next;
          }

          nextCelId = `artifact-cel-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
          const celArtifact: Artifact = {
            ...baseFields,
            id: nextCelId,
          };
          return [...prev, celArtifact];
        });

        if (nextCelId) {
          setCelArtifactId(nextCelId);
        }
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
    setAwaitingTodoFeedback(false);
    setCurrentNode(null);
    setExecutionStep(0);
    setCurrentView('home');
    setFileUploads([]);
    setArtifacts([]);
    setActiveArtifact(null);
    setCelArtifactId(null);
    toolStepCounter.current = 0;
    toolStepMessageMap.current = {};
    lastToolStepRef.current = 0;

    return newChatId;
  };

  const addArtifact = (artifactData: Omit<Artifact, 'id'>): string => {
    let generatedId = '';

    setArtifacts(prev => {
      const fallbackText = 'Artifact available. Download to view.';
      const isFallback =
        !artifactData.content ||
        artifactData.content.trim().length === 0 ||
        artifactData.content.trim().startsWith(fallbackText);

      let enrichedArtifact = { ...artifactData };

      if (isFallback) {
        const matching = prev.find(existing => {
          const sameFilename = existing.filename && artifactData.filename
            ? existing.filename === artifactData.filename
            : false;
          const sameTitle = existing.title === artifactData.title;
          return (sameFilename || sameTitle) &&
            existing.content &&
            !existing.content.trim().startsWith(fallbackText);
        });

        if (matching) {
          enrichedArtifact = {
            ...enrichedArtifact,
            content: matching.content,
            language: enrichedArtifact.language ?? matching.language,
            downloadUrl: enrichedArtifact.downloadUrl ?? matching.downloadUrl,
            previewType: enrichedArtifact.previewType ?? matching.previewType,
            truncated: enrichedArtifact.truncated ?? matching.truncated,
            size: enrichedArtifact.size ?? matching.size,
            isLarge: enrichedArtifact.isLarge ?? matching.isLarge,
            metadata: { ...(matching.metadata ?? {}), ...(enrichedArtifact.metadata ?? {}) },
          };
        }
      }

      const duplicateIndex = prev.findIndex(existing => {
        if (enrichedArtifact.messageId && existing.messageId === enrichedArtifact.messageId) {
          if (enrichedArtifact.filename && existing.filename) {
            return existing.filename === enrichedArtifact.filename;
          }
          if (enrichedArtifact.title) {
            return existing.title === enrichedArtifact.title;
          }
        }
        if (enrichedArtifact.downloadUrl && existing.downloadUrl) {
          return enrichedArtifact.downloadUrl === existing.downloadUrl;
        }
        return false;
      });

      if (duplicateIndex >= 0) {
        const existing = prev[duplicateIndex];
        generatedId = existing.id;
        const updatedArtifact: Artifact = {
          ...existing,
          ...enrichedArtifact,
          id: existing.id,
          metadata: { ...(existing.metadata ?? {}), ...(enrichedArtifact.metadata ?? {}) },
        };

        const next = [...prev];
        next[duplicateIndex] = updatedArtifact;
        return next;
      }

      const newArtifact: Artifact = {
        ...enrichedArtifact,
        id: `artifact-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      };
      generatedId = newArtifact.id;
      return [...prev, newArtifact];
    });

    return generatedId;
  };

  const addMessage = (messageData: Omit<Message, 'id' | 'timestamp'>): string => {
    const newMessageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const timestamp = new Date();
    let relatedArtifacts: Artifact[] | undefined;

    if (messageData.hasArtifact && messageData.artifactContent) {
      const artifactTitle = messageData.artifactFilename ||
        `${messageData.artifactType || 'Code'} from message`;
      const artifactMeta = messageData.artifactMetadata as Record<string, unknown> | undefined;
      const isLargeFlag = Boolean(artifactMeta?.['is_large'] ?? artifactMeta?.['isLarge']);

      const artifactPayload: Omit<Artifact, 'id'> = {
        type: messageData.artifactType || 'code',
        title: artifactTitle,
        content: messageData.artifactContent,
        language: messageData.artifactLanguage,
        filename: messageData.artifactFilename,
        messageId: newMessageId,
        downloadUrl: messageData.artifactDownloadUrl,
        previewType: messageData.artifactPreviewType,
        size: messageData.artifactSize,
        truncated: messageData.artifactTruncated,
        metadata: artifactMeta,
        isLarge: isLargeFlag,
      };
      const artifactId = addArtifact(artifactPayload);
      setActiveArtifact(artifactId);
      relatedArtifacts = [{ ...artifactPayload, id: artifactId }];
    }

    const newMessage: Message = {
      ...messageData,
      id: newMessageId,
      timestamp,
      relatedArtifacts,
    };

    setMessages(prev => [...prev, newMessage]);
    return newMessage.id;
  };

  const sendMessage = async (text: string, files: File[] = []) => {
    if (!wsService.current || !wsService.current.isConnected()) {
      throw new Error('Not connected to AI service');
    }

    const trimmedInput = (text || '').trim();

    if (awaitingTodoFeedback) {
      if (!trimmedInput) {
        throw new Error('Provide feedback for the TODO list before continuing.');
      }
      if (files.length > 0) {
        throw new Error('File uploads are not allowed while reviewing the TODO list.');
      }

      const approveCommand = '/approve';
      const isApprove = trimmedInput.toLowerCase().startsWith(approveCommand);
      const commentText = isApprove ? trimmedInput.slice(approveCommand.length).trim() : trimmedInput;

      if (isApprove && (!todos || todos.trim().length === 0)) {
        throw new Error('There is no TODO list to approve.');
      }

      const looksLikeTodoMarkdown = (value: string) => {
        const lines = value.trim().split('\n').filter(line => line.trim().length > 0);
        if (lines.length === 0) return false;
        const todoLines = lines.filter(line => /^(\s*[-*]\s+\[[ xX]\]|\s*\d+\.\s+|\s*[-*]\s+)/.test(line));
        return todoLines.length >= Math.max(1, Math.ceil(lines.length * 0.5));
      };

      const feedbackMarkdown = !isApprove && looksLikeTodoMarkdown(trimmedInput) ? trimmedInput : undefined;

      addMessage({
        text,
        isUser: true,
      });

      setClarificationQuestion(null);
      setIsLoading(true);

      try {
        await submitTodoFeedback({
          decision: isApprove ? 'approve' : 'update',
          markdown: isApprove ? (todos ?? '') : feedbackMarkdown,
          comment: commentText || undefined,
        });
      } catch (error) {
        console.error('Failed to send TODO feedback:', error);
        setIsLoading(false);
        addMessage({
          text: `⚠️ Failed to send TODO feedback: ${error instanceof Error ? error.message : error}`,
          isUser: false,
        });
        throw error;
      }
      return;
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

  const submitTodoFeedback = async ({ decision, markdown, comment }: TodoFeedbackPayload) => {
    if (!wsService.current || !wsService.current.isConnected()) {
      throw new Error('Not connected to AI service');
    }

    const trimmedMarkdown = markdown?.trim();
    const trimmedComment = comment?.trim();

    if (decision === 'update') {
      if (!trimmedMarkdown && !trimmedComment) {
        throw new Error('Provide feedback or updated TODO details before requesting changes.');
      }
      if (trimmedMarkdown) {
        setTodos(trimmedMarkdown);
      }
    } else {
      setAwaitingTodoFeedback(false);
    }

    setIsLoading(true);

    try {
      wsService.current.sendTodoFeedback({
        decision,
        markdown: trimmedMarkdown,
        comment: trimmedComment,
      });
    } catch (error) {
      if (decision === 'approve') {
        setAwaitingTodoFeedback(true);
        setIsLoading(false);
      } else {
        setIsLoading(false);
      }
      console.error('Failed to send TODO feedback:', error);
      throw error instanceof Error ? error : new Error('Failed to send TODO feedback');
    }
  };

  const clearCompletedUploads = () => {
    setFileUploads(prev => prev.filter(upload => upload.status !== 'completed'));
  };

  const handleSetActiveChat = (chatId: string) => {
    setActiveChat(chatId);
    toolStepCounter.current = 0;
    toolStepMessageMap.current = {};
    lastToolStepRef.current = 0;

    const existingChat = chats.find(chat => chat.id === chatId);

    if (existingChat && messages.length === 0) {
      setMessages([]);
      setClarificationQuestion(null);
      setTodos(null);
      setAwaitingTodoFeedback(false);
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
        celArtifactId,
        addArtifact,
        sendMessage,
        isConnected,
        connectionStatus,
        currentNode,
        clarificationQuestion,
        sendClarification,
        todos,
        awaitingTodoFeedback,
        submitTodoFeedback,
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
