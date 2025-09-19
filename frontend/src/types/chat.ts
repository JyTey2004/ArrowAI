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
}