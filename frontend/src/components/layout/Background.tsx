// src/components/layout/Background.tsx
import styled from 'styled-components';

export const Background = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: ${props => props.theme.background};
  z-index: -1;
  transition: background-color 0.3s ease;
`;