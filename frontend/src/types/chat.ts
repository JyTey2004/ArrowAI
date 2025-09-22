// src/types/chat.ts
export interface Chat {
    id: string;
    title: string;
    preview: string;
    timestamp: Date;
    isActive?: boolean;
}

export interface Message {
    id: string;
    text: string;
    isUser: boolean;
    timestamp: Date;
    hasArtifact?: boolean;
    artifactType?: 'code' | 'document' | 'image' | 'chart';
    artifactContent?: string;
    artifactLanguage?: string;
}

export interface Artifact {
    id: string;
    type: 'code' | 'document' | 'image' | 'chart';
    title: string;
    content: string;
    language?: string;
    messageId: string;
}