// src/services/websocketService.ts
export interface WebSocketMessage {
    event: string;
    [key: string]: any;
}

export interface WebSocketCallbacks {
    onNode?: (name: string, step?: number) => void;
    onClarify?: (question: string) => void;
    onTodos?: (markdown: string) => void;
    onCode?: (text: string) => void;
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

export interface FileUpload {
    file: File;
    name: string;
    size: number;
    type: string;
    content?: string | ArrayBuffer;
}

export class AIWebSocketService {
    private ws: WebSocket | null = null;
    private callbacks: WebSocketCallbacks = {};
    private runId: string;
    private baseUrl: string;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 3;
    private reconnectDelay = 1000;
    private uploadQueue: Map<string, FileUpload> = new Map();

    constructor(baseUrl: string = 'ws://localhost:8000') {
        this.baseUrl = baseUrl;
        this.runId = this.generateRunId();
    }

    private generateRunId(): string {
        return `run_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    setCallbacks(callbacks: WebSocketCallbacks) {
        this.callbacks = callbacks;
    }

    async connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            try {
                const wsUrl = `${this.baseUrl}/ws/assist?run_id=${this.runId}`;
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    this.callbacks.onConnect?.();
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data: WebSocketMessage = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };

                this.ws.onclose = (event) => {
                    console.log('WebSocket closed:', event.code, event.reason);
                    this.callbacks.onDisconnect?.();

                    // Attempt to reconnect unless it was a clean close
                    if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        setTimeout(() => {
                            console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
                            this.connect();
                        }, this.reconnectDelay * this.reconnectAttempts);
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(new Error('Failed to connect to WebSocket'));
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    private handleMessage(data: WebSocketMessage) {
        console.log('Received WebSocket message:', data);

        switch (data.event) {
            case 'node':
                this.callbacks.onNode?.(data.name, data.step);
                break;

            case 'clarify':
                this.callbacks.onClarify?.(data.question);
                break;

            case 'todos':
                this.callbacks.onTodos?.(data.markdown);
                break;

            case 'code':
                this.callbacks.onCode?.(data.text);
                break;

            case 'sandbox.stdout':
                this.callbacks.onStdout?.(data.text);
                break;

            case 'sandbox.stderr':
                this.callbacks.onStderr?.(data.text);
                break;

            case 'sandbox.artifacts':
                this.callbacks.onArtifacts?.(data.items);
                break;

            case 'answer':
                this.callbacks.onAnswer?.(data.text);
                break;

            case 'error':
                this.callbacks.onError?.(data.detail);
                break;

            case 'file_upload_progress':
                this.callbacks.onFileUploadProgress?.(data.progress, data.fileName);
                break;

            case 'file_upload_complete':
                this.callbacks.onFileUploadComplete?.(data.fileName);
                break;

            case 'file_upload_error':
                this.callbacks.onFileUploadError?.(data.error, data.fileName);
                break;

            default:
                console.log('Unhandled WebSocket event:', data.event);
        }
    }

    private async readFileAsBase64(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = reader.result as string;
                // Remove the data URL prefix (e.g., "data:text/plain;base64,")
                const base64 = result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    private async readFileAsText(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    private async processFile(file: File): Promise<FileUpload> {
        const uploadId = `${Date.now()}_${file.name}`;

        const fileUpload: FileUpload = {
            file,
            name: file.name,
            size: file.size,
            type: file.type,
        };

        // For text files, read as text; for others, read as base64
        const isTextFile = file.type.startsWith('text/') ||
            file.type === 'application/json' ||
            file.type === 'application/javascript' ||
            file.type === 'application/typescript' ||
            file.name.match(/\.(txt|md|csv|json|js|ts|py|html|css|xml|yaml|yml)$/i);

        try {
            if (isTextFile) {
                fileUpload.content = await this.readFileAsText(file);
            } else {
                fileUpload.content = await this.readFileAsBase64(file);
            }
        } catch (error) {
            throw new Error(`Failed to read file ${file.name}: ${error}`);
        }

        this.uploadQueue.set(uploadId, fileUpload);
        return fileUpload;
    }

    async uploadFiles(files: File[]): Promise<FileUpload[]> {
        const processedFiles: FileUpload[] = [];

        for (const file of files) {
            try {
                this.callbacks.onFileUploadProgress?.(0, file.name);
                const processedFile = await this.processFile(file);
                processedFiles.push(processedFile);
                this.callbacks.onFileUploadProgress?.(100, file.name);
                this.callbacks.onFileUploadComplete?.(file.name);
            } catch (error) {
                console.error(`Failed to process file ${file.name}:`, error);
                this.callbacks.onFileUploadError?.(error instanceof Error ? error.message : 'Unknown error', file.name);
            }
        }

        return processedFiles;
    }

    async sendMessage(text: string, files: File[] = []) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket is not connected');
        }

        let processedFiles: FileUpload[] = [];

        if (files.length > 0) {
            try {
                processedFiles = await this.uploadFiles(files);
            } catch (error) {
                console.error('File upload failed:', error);
                throw new Error('Failed to upload files');
            }
        }

        const message = {
            type: 'user_message',
            text,
            files: processedFiles.map(f => ({
                name: f.name,
                size: f.size,
                type: f.type,
                content: f.content,
                encoding: f.file.type.startsWith('text/') ||
                    f.file.type === 'application/json' ||
                    f.file.type === 'application/javascript' ||
                    f.file.type === 'application/typescript' ||
                    f.name.match(/\.(txt|md|csv|json|js|ts|py|html|css|xml|yaml|yml)$/i) ? 'text' : 'base64'
            }))
        };

        this.ws.send(JSON.stringify(message));
    }

    sendClarification(text: string) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket is not connected');
        }

        const message = {
            type: 'user_message',
            text
        };

        this.ws.send(JSON.stringify(message));
    }

    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'User disconnected');
            this.ws = null;
        }
        this.uploadQueue.clear();
    }

    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    getRunId(): string {
        return this.runId;
    }

    // Generate new run ID for new conversations
    newConversation() {
        this.runId = this.generateRunId();
        this.uploadQueue.clear();
    }

    // Get supported file types
    getSupportedFileTypes(): string[] {
        return [
            // Text files
            '.txt', '.md', '.csv', '.json', '.xml', '.yaml', '.yml',
            // Code files
            '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.cpp', '.c', '.h',
            '.css', '.html', '.php', '.rb', '.go', '.rs', '.swift', '.kt',
            // Data files
            '.xlsx', '.xls', '.pdf',
            // Images
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
            // Archives
            '.zip', '.tar', '.gz'
        ];
    }

    // Check if file type is supported
    isFileTypeSupported(file: File): boolean {
        const supportedTypes = this.getSupportedFileTypes();
        const extension = '.' + file.name.split('.').pop()?.toLowerCase();
        return supportedTypes.includes(extension);
    }

    // Get maximum file size (in bytes)
    getMaxFileSize(): number {
        return 10 * 1024 * 1024; // 10MB
    }

    // Validate file before upload
    validateFile(file: File): { valid: boolean; error?: string } {
        if (!this.isFileTypeSupported(file)) {
            return {
                valid: false,
                error: `File type not supported: ${file.name}. Supported types: ${this.getSupportedFileTypes().join(', ')}`
            };
        }

        if (file.size > this.getMaxFileSize()) {
            return {
                valid: false,
                error: `File too large: ${file.name}. Maximum size is ${Math.round(this.getMaxFileSize() / (1024 * 1024))}MB`
            };
        }

        return { valid: true };
    }
}