// src/components/chat/ArtifactPanel.tsx
import React, { useMemo, useState, useCallback } from 'react';
import styled from 'styled-components';
import {
  X, Download, Maximize2, Minimize2, Code2, FileText,
  BarChart, Check, Eye, Code, Copy, Image as ImageIcon, ExternalLink
} from 'lucide-react';
import type { Artifact } from '../../types/chat';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';

import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Papa from 'papaparse';

// Map common aliases Prism expects
const LANGUAGE_ALIASES: Record<string, string> = {
  ts: 'tsx',
  js: 'jsx',
  md: 'markdown',
  shell: 'bash',
  sh: 'bash',
  py: 'python',
  yml: 'yaml',
};

// Create a custom sanitize schema that allows tables and other GFM elements
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    td: ['align', 'colSpan', 'rowSpan'],
    th: ['align', 'colSpan', 'rowSpan', 'scope'],
    table: ['className'],
  },
  tagNames: [
    ...(defaultSchema.tagNames || []),
    'table',
    'thead',
    'tbody',
    'tfoot',
    'tr',
    'th',
    'td',
  ],
};

interface ArtifactPanelProps {
  artifact?: Artifact;
  isExpanded: boolean;
  onClose: () => void;
  onToggleExpand: () => void;
}

const PanelContainer = styled.div<{ $isExpanded: boolean }>`
  width: ${p => (p.$isExpanded ? '100%' : '50%')};
  height: 100vh;
  background: ${p => p.theme.glassBackground};
  backdrop-filter: blur(16px) saturate(120%);
  border-left: 1px solid ${p => p.theme.glassBorder};
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg,
      rgba(255,255,255,0.1) 0%,
      transparent 30%,
      transparent 70%,
      rgba(255,255,255,0.05) 100%);
    pointer-events: none;
  }
`;

const PanelHeader = styled.div`
  padding: 16px 20px;
  border-bottom: 1px solid ${p => p.theme.glassBorder};
  background: ${p => p.theme.glassBackground};
  backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: space-between;
  position: relative; z-index: 1;

  &::after {
    content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 1px;
    background: linear-gradient(90deg, transparent 0%, ${p => p.theme.accent}40 50%, transparent 100%);
  }
`;

const HeaderInfo = styled.div`
  display: flex; align-items: center; gap: 12px;
`;

const IconContainer = styled.div`
  width: 36px; height: 36px; border-radius: 8px;
  background: linear-gradient(135deg, ${p => p.theme.accent}, ${p => p.theme.accentHover});
  display: flex; align-items: center; justify-content: center; color: white;
`;

const HeaderText = styled.div`
  h3 {
    font-size: 16px; font-weight: 600; color: ${p => p.theme.textPrimary};
    margin: 0 0 2px 0;
  }
  p { font-size: 12px; color: ${p => p.theme.textSecondary}; margin: 0; }
`;

const HeaderActions = styled.div`
  display: flex; align-items: center; gap: 8px;
`;

const ActionButton = styled.button<{ $variant?: 'danger'; $active?: boolean }>`
  width: 32px; height: 32px; border-radius: 6px;
  background: ${p =>
    p.$variant === 'danger' ? 'rgba(239,68,68,0.1)' :
      p.$active ? p.theme.accent :
        p.theme.glassBackground};
  border: 1px solid ${p =>
    p.$variant === 'danger' ? 'rgba(239,68,68,0.3)' :
      p.$active ? p.theme.accent :
        p.theme.glassBorder};
  color: ${p =>
    p.$variant === 'danger' ? '#ef4444' :
      p.$active ? 'white' :
        p.theme.textPrimary};
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .2s ease;
  &:hover {
    background: ${p =>
    p.$variant === 'danger' ? 'rgba(239,68,68,0.2)' :
      p.$active ? p.theme.accentHover :
        p.theme.glassHover};
    border-color: ${p => p.$variant === 'danger' ? 'rgba(239,68,68,0.5)' : p.theme.accent};
    transform: translateY(-1px);
  }
`;

const ContentArea = styled.div`
  flex: 1; overflow: hidden; display: flex; flex-direction: column; position: relative; z-index: 1;
`;

const ViewToggle = styled.div`
  display: flex;
  background: ${p => p.theme.glassBackground};
  border-bottom: 1px solid ${p => p.theme.glassBorder};
  padding: 8px 12px; gap: 4px;
`;

