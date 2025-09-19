import styled from 'styled-components';

// Main app container
export const AppContainer = styled.div`
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  position: relative;
`;

// Layout containers for different modes
export const MainContent = styled.div<{ $layoutMode: 'centered' | 'split' }>`
  flex: 1;
  display: flex;
  height: 100vh;
  overflow: hidden;
  transition: all 0.3s ease;
`;

export const ChatSection = styled.div<{ $layoutMode: 'centered' | 'split' }>`
  width: ${props => props.$layoutMode === 'split' ? '50%' : '100%'};
  display: flex;
  flex-direction: column;
  height: 100vh;
  transition: width 0.3s ease;
  border-right: ${props => props.$layoutMode === 'split' ? `1px solid ${props.theme.borderColor}` : 'none'};
`;

export const ArtifactSection = styled.div<{ $isVisible: boolean }>`
  width: ${props => props.$isVisible ? '50%' : '0%'};
  height: 100vh;
  overflow: hidden;
  transition: width 0.3s ease;
  background-color: ${props => props.theme.surfaceBackground};
  border-left: ${props => props.$isVisible ? `1px solid ${props.theme.borderColor}` : 'none'};
`;

// Responsive breakpoints
export const MobileBreakpoint = '768px';
export const TabletBreakpoint = '1024px';
export const DesktopBreakpoint = '1200px';

// Loading and error states
export const LoadingContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  flex-direction: column;
  gap: 16px;
  color: ${props => props.theme.textSecondary};
`;

export const LoadingSpinner = styled.div`
  width: 32px;
  height: 32px;
  border: 3px solid ${props => props.theme.borderColor};
  border-top: 3px solid ${props => props.theme.buttonPrimary};
  border-radius: 50%;
  animation: spin 1s linear infinite;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

export const ErrorContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  flex-direction: column;
  gap: 16px;
  color: ${props => props.theme.textSecondary};
  padding: 24px;
  text-align: center;
`;

export const ErrorMessage = styled.div`
  font-size: 16px;
  color: ${props => props.theme.textPrimary};
  max-width: 400px;
`;

export const RetryButton = styled.button`
  padding: 12px 24px;
  background-color: ${props => props.theme.buttonPrimary};
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: ${props => props.theme.buttonHover};
  }
`;