// src/styles/GlobalStyle.ts
import { createGlobalStyle } from 'styled-components';

export const GlobalStyle = createGlobalStyle`
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  html {
    height: 100%;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
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