// src/components/sidebar/Sidebar.tsx
import React, { useMemo, useState } from 'react';
import styled, { keyframes } from 'styled-components';
import {
    Home,
    Plus,
    Sun,
    Moon,
    PanelLeftClose,
    PanelLeftOpen,
    Clock,
    Archive
} from 'lucide-react';
import { useChat } from '../../contexts/ChatContext';
import { useTheme } from '../../contexts/ThemeContext';
import { ChatItem } from './ChatItem';

// Subtle entrance
const slideInStagger = keyframes`
  from { transform: translateY(6px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
`;

const SidebarContainer = styled.div<{ $isCollapsed: boolean }>`
  width: ${p => (p.$isCollapsed ? '56px' : '300px')};
  height: 100vh;
  background: ${p => p.theme.glassBackground};
  backdrop-filter: blur(16px) saturate(150%);
  border-right: 1px solid ${p => p.theme.glassBorder};
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  transition: width 280ms cubic-bezier(0.23, 1, 0.32, 1);
`;

const Header = styled.div<{ $isCollapsed: boolean }>`
  padding: ${p => (p.$isCollapsed ? '8px' : '12px 12px')};
  border-bottom: 1px solid ${p => p.theme.glassBorder};
  display: flex;
  align-items: center;
  justify-content: ${p => (p.$isCollapsed ? 'center' : 'space-between')};
  gap: 8px;
`;

const Brand = styled.div<{ $isCollapsed: boolean }>`
  display: ${p => (p.$isCollapsed ? 'none' : 'flex')};
  align-items: center;
  gap: 8px;

  h1 {
    margin: 0;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 0.4px;
    color: ${p => p.theme.textPrimary};
  }
`;

const IconButton = styled.button`
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: ${p => p.theme.glassBackground};
  border: 1px solid ${p => p.theme.glassBorder};
  color: ${p => p.theme.textPrimary};
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: 160ms ease;

  &:hover {
    border-color: ${p => p.theme.accent};
  }
`;

const NavigationSection = styled.div<{ $isCollapsed: boolean }>`
  padding: ${p => (p.$isCollapsed ? '0' : '8px 10px')};
  margin-bottom: 6px;
`;

const NavGrid = styled.div<{ $isCollapsed: boolean }>`
  display: ${p => (p.$isCollapsed ? 'flex' : 'grid')};
  ${p =>
        p.$isCollapsed
            ? 'flex-direction: column; align-items: center; gap: 8px; padding: 8px;'
            : 'grid-template-columns: 1fr 1fr; gap: 8px;'}
`;

const NavButton = styled.button<{
    $isActive?: boolean;
    $isPrimary?: boolean;
    $isCollapsed?: boolean;
}>`
  ${p => (p.$isCollapsed ? 'height: 40px; width: 40px;' : 'padding: 10px;')}
  background: ${p => p.theme.glassBackground};
  border: 1px solid
    ${p => (p.$isActive || p.$isPrimary ? p.theme.accent : p.theme.glassBorder)};
  border-radius: 8px;
  color: ${p => p.theme.textPrimary};
  display: flex;
  align-items: center;
  justify-content: ${p => (p.$isCollapsed ? 'center' : 'flex-start')};
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  cursor: pointer;
  transition: 160ms ease;
  outline: none;

  &:hover {
    border-color: ${p => p.theme.accent};
  }
`;

const ContentArea = styled.div<{ $isCollapsed: boolean }>`
  flex: 1;
  padding: ${p => (p.$isCollapsed ? '8px 6px' : '10px')};
  overflow-y: auto;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: ${p => p.theme.glassBorder};
    border-radius: 3px;
  }
`;

const SectionHeader = styled.div<{ $isCollapsed: boolean }>`
  display: ${p => (p.$isCollapsed ? 'none' : 'flex')};
  align-items: center;
  gap: 6px;
  margin: 6px 2px 10px;

  h3 {
    margin: 0;
    font-size: 11px;
    font-weight: 800;
    color: ${p => p.theme.textSecondary};
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
`;

const ChatsList = styled.div<{ $isCollapsed: boolean }>`
  display: flex;
  flex-direction: column;
  gap: ${p => (p.$isCollapsed ? '8px' : '6px')};
  animation: ${slideInStagger} 0.35s ease-out;
`;

