// src/styles/theme/lightTheme.ts
import type { Theme } from '../../types/theme';

export const lightTheme: Theme = {
  // Basic colors
  background: '#f8fafc',
  surface: '#ffffff',
  border: '#e2e8f0',

  // Text colors
  textPrimary: '#1e293b',
  textSecondary: '#64748b',

  // Blue accent system
  accent: '#3b82f6',
  accentHover: '#2563eb',
  accentLight: '#dbeafe',
  accentDark: '#1d4ed8',

  // Interactive colors (using blue accents)
  primary: '#3b82f6',
  primaryHover: '#2563eb',

  // Glass system with blue tint
  glassBackground: 'rgba(248, 250, 252, 0.8)',
  glassBorder: 'rgba(59, 130, 246, 0.2)',
  glassHover: 'rgba(59, 130, 246, 0.1)',
  glassActive: 'rgba(59, 130, 246, 0.15)',

  // success system
  success: '#22c55e',
  successHover: '#16a34a',
  successLight: '#166534',
  successDark: '#15803d',

  // warning system
  warning: '#eab308',
  warningHover: '#ca8a04',
  warningLight: '#fbbf24',
  warningDark: '#b45309',

  // error system
  error: '#ef4444',
  errorHover: '#dc2626',
  errorLight: '#b91c1c',
  errorDark: '#991b1b',
};