const ViewButton = styled.button<{ $active: boolean }>`
  padding: 6px 12px; border-radius: 6px;
  border: 1px solid ${p => (p.$active ? p.theme.accent : p.theme.glassBorder)};
  background: ${p => (p.$active ? p.theme.accent : 'transparent')};
  color: ${p => (p.$active ? 'white' : p.theme.textSecondary)};
  font-size: 11px; font-weight: 500; cursor: pointer; transition: all .2s ease;
  display: flex; align-items: center; gap: 4px;
  &:hover { background: ${p => (p.$active ? p.theme.accentHover : p.theme.glassHover)}; }
`;

const CodeContainer = styled.div`
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
`;

const CodeHeader = styled.div`
  padding: 12px 20px; background: ${p => p.theme.glassHover};
  border-bottom: 1px solid ${p => p.theme.glassBorder};
  display: flex; align-items: center; justify-content: space-between;
  font-size: 12px; color: ${p => p.theme.textSecondary};
`;

const LanguageBadge = styled.span`
  padding: 4px 8px;
  background: ${p => p.theme.accent}20;
  border: 1px solid ${p => p.theme.accent}40;
  border-radius: 4px; font-size: 11px; font-weight: 600;
  color: ${p => p.theme.accent}; text-transform: uppercase;
`;

const CopyButton = styled.button<{ $copied: boolean }>`
  padding: 6px 12px;
  background: ${p => (p.$copied ? '#10b981' : p.theme.glassBackground)};
  border: 1px solid ${p => (p.$copied ? '#10b981' : p.theme.glassBorder)};
  border-radius: 6px; color: ${p => (p.$copied ? 'white' : p.theme.textPrimary)};
  font-size: 11px; font-weight: 500; cursor: pointer;
  display: flex; align-items: center; gap: 4px; transition: all .2s ease;
  &:hover {
    background: ${p => (p.$copied ? '#059669' : p.theme.glassHover)};
    border-color: ${p => (p.$copied ? '#059669' : p.theme.accent)};
  }
`;

const CodeBlockOuter = styled.div`
  flex: 1; overflow: auto;
  .code-line {
    display: block;
    white-space: pre-wrap;
    word-break: break-word;
  }
  pre {
    margin: 0 !important;
    padding: 20px !important;
    background: ${p => p.theme.background} !important;
    font-family: 'SF Mono','Monaco','Cascadia Code','Roboto Mono',monospace !important;
    font-size: 13px !important;
    line-height: 1.6 !important;
  }
`;

const ImagePreviewContainer = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px;
  overflow: auto;
`;

const PreviewImage = styled.img`
  max-width: 100%;
  max-height: 80vh;
  border-radius: 12px;
  border: 1px solid ${p => p.theme.glassBorder};
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
`;

const PreviewNotice = styled.div`
  font-size: 12px;
  color: ${p => p.theme.textSecondary};
  background: ${p => p.theme.glassBackground};
  border: 1px solid ${p => p.theme.glassBorder};
  border-radius: 8px;
  padding: 8px 12px;
  text-align: center;
  a {
    color: ${p => p.theme.accent};
    font-weight: 600;
  }
`;

const MarkdownContent = styled.div`
  flex: 1; padding: 20px; overflow: auto;
  font-size: 14px; line-height: 1.7; color: ${p => p.theme.textPrimary};

  h1,h2,h3,h4,h5,h6 { margin: 24px 0 12px; font-weight: 600; line-height: 1.3; }
  h1 { font-size: 24px; border-bottom: 2px solid ${p => p.theme.glassBorder}; padding-bottom: 8px; }
  h2 { font-size: 20px; border-bottom: 1px solid ${p => p.theme.glassBorder}; padding-bottom: 6px; }
  h3 { font-size: 18px; } h4 { font-size: 16px; } h5,h6 { font-size: 14px; }

  p { margin: 0 0 16px; }
  ul,ol { margin: 16px 0; padding-left: 24px; }
  li { margin: 4px 0; line-height: 1.5; }
  blockquote {
    border-left: 4px solid ${p => p.theme.accent};
    margin: 16px 0; padding: 8px 0 8px 20px;
    background: ${p => p.theme.glassBackground};
    border-radius: 0 8px 8px 0; color: ${p => p.theme.textSecondary}; font-style: italic;
  }
  
  /* Enhanced table styles */
  table { 
    border-collapse: collapse; 
    width: 100%; 
    margin: 16px 0; 
    font-size: 13px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    overflow: hidden;
  }
  thead {
    background: ${p => p.theme.glassBackground};
  }
  th {
    border: 1px solid ${p => p.theme.glassBorder}; 
    padding: 12px 16px; 
    text-align: left;
    font-weight: 600;
    background: ${p => p.theme.glassHover};
    color: ${p => p.theme.textPrimary};
  }
  td {
    border: 1px solid ${p => p.theme.glassBorder}; 
    padding: 10px 16px; 
    text-align: left;
  }
  tbody tr {
    transition: background-color 0.15s ease;
  }
  tbody tr:hover {
    background: ${p => p.theme.glassBackground};
  }
  tbody tr:nth-child(even) {
    background: rgba(0, 0, 0, 0.02);
  }
  
  hr { border: none; border-top: 1px solid ${p => p.theme.glassBorder}; margin: 24px 0; }

  code {
    background: ${p => p.theme.glassBackground};
    border: 1px solid ${p => p.theme.glassBorder};
    border-radius: 4px; padding: 2px 6px;
    font-family: 'SF Mono','Monaco','Cascadia Code','Roboto Mono',monospace;
    font-size: 12px; color: ${p => p.theme.accent};
  }
  pre > code { background: transparent; border: 0; padding: 0; color: inherit; }
  a { color: ${p => p.theme.accent}; text-decoration: underline; }
  a:hover { text-decoration: none; opacity: .85; }
