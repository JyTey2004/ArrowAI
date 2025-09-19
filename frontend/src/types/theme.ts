// src/types/theme.ts
export interface Theme {
  // Basic colors
  background: string;
  surface: string;
  border: string;

  // Text colors
  textPrimary: string;
  textSecondary: string;

  // Blue accent system
  accent: string;
  accentHover: string;
  accentLight: string;
  accentDark: string;

  // Interactive colors
  primary: string;
  primaryHover: string;

  // Glass system
  glassBackground: string;
  glassBorder: string;
  glassHover: string;
  glassActive: string;
}