---
name: Trace.ai Design System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e1e9f8'
  surface-container-high: '#d4def1'
  surface-container-highest: '#c6d3eb'
  on-surface: '#1a1c1e'
  on-surface-variant: '#43474e'
  outline: '#73777f'
  outline-variant: '#c3c7cf'
  primary: '#1e293b'
  on-primary: '#ffffff'
  primary-container: '#d9e2ff'
  on-primary-container: '#001945'
  secondary: '#565e71'
  on-secondary: '#ffffff'
  secondary-container: '#dae2f9'
  on-secondary-container: '#131c2b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#410002'
  success: '#15803d'
  on-success: '#ffffff'
  warning: '#b45309'
  on-warning: '#ffffff'

typography:
  font-family: 'Geist, sans-serif'
  scales:
    display-lg: { size: '57px', weight: '700', letter-spacing: '-0.02em' }
    headline-md: { size: '28px', weight: '600', letter-spacing: '-0.01em' }
    title-lg: { size: '22px', weight: '600', letter-spacing: '0' }
    body-md: { size: '16px', weight: '400', letter-spacing: '0.01em' }
    label-md: { size: '12px', weight: '500', letter-spacing: '0.05em' }

spacing:
  margin-desktop: '24px'
  gutter: '16px'
  radius-lg: '16px'
  radius-md: '8px'

components:
  card:
    background: 'surface-container-lowest'
    border: '1px solid outline-variant'
    shadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
    padding: '24px'
  sidebar:
    width: '260px'
    background: 'surface'
    border-right: '1px solid outline-variant'
  navigation:
    active: 'primary-container'
    on-active: 'on-primary-container'

layout:
  structure: 'Three-column dashboard with fixed sidebar, scrollable anomaly feed, and central analysis view with right-side AI intelligence panel.'
---

# Trace.ai Dashboard Implementation Guide

## Overview
This document provides the technical specifications for implementing the Trace.ai Causal Analysis Dashboard. The design uses a premium, high-density light theme optimized for enterprise AI workflows.

## Core Features
1. **Anomaly Feed**: A left-hand list of detected issues with severity badges and impact percentages.
2. **Analysis Workspace**: A central area featuring a time-series line chart comparing Actual vs. Expected metrics.
3. **Causal Intelligence Panel**: A right-side panel displaying AI-generated hypotheses, confidence scores, and supporting evidence (logs).

## Styling Implementation
- **Borders**: Use ultra-thin 1px borders in `outline-variant` for section separation.
- **Shadows**: Use subtle, diffused shadows for cards to create depth without clutter.
- **Interactions**: Buttons should have a slight scale-down effect (98%) on click and a background color shift on hover.