const Footer = styled.div<{ $isCollapsed: boolean }>`
  padding: ${p => (p.$isCollapsed ? '8px' : '10px')};
  border-top: 1px solid ${p => p.theme.glassBorder};
  display: flex;
  justify-content: ${p => (p.$isCollapsed ? 'center' : 'stretch')};
`;

const ChatItemContainer = styled.div<{ $index: number }>`
  animation: ${slideInStagger} 0.3s ease-out both;
  animation-delay: ${p => `${p.$index * 0.06}s`};
`;

const ThemeButton = styled(NavButton)`
    height: 40px;
  width: 40px;
  justify-content: center;
`;

export const Sidebar: React.FC = () => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const { chats, activeChat, setActiveChat, addNewChat, currentView, setCurrentView } = useChat();
    const { isDark, toggleTheme } = useTheme();

    const displayChats = currentView === 'home' ? chats.slice(0, 6) : chats;

    // Define top-level nav items
    const navItems = useMemo(
        () => [
            {
                key: 'home' as const,
                label: 'Home',
                icon: <Home size={18} />,
                active: currentView === 'home',
                onClick: () => setCurrentView('home'),
            },
            {
                key: 'all-chats' as const,
                label: 'Archive',
                icon: <Archive size={18} />,
                active: currentView === 'all-chats',
                onClick: () => setCurrentView('all-chats'),
            },
        ],
        [currentView, setCurrentView]
    );

    // When collapsed: only show the *active* nav item (no logo, no extra buttons except theme at bottom)
    const collapsedNav = navItems.filter(n => n.active);

    return (
        <SidebarContainer $isCollapsed={isCollapsed}>
            <Header $isCollapsed={isCollapsed}>
                <Brand $isCollapsed={isCollapsed}>
                    <h1>ArrowAI</h1>
                </Brand>

                <IconButton onClick={() => setIsCollapsed(v => !v)} aria-label="Toggle sidebar">
                    {isCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
                </IconButton>
            </Header>

            <NavigationSection $isCollapsed={isCollapsed}>
                <NavGrid $isCollapsed={isCollapsed}>
                    {(isCollapsed ? collapsedNav : navItems).map(item => (
                        <NavButton
                            key={item.key}
                            $isActive={item.active}
                            $isCollapsed={isCollapsed}
                            onClick={item.onClick}
                            title={item.label}
                        >
                            {item.icon}
                            {!isCollapsed && item.label}
                        </NavButton>
                    ))}

                    {!isCollapsed && (
                        <NavButton
                            $isPrimary
                            onClick={addNewChat}
                            title="New Chat"
                            style={{ gridColumn: '1 / -1' }}
                        >
                            <Plus size={18} />
                            New Chat
                        </NavButton>
                    )}
                </NavGrid>
            </NavigationSection>

            <ContentArea $isCollapsed={isCollapsed}>
                {!isCollapsed && (
                    <>
                        <SectionHeader $isCollapsed={isCollapsed}>
                            <Clock size={14} />
                            <h3>{currentView === 'home' ? 'Recent' : 'All Chats'}</h3>
                        </SectionHeader>

                        <ChatsList $isCollapsed={isCollapsed}>
                            {displayChats.map((chat, index) => (
                                <ChatItemContainer key={chat.id} $index={index}>
                                    <ChatItem
                                        chat={chat}
                                        isActive={activeChat === chat.id}
                                        onClick={() => setActiveChat(chat.id)}
                                    />
                                </ChatItemContainer>
                            ))}

                            {displayChats.length === 0 && (
                                <div
                                    style={{
                                        textAlign: 'center',
                                        color: '#64748b',
                                        fontSize: 12,
                                        padding: '18px 12px',
                                        opacity: 0.75,
                                    }}
                                >
                                    No conversations yet.
                                    <br />
                                    Start chatting to see them here!
                                </div>
                            )}
                        </ChatsList>
                    </>
                )}
            </ContentArea>

            <Footer $isCollapsed={isCollapsed}>
                <ThemeButton
                    $isCollapsed={isCollapsed}
                    onClick={toggleTheme}
                    title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                >
                    {isDark ? <Sun size={18} /> : <Moon size={18} />}
                    {!isCollapsed && (isDark ? 'Light Mode' : 'Dark Mode')}
                </ThemeButton>
            </Footer>
        </SidebarContainer>
    );
};
