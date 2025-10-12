// src/types/chat.ts
export interface Chat {
    id: string;
    title: string;
    preview: string;
    timestamp: Date;
}

export interface Message {
    id: string;
    text: string;
    isUser: boolean;
    timestamp: Date;
    hasArtifact?: boolean;
    artifactType?: string;
    artifactContent?: string;
    artifactLanguage?: string;
    artifactFilename?: string;
    artifactDownloadUrl?: string;
    artifactPreviewType?: string;
    artifactSize?: number;
    artifactTruncated?: boolean;
    artifactMetadata?: Record<string, unknown>;
    toolStep?: number;
    relatedArtifacts?: Artifact[];
    files?: AttachedFile[];
}

export interface AttachedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    url?: string;
    content?: string;
}

export interface Artifact {
    id: string;
    type: string;
    title: string;
    content: string;
    language?: string;
    filename?: string;
    messageId?: string;
    downloadUrl?: string;
    previewType?: string;
    size?: number;
    truncated?: boolean;
    metadata?: Record<string, unknown>;
    isLarge?: boolean;
    createdAt?: Date;
    updatedAt?: Date;
}

export interface FileUploadProgress {
    fileName: string;
    progress: number;
    status: 'uploading' | 'completed' | 'error';
    error?: string;
}

export interface WebSocketEventHandlers {
    onNode?: (name: string, step?: number) => void;
    onClarify?: (question: string) => void;
    onTodos?: (markdown: string, requiresFeedback?: boolean, source?: string) => void;
    onCode?: (text: string, filename?: string) => void;
    onThought?: (thought: string) => void;
    onToolCall?: (payload: { text?: string; tool?: string; description?: string; args?: Record<string, unknown>; server?: string | null; metadata?: Record<string, unknown> }) => void;
    onStatus?: (payload: Record<string, unknown>) => void;
    onStdout?: (text: string) => void;
    onStderr?: (text: string) => void;
    onArtifacts?: (items: any[]) => void;
    onAnswer?: (text: string) => void;
    onError?: (detail: string) => void;
    onConnect?: () => void;
    onDisconnect?: () => void;
    onFileUploadProgress?: (progress: number, fileName: string) => void;
    onFileUploadComplete?: (fileName: string) => void;
    onFileUploadError?: (error: string, fileName: string) => void;
    onTodoStatus?: (status: string) => void;
    onCel?: (content: string) => void;
}
