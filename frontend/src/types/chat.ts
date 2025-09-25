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
    artifactType?: 'code' | 'document' | 'chart' | 'html';
    artifactContent?: string;
    artifactLanguage?: string;
    artifactFilename?: string;
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
    type: 'code' | 'document' | 'chart' | 'html';
    title: string;
    content: string;
    language?: string;
    filename?: string;
    messageId?: string;
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
    onTodos?: (markdown: string) => void;
    onCode?: (text: string, filename?: string) => void;
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
}