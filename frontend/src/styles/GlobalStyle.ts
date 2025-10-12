// src/styles/GlobalStyle.ts
import { createGlobalStyle } from 'styled-components';
import casualFont from '../font/Casual-Regular.ttf';

export const GlobalStyle = createGlobalStyle`
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  @font-face {
    font-family: 'Casual';
    src: url(${casualFont}) format('truetype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
  }

  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  html {
    height: 100%;
  }

  body {
    font-family: 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
    background-color: ${props => props.theme.background};
    color: ${props => props.theme.textPrimary};
    height: 100%;
    line-height: 1.6;
    transition: background-color 0.3s ease, color 0.3s ease;
  }

  #root {
    height: 100vh;
  }

  button {
    cursor: pointer;
    font-family: inherit;
  }

  input {
    font-family: inherit;
  }
`;
