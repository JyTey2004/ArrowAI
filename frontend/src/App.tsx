// src/App.tsx
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeContextProvider } from './contexts/ThemeContext';
import { ChatContextProvider } from './contexts/ChatContext';
import { MainLayout } from './components/layout/MainLayout';
import { GlobalStyle } from './styles/GlobalStyle';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <ThemeContextProvider>
        <ChatContextProvider>
          <GlobalStyle />
          <MainLayout />
        </ChatContextProvider>
      </ThemeContextProvider>
    </BrowserRouter>
  );
};

export default App;