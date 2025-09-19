// src/components/sidebar/SidebarButton.tsx
import React from 'react';
import styled, { keyframes } from 'styled-components';

interface SidebarButtonProps {
    children: React.ReactNode;
    onClick?: () => void;
    isActive?: boolean;
    variant?: 'primary' | 'secondary' | 'ghost';
}

const shimmer = keyframes`
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
`;

const glow = keyframes`
  0%, 100% { box-shadow: 0 0 5px ${props => props.theme.accent}40; }
  50% { box-shadow: 0 0 20px ${props => props.theme.accent}60, 0 0 30px ${props => props.theme.accent}30; }
`;

const Button = styled.button<{
    $isActive?: boolean;
    $variant?: 'primary' | 'secondary' | 'ghost'
}>`
  width: 100%;
  padding: 14px 18px;
  background: ${props => {
        if (props.$isActive && props.$variant === 'primary') {
            return `linear-gradient(135deg, ${props.theme.accent}, ${props.theme.accentHover})`;
        }
        if (props.$isActive) {
            return props.theme.glassActive;
        }
        if (props.$variant === 'primary') {
            return `linear-gradient(135deg, ${props.theme.accent}, ${props.theme.accentHover})`;
        }
        return props.theme.glassBackground;
    }};
  backdrop-filter: blur(12px) saturate(180%);
  color: ${props => {
        if (props.$isActive && props.$variant === 'primary') return 'white';
        if (props.$variant === 'primary') return 'white';
        return props.theme.textPrimary;
    }};
  border: 1px solid ${props => {
        if (props.$isActive || props.$variant === 'primary') return props.theme.accent;
        return props.theme.glassBorder;
    }};
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  position: relative;
  overflow: hidden;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  /* Shimmer effect overlay */
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, 
      transparent, 
      rgba(255, 255, 255, 0.2), 
      transparent
    );
    transition: left 0.6s ease;
  }
  
  /* Glow effect for primary/active buttons */
  ${props => (props.$isActive || props.$variant === 'primary') && `
    animation: ${glow} 2s ease-in-out infinite;
  `}
  
  &:hover {
    transform: translateY(-2px) scale(1.02);
    background: ${props => {
        if (props.$variant === 'primary') return `linear-gradient(135deg, ${props.theme.accentHover}, ${props.theme.accentDark})`;
        return props.theme.glassHover;
    }};
    border-color: ${props => props.theme.accent};
    box-shadow: 0 8px 25px ${props => props.theme.accent}40;
    
    &::before {
      left: 100%;
    }
  }
  
  &:active {
    transform: translateY(-1px) scale(1);
  }
`;

const IconWrapper = styled.span<{ $variant?: string }>`
  display: flex;
  align-items: center;
  font-size: 16px;
  filter: ${props => props.$variant === 'primary' ? 'drop-shadow(0 0 4px rgba(255,255,255,0.5))' : 'none'};
`;

export const SidebarButton: React.FC<SidebarButtonProps> = ({
    children,
    onClick,
    isActive,
    variant = 'secondary'
}) => {
    return (
        <Button
            onClick={onClick}
            $isActive={isActive}
            $variant={variant}
        >
            <IconWrapper $variant={variant}>
                {children}
            </IconWrapper>
        </Button>
    );
};