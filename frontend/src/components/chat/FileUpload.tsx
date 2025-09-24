// src/components/chat/FileUpload.tsx
import React, { useRef, useState } from 'react';
import styled from 'styled-components';
import { Upload, X, File, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { useChat } from '../../contexts/ChatContext';

const FileUploadContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const DropZone = styled.div<{ $isDragOver: boolean; $hasFiles: boolean }>`
  border: 2px dashed ${props =>
        props.$isDragOver ? props.theme.accent :
            props.$hasFiles ? props.theme.accent + '60' :
                props.theme.glassBorder
    };
  border-radius: 12px;
  padding: ${props => props.$hasFiles ? '12px' : '20px'};
  text-align: center;
  background: ${props => props.$isDragOver ? props.theme.accent + '10' : props.theme.glassBackground};
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: ${props => props.theme.accent};
    background: ${props => props.theme.accent}08;
  }
`;

const DropZoneContent = styled.div<{ $hasFiles: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: ${props => props.theme.textSecondary};
  font-size: ${props => props.$hasFiles ? '12px' : '14px'};
`;

const UploadIcon = styled.div<{ $hasFiles: boolean }>`
  font-size: ${props => props.$hasFiles ? '16px' : '24px'};
  color: ${props => props.theme.accent};
  opacity: 0.7;
`;

const FileList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const FileItem = styled.div<{ $status: 'uploading' | 'completed' | 'error' | 'pending' }>`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: ${props => props.theme.glassBackground};
  border: 1px solid ${props => {
        switch (props.$status) {
            case 'completed': return props.theme.success || '#22c55e';
            case 'error': return props.theme.error || '#ef4444';
            case 'uploading': return props.theme.accent;
            default: return props.theme.glassBorder;
        }
    }};
  border-radius: 8px;
  font-size: 12px;
`;

const FileInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

const FileName = styled.div`
  font-weight: 500;
  color: ${props => props.theme.textPrimary};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const FileSize = styled.div`
  color: ${props => props.theme.textSecondary};
  font-size: 11px;
`;

const FileStatus = styled.div<{ $status: 'uploading' | 'completed' | 'error' | 'pending' }>`
  display: flex;
  align-items: center;
  gap: 4px;
  color: ${props => {
        switch (props.$status) {
            case 'completed': return props.theme.success || '#22c55e';
            case 'error': return props.theme.error || '#ef4444';
            case 'uploading': return props.theme.accent;
            default: return props.theme.textSecondary;
        }
    }};
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 2px;
  background: ${props => props.theme.glassBorder};
  border-radius: 1px;
  overflow: hidden;
  margin-top: 4px;
`;

const ProgressFill = styled.div<{ $progress: number }>`
  width: ${props => props.$progress}%;
  height: 100%;
  background: ${props => props.theme.accent};
  transition: width 0.3s ease;
`;

const RemoveButton = styled.button`
  width: 16px;
  height: 16px;
  border: none;
  background: transparent;
  color: ${props => props.theme.textSecondary};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  
  &:hover {
    background: ${props => props.theme.glassHover};
    color: ${props => props.theme.error || '#ef4444'};
  }
`;

const HiddenFileInput = styled.input`
  display: none;
`;

const FileTypeHint = styled.div`
  font-size: 10px;
  color: ${props => props.theme.textSecondary};
  opacity: 0.8;
  margin-top: 4px;
`;

const ErrorMessage = styled.div`
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
`;

interface FileUploadProps {
    onFilesSelected: (files: File[]) => void;
    disabled?: boolean;
    maxFiles?: number;
}

export const FileUpload: React.FC<FileUploadProps> = ({
    onFilesSelected,
    disabled = false,
    maxFiles = 5
}) => {
    const { fileUploads, getSupportedFileTypes, validateFile, getMaxFileSize } = useChat();
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [isDragOver, setIsDragOver] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const supportedTypes = getSupportedFileTypes();
    const maxFileSize = getMaxFileSize();

    const handleFileSelect = (files: FileList | null) => {
        if (!files || disabled) return;

        const fileArray = Array.from(files);
        const newFiles: File[] = [];
        let errorMessages: string[] = [];

        // Check total file count
        if (selectedFiles.length + fileArray.length > maxFiles) {
            errorMessages.push(`Maximum ${maxFiles} files allowed`);
        }

        for (const file of fileArray) {
            // Validate each file
            const validation = validateFile(file);
            if (validation.valid) {
                newFiles.push(file);
            } else {
                errorMessages.push(validation.error || `Invalid file: ${file.name}`);
            }
        }

        if (errorMessages.length > 0) {
            setError(errorMessages[0]); // Show first error
            setTimeout(() => setError(null), 5000);
        }

        if (newFiles.length > 0) {
            const updatedFiles = [...selectedFiles, ...newFiles].slice(0, maxFiles);
            setSelectedFiles(updatedFiles);
            onFilesSelected(updatedFiles);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        handleFileSelect(e.dataTransfer.files);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    };

    const handleDragLeave = () => {
        setIsDragOver(false);
    };

    const handleClick = () => {
        if (!disabled) {
            fileInputRef.current?.click();
        }
    };

    const removeFile = (index: number) => {
        const updatedFiles = selectedFiles.filter((_, i) => i !== index);
        setSelectedFiles(updatedFiles);
        onFilesSelected(updatedFiles);
    };

    const clearFiles = () => {
        setSelectedFiles([]);
        onFilesSelected([]);
        setError(null);
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const getFileStatus = (file: File): 'uploading' | 'completed' | 'error' | 'pending' => {
        const upload = fileUploads.find(u => u.file.name === file.name && u.file.size === file.size);
        return upload?.status || 'pending';
    };

    const getFileProgress = (file: File): number => {
        const upload = fileUploads.find(u => u.file.name === file.name && u.file.size === file.size);
        return upload?.progress || 0;
    };

    const getFileError = (file: File): string | undefined => {
        const upload = fileUploads.find(u => u.file.name === file.name && u.file.size === file.size);
        return upload?.error;
    };

    const renderStatusIcon = (status: 'uploading' | 'completed' | 'error' | 'pending') => {
        switch (status) {
            case 'uploading':
                return <Loader size={12} className="animate-spin" />;
            case 'completed':
                return <CheckCircle size={12} />;
            case 'error':
                return <AlertCircle size={12} />;
            default:
                return <File size={12} />;
        }
    };

    return (
        <FileUploadContainer>
            {error && (
                <ErrorMessage>
                    <AlertCircle size={14} />
                    {error}
                </ErrorMessage>
            )}

            <DropZone
                $isDragOver={isDragOver}
                $hasFiles={selectedFiles.length > 0}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={handleClick}
            >
                <DropZoneContent $hasFiles={selectedFiles.length > 0}>
                    <UploadIcon $hasFiles={selectedFiles.length > 0}>
                        <Upload size={selectedFiles.length > 0 ? 16 : 24} />
                    </UploadIcon>
                    <div>
                        {selectedFiles.length > 0
                            ? `${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''} selected`
                            : isDragOver
                                ? 'Drop files here'
                                : 'Click to upload or drag files here'
                        }
                    </div>
                    {selectedFiles.length === 0 && (
                        <FileTypeHint>
                            Max {Math.round(maxFileSize / (1024 * 1024))}MB •
                            {supportedTypes.slice(0, 5).join(', ')}
                            {supportedTypes.length > 5 && ` +${supportedTypes.length - 5} more`}
                        </FileTypeHint>
                    )}
                </DropZoneContent>
            </DropZone>

            {selectedFiles.length > 0 && (
                <FileList>
                    {selectedFiles.map((file, index) => {
                        const status = getFileStatus(file);
                        const progress = getFileProgress(file);
                        const fileError = getFileError(file);

                        return (
                            <FileItem key={`${file.name}-${index}`} $status={status}>
                                <FileStatus $status={status}>
                                    {renderStatusIcon(status)}
                                </FileStatus>

                                <FileInfo>
                                    <FileName>{file.name}</FileName>
                                    <FileSize>{formatFileSize(file.size)}</FileSize>

                                    {status === 'uploading' && (
                                        <ProgressBar>
                                            <ProgressFill $progress={progress} />
                                        </ProgressBar>
                                    )}

                                    {status === 'error' && fileError && (
                                        <div style={{ color: '#ef4444', fontSize: '10px', marginTop: '2px' }}>
                                            {fileError}
                                        </div>
                                    )}
                                </FileInfo>

                                <RemoveButton
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeFile(index);
                                    }}
                                    title="Remove file"
                                >
                                    <X size={12} />
                                </RemoveButton>
                            </FileItem>
                        );
                    })}
                </FileList>
            )}

            <HiddenFileInput
                ref={fileInputRef}
                type="file"
                multiple
                accept={supportedTypes.join(',')}
                onChange={(e) => handleFileSelect(e.target.files)}
                disabled={disabled}
            />
        </FileUploadContainer>
    );
};