`;

const CsvTableContainer = styled.div`
  flex: 1; 
  overflow: auto;
  padding: 20px;
`;

const CsvTable = styled.table`
  border-collapse: collapse; 
  width: 100%; 
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  overflow: hidden;
  
  thead {
    position: sticky;
    top: 0;
    z-index: 10;
    background: ${p => p.theme.glassHover};
  }
  
  th {
    border: 1px solid ${p => p.theme.glassBorder}; 
    padding: 12px 16px; 
    text-align: left;
    font-weight: 600;
    background: ${p => p.theme.glassHover};
    color: ${p => p.theme.textPrimary};
    white-space: nowrap;
  }
  
  td {
    border: 1px solid ${p => p.theme.glassBorder}; 
    padding: 10px 16px; 
    text-align: left;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  tbody tr {
    transition: background-color 0.15s ease;
  }
  
  tbody tr:hover {
    background: ${p => p.theme.glassBackground};
  }
  
  tbody tr:nth-child(even) {
    background: rgba(0, 0, 0, 0.02);
  }
`;

const CsvInfo = styled.div`
  padding: 12px 20px;
  background: ${p => p.theme.glassBackground};
  border-bottom: 1px solid ${p => p.theme.glassBorder};
  font-size: 12px;
  color: ${p => p.theme.textSecondary};
  display: flex;
  gap: 16px;
  align-items: center;
  
  strong {
    color: ${p => p.theme.textPrimary};
    font-weight: 600;
  }
`;

const EmptyState = styled.div`
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; color: ${p => p.theme.textSecondary}; gap: 16px;
  div { font-size: 48px; opacity: 0.5; }
  h3 { font-size: 18px; margin: 0; color: ${p => p.theme.textPrimary}; }
  p { margin: 0; font-size: 14px; }
`;

const getArtifactIcon = (type: string) => {
  switch (type) {
    case 'code': return <Code2 size={18} />;
    case 'document': return <FileText size={18} />;
    case 'chart': return <BarChart size={18} />;
    case 'image': return <ImageIcon size={18} />;
    default: return <Code2 size={18} />;
  }
};

const getArtifactTypeLabel = (type: string) => {
  switch (type) {
    case 'code': return 'Code Artifact';
    case 'document': return 'Document';
    case 'chart': return 'Chart';
    case 'image': return 'Image';
    default: return 'Artifact';
  }
};

const normalizeLang = (lang?: string) => {
  if (!lang) return undefined;
  const lower = lang.toLowerCase();
  return LANGUAGE_ALIASES[lower] ?? lower;
};

const inferExtension = (language?: string, fallback = 'txt') => {
  const lang = normalizeLang(language);
  if (!lang) return fallback;
  const map: Record<string, string> = {
    typescript: 'ts', tsx: 'tsx', ts: 'ts',
    javascript: 'js', jsx: 'jsx', js: 'js',
    json: 'json', yaml: 'yml', yml: 'yml',
    markdown: 'md', md: 'md',
    python: 'py', ruby: 'rb', go: 'go', rust: 'rs',
    java: 'java', c: 'c', cpp: 'cpp',
    bash: 'sh', zsh: 'sh', sh: 'sh',
    html: 'html', css: 'css', scss: 'scss',
  };
  return map[lang] ?? fallback;
};

const formatBytes = (bytes?: number): string | undefined => {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes <= 0) {
    return undefined;
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const precision = value < 10 && unitIndex > 0 ? 1 : 0;
  return `${value.toFixed(precision)} ${units[unitIndex]}`;
};

export const ArtifactPanel: React.FC<ArtifactPanelProps> = ({
  artifact, isExpanded, onClose, onToggleExpand,
}) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'rendered' | 'raw'>('rendered');

  const isMarkdown = useMemo(() => {
    if (!artifact?.content) return false;
    const lang = artifact.language?.toLowerCase();
    return artifact.type === 'document' ||
      lang === 'markdown' || lang === 'md';
  }, [artifact]);

  const isCsv = useMemo(() => {
    if (!artifact?.content) return false;
    const lang = artifact.language?.toLowerCase();
    const ext = artifact.filename?.toLowerCase().split('.').pop();
    return lang === 'csv' || ext === 'csv';
  }, [artifact]);

  const parsedCsvData = useMemo(() => {
    if (!isCsv || !artifact?.content) return null;
    try {
      const result = Papa.parse(artifact.content, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
        delimitersToGuess: [',', '\t', '|', ';']
      });
      return result.data.length > 0 ? result : null;
    } catch (e) {
      console.error('CSV parse error:', e);
      return null;
    }
  }, [isCsv, artifact]);

  const handleCopy = useCallback(async (text?: string) => {
    const value = text ?? artifact?.content ?? '';
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  }, [artifact]);

  const handleDownload = () => {
    if (artifact?.downloadUrl) {
      window.open(artifact.downloadUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    if (!artifact?.content) return;

    const blob = new Blob([artifact.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;

    const fallbackExt = artifact.type === 'image' ? 'png' : 'txt';
    const downloadName = artifact.filename ||
      `${artifact.title.toLowerCase().replace(/\s+/g, '-')}.${inferExtension(artifact.language, fallbackExt)}`;

    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const codeLanguage = useMemo(() => normalizeLang(artifact?.language), [artifact]);
  const headerSubtitle = useMemo(() => {
    if (!artifact) return 'Artifact';
    const parts: string[] = [getArtifactTypeLabel(artifact.type)];
    const sizeLabel = formatBytes(artifact.size);
    if (sizeLabel) parts.push(sizeLabel);
    if (artifact.truncated) parts.push('Preview truncated');
    if (artifact.isLarge) parts.push('Large file');
    return parts.join(' • ');
  }, [artifact]);

  if (!artifact) {
    return (
      <PanelContainer $isExpanded={isExpanded}>
        <PanelHeader>
          <HeaderInfo>
            <IconContainer><FileText size={18} /></IconContainer>
            <HeaderText>
              <h3>No Artifact</h3>
              <p>Select a message with an artifact to view</p>
            </HeaderText>
          </HeaderInfo>
          <HeaderActions>
            <ActionButton onClick={onClose} $variant="danger"><X size={16} /></ActionButton>
          </HeaderActions>
        </PanelHeader>
        <ContentArea>
          <EmptyState>
            <div>📄</div>
            <h3>No Artifact Selected</h3>
            <p>Click on an artifact in a message to view it here</p>
          </EmptyState>
        </ContentArea>
      </PanelContainer>
    );
  }

  return (
    <PanelContainer $isExpanded={isExpanded}>
      <PanelHeader>
        <HeaderInfo>
          <IconContainer>
            {getArtifactIcon(artifact.type)}
          </IconContainer>
          <HeaderText>
            <h3>{artifact.filename || artifact.title}</h3>
            <p>{headerSubtitle}</p>
          </HeaderText>
        </HeaderInfo>

        <HeaderActions>
          <ActionButton onClick={handleDownload} title="Download">
            <Download size={14} />
          </ActionButton>
          <ActionButton onClick={onToggleExpand} title={isExpanded ? 'Split View' : 'Full Screen'}>
            {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </ActionButton>
          <ActionButton onClick={onClose} $variant="danger" title="Close">
            <X size={14} />
          </ActionButton>
        </HeaderActions>
      </PanelHeader>

      {artifact.type === 'document' && isMarkdown && (
        <ViewToggle>
          <ViewButton $active={viewMode === 'rendered'} onClick={() => setViewMode('rendered')}>
            <Eye size={12} /> Rendered
          </ViewButton>
          <ViewButton $active={viewMode === 'raw'} onClick={() => setViewMode('raw')}>
            <Code size={12} /> Raw
          </ViewButton>
        </ViewToggle>
      )}

      {isCsv && parsedCsvData && (
        <ViewToggle>
          <ViewButton $active={viewMode === 'rendered'} onClick={() => setViewMode('rendered')}>
            <BarChart size={12} /> Table
          </ViewButton>
          <ViewButton $active={viewMode === 'raw'} onClick={() => setViewMode('raw')}>
            <Code size={12} /> Raw
          </ViewButton>
        </ViewToggle>
      )}

      <ContentArea>
        {artifact.type === 'code' ? (
          <CodeContainer>
            <CodeHeader>
              <LanguageBadge>{codeLanguage ?? 'text'}</LanguageBadge>
              <CopyButton onClick={() => handleCopy()} $copied={copied}>
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? 'Copied!' : 'Copy Code'}
              </CopyButton>
            </CodeHeader>
            <CodeBlockOuter>
              <SyntaxHighlighter
                language={codeLanguage}
                style={oneDark}
                showLineNumbers
                wrapLongLines
                PreTag="pre"
                CodeTag={(props: any) => <code {...props} />}
              >
                {artifact.content}
              </SyntaxHighlighter>
            </CodeBlockOuter>
          </CodeContainer>
        ) : artifact.type === 'image' ? (
          <ImagePreviewContainer>
            {artifact.downloadUrl ? (
              <PreviewImage
                src={artifact.downloadUrl}
                alt={artifact.filename || artifact.title}
              />
            ) : (
              <PreviewNotice>No image preview available.</PreviewNotice>
            )}
            {artifact.content && artifact.content !== artifact.downloadUrl && (
              <PreviewNotice>
                <ReactMarkdown rehypePlugins={[[rehypeSanitize, sanitizeSchema]]} remarkPlugins={[remarkGfm]}>
                  {artifact.content}
                </ReactMarkdown>
              </PreviewNotice>
            )}
            {artifact.downloadUrl && (
              <PreviewNotice>
                <a href={artifact.downloadUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink size={12} /> Open original
                </a>
              </PreviewNotice>
            )}
          </ImagePreviewContainer>
        ) : isCsv && parsedCsvData && viewMode === 'rendered' ? (
          <>
            <CsvInfo>
              <span><strong>{parsedCsvData.data.length}</strong> rows</span>
              <span><strong>{parsedCsvData.meta.fields?.length || 0}</strong> columns</span>
            </CsvInfo>
            <CsvTableContainer>
              <CsvTable>
                <thead>
                  <tr>
                    {parsedCsvData.meta.fields?.map((field: string, idx: number) => (
                      <th key={idx}>{field}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parsedCsvData.data.map((row: any, rowIdx: number) => (
                    <tr key={rowIdx}>
                      {parsedCsvData.meta.fields?.map((field: string, colIdx: number) => (
                        <td key={colIdx} title={String(row[field] ?? '')}>
                          {row[field] !== null && row[field] !== undefined ? String(row[field]) : ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </CsvTable>
            </CsvTableContainer>
          </>
        ) : (
          <>
            {(artifact.truncated || artifact.isLarge) && artifact.downloadUrl && (
              <PreviewNotice>
                {artifact.truncated ? 'Preview truncated.' : 'Preview limited due to file size.'}{' '}
                <a href={artifact.downloadUrl} target="_blank" rel="noopener noreferrer">
                  Download full file
                </a>
              </PreviewNotice>
            )}
            {isMarkdown && viewMode === 'rendered' ? (
              <MarkdownContent>
                <ReactMarkdown
                  rehypePlugins={[
                    rehypeSlug,
                    [rehypeAutolinkHeadings, { behavior: 'wrap' }],
                    [rehypeSanitize, sanitizeSchema]
                  ]}
                  remarkPlugins={[remarkGfm]}
                >
                  {artifact.content}
                </ReactMarkdown>
              </MarkdownContent>
            ) : (
              <CodeContainer>
                <CodeHeader>
                  <LanguageBadge>{normalizeLang(artifact.language) ?? 'text'}</LanguageBadge>
                  <CopyButton onClick={() => handleCopy()} $copied={copied}>
                    {copied ? <Check size={12} /> : <Copy size={12} />}
                    {copied ? 'Copied!' : 'Copy'}
                  </CopyButton>
                </CodeHeader>
                <CodeBlockOuter>
                  <SyntaxHighlighter
                    language={normalizeLang(artifact.language)}
                    style={oneDark}
                    showLineNumbers
                    wrapLongLines
                    PreTag="pre"
                    CodeTag={(props: any) => <code {...props} />}
                  >
                    {artifact.content}
                  </SyntaxHighlighter>
                </CodeBlockOuter>
              </CodeContainer>
            )}
          </>
        )}
      </ContentArea>
    </PanelContainer>
  );
};