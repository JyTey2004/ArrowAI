// src/styles/theme/darkTheme.ts
import type { Theme } from '../../types/theme'


export const darkTheme: Theme = {
    // Basic colors
    background: '#0f172a',
    surface: '#1e293b',
    border: '#334155',

    // Text colors
    textPrimary: '#f1f5f9',
    textSecondary: '#94a3b8',

    // Blue accent system
    accent: '#60a5fa',
    accentHover: '#3b82f6',
    accentLight: '#1e3a8a',
    accentDark: '#1d4ed8',

    // Interactive colors (using blue accents)
    primary: '#60a5fa',
    primaryHover: '#3b82f6',

    // Glass system with blue tint
    glassBackground: 'rgba(15, 23, 42, 0.8)',
    glassBorder: 'rgba(96, 165, 250, 0.2)',
    glassHover: 'rgba(96, 165, 250, 0.1)',
    glassActive: 'rgba(96, 165, 250, 0.15)',

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