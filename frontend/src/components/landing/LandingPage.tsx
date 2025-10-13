import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Layers,
  MessageSquare,
  Play,
  ShieldCheck,
  Sparkles,
  Zap,
  Globe,
  Lock,
  ExternalLink,
  Divide,
  FileChartLine,
  SquareCheck,
  Twitter,
  Linkedin,
  Github,
  Mail,
  Dot,
  Upload,
  FileUp,
  CheckCircle2,
} from 'lucide-react';
import { useChat } from '../../contexts/ChatContext';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

// Register the ScrollTrigger plugin
gsap.registerPlugin(ScrollTrigger);

const LandingWrapper = styled.div`
  width: 100%;
  min-height: 100vh;
  background: #ffffff;
  color: #1a1a2e;
  overflow-x: hidden;
  font-family: inherit;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
`;

const FloatingNav = styled.nav`
  position: fixed;
  top: 24px;
  left: clamp(24px, 6vw, 60px);
  transform: none;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  width: min(calc(100% - clamp(24px, 6vw, 60px) * 2));
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.32), rgba(255, 255, 255, 0.08));
  backdrop-filter: blur(26px) saturate(200%);
  border-radius: 50px;
  box-shadow:
    0 18px 48px rgba(15, 23, 42, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.45),
    inset 0 0 0 1px rgba(99, 102, 241, 0.12);

  @media (max-width: 768px) {
    padding: 12px 20px;
    left: 16px;
    width: calc(100% - 32px);
  }
`;

const NavBrand = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  font-family: inherit;
  letter-spacing: 0.5px;
`;

const BrandMark = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
`;

const NavLinks = styled.div`
  display: flex;
  gap: 32px;

  @media (max-width: 768px) {
    display: none;
  }
`;

const NavLink = styled.button`
  background: none;
  border: none;
  color: #4b5563;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.3s ease;
  font-family: inherit;
  letter-spacing: -0.2px;

  &:hover {
    color: #1a1a2e;
  }
`;

const NavActions = styled.div`
  display: flex;
  gap: 16px;
`;

const SecondaryButton = styled.button`
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 10px;
  color: #1a1a2e;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  letter-spacing: -0.2px;

  &:hover {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.45);
  }

  @media (max-width: 768px) {
    display: none;
  }
`;

const PrimaryButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: #1a1a2e;
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  letter-spacing: -0.2px;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(26, 26, 46, 0.2);
    background: #2d2d44;
  }
`;

const HeroSection = styled.section`
  position: relative;
  width: 100%;
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 20vh 60px 10vh 60px;
  background: linear-gradient(180deg, #f1f3f6 0%, #e4e6ed 100%);

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at center, transparent 0%, rgba(255, 255, 255, 0.4) 100%);
    z-index: 1;
    pointer-events: none;
  }

  @media (max-width: 768px) {
    padding: 0 24px;
  }
`;

const HeroFeatureBoxes = styled.div`
  display: flex;
  gap: 24px;
  margin-top: 48px;
  justify-content: flex-start;
  flex-wrap: wrap;

  @media (max-width: 768px) {
    justify-content: center;
  }
`;

const FeatureBox = styled.div`
  position: relative;
  padding: 20px 24px;
  padding-left: 32px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px) saturate(180%);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 12px;
  transition: all 0.3s ease;
  max-width: 280px;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #6366f1, #8b5cf6);
    border-radius: 12px 0 0 12px;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(99, 102, 241, 0.3);
    transform: translateY(-2px);
  }

  @media (max-width: 768px) {
    max-width: 100%;
  }
`;

const FeatureBoxTitle = styled.div`
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 6px;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: 0.5px;
`;

const FeatureBoxDescription = styled.div`
  font-size: 14px;
  color: #4b5563;
  line-height: 1.5;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const DotCanvas = styled.canvas<{ $zIndex?: number }>`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: ${props => props.$zIndex || 1};
`;


const DotCanvasOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.2);
  z-index: 2;
  pointer-events: none;
`;


const HeroContent = styled.div`
  position: relative;
  z-index: 2;
  max-width: 960px;
  width: 100%;
  margin: 0 auto 0 0;
  text-align: left;

  @media (max-width: 768px) {
    margin: 0 auto;
    text-align: center;
  }
`;

const Badge = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 999px;
  color: #6366f1;
  font-size: 13px;
  backdrop-filter: blur(10px) saturate(180%);
  font-weight: 500;
  margin-bottom: 12px;
  font-family: inherit;
  letter-spacing: -0.1px;
`;

const HeroTitle = styled.h1`
  font-size: clamp(56px, 8vw, 96px);
  font-weight: 400;
  line-height: 1.05;
  margin-bottom: 24px;
  color: #1a1a2e;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: 1.2px;
`;

const HeroSubtitle = styled.p`
  font-size: clamp(17px, 2vw, 21px);
  color: #1d1f21ff;
  line-height: 1.5;
  margin-bottom: 48px;
  max-width: 620px;
  margin-left: 0;
  margin-right: 0;
  font-weight: 400;
  font-family: inherit;
  letter-spacing: 0.3px;

  @media (max-width: 768px) {
    margin-left: auto;
    margin-right: auto;
  }
`;

const HeroButtons = styled.div`
  display: flex;
  gap: 16px;
  justify-content: flex-start;
  flex-wrap: wrap;

  @media (max-width: 768px) {
    justify-content: center;
  }
`;

const OutlineButton = styled(PrimaryButton)`
  background: transparent;
  border: 1px solid #e5e7eb;
  color: #4b5563;

  &:hover {
    background: #f9fafb;
    border-color: #d1d5db;
    color: #1a1a2e;
  }
`;

interface FullWidthSectionProps {
  $isDark?: boolean;
}

const FullWidthSection = styled.section<FullWidthSectionProps>`
  width: 100%;
  padding: 120px 30px;
  background: ${props => (props.$isDark ? '#f9fafb' : '#ffffff')};

  @media (max-width: 768px) {
    padding: 80px 24px;
  }
`;

const SectionHeader = styled.div`
  max-width: 800px;
  margin: 0 auto 40px;
  text-align: center;
`;

const SectionTitle = styled.h2`
  font-size: clamp(36px, 5vw, 52px);
  font-weight: 400;
  margin-bottom: 20px;
  color: #1a1a2e;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: -1.5px;
`;

const SectionSubtitle = styled.p`
  font-size: 18px;
  color: #6b7280;
  line-height: 1.7;
  font-family: inherit;
  letter-spacing: 1px;
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 32px;
  max-width: 1400px;
  margin: 0 auto;
`;

const StatCard = styled.div`
  padding: 40px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  text-align: center;
  transition: all 0.3s ease;

  &:hover {
    border-color: #6366f1;
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  }
`;

const StatValue = styled.div`
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 12px;
  color: #1a1a2e;
  font-family: inherit;
  letter-spacing: -1.5px;
`;

const StatLabel = styled.div`
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
  font-family: inherit;
  letter-spacing: -0.2px;
`;


// --- [NEW STYLED COMPONENTS FOR VIDEO SECTION] ---
const VideoFeaturesSection = styled.section`
  /* The height of this section determines the scroll distance for the animation.
     A larger value means the user has to scroll more to play the full video. */
  height: 300vh;
  position: relative;
  background-color: #f9fafb; /* Or your desired background */
`;

const StickyContainer = styled.div`
  position: sticky;
  top: 0;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const VideoCanvas = styled.canvas`
  width: 100%;
  height: 100%;
  object-fit: contain;
`;

const FeatureTextOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  pointer-events: none;
`;

const FeatureTextItem = styled.div`
  position: absolute;
  max-width: 500px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(99, 102, 241, 0.1);
  opacity: 0; /* Initially hidden */
`;

const FeatureIcon = styled.div`
  width: 64px;
  height: 64px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f0f0ff, #e8e8ff);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  border: 1px solid rgba(99, 102, 241, 0.1);
`;

const FeatureTitle = styled.h3`
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #1a1a2e;
  font-family: inherit;
  letter-spacing: -0.4px;
`;

const FeatureDescription = styled.p`
  font-size: 15px;
  color: #6b7280;
  line-height: 1.7;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const DemoSection = styled(FullWidthSection)`
  position: relative;
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%);
  overflow: hidden;
`;

// Add these styled component variants
const SectionHeaderLight = styled(SectionHeader)`
  ${SectionTitle} {
    color: white;
  }
  
  ${SectionSubtitle} {
    color: rgba(255, 255, 255, 0.85);
  }
`;

const LiveTag = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 999px;
  color: #6366f1;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  letter-spacing: -0.1px;
`;

const DemoContainer = styled.div`
  position: relative;
  z-index: 1;
  max-width: 1600px;
  margin: 0 auto 80px;
`;

const DemoViewport = styled.div`
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
`;

const DemoToolbar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 30px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
`;

const ToolbarTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: white;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const DemoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  padding: 40px;
`;

const DemoCard = styled.div`
  padding: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  transition: all 0.3s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(99, 102, 241, 0.4);
    transform: translateY(-5px);
  }
`;

const DemoCardTitle = styled.div`
  font-size: 15px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
  font-family: inherit;
  letter-spacing: -0.3px;
`;

const DemoPromptsSection = styled.div`
  margin-bottom: 60px;
  position: relative;
  z-index: 1;
`;

const PromptsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  max-width: 1600px;
  margin: 0 auto;
`;

const PromptCard = styled.div`
  padding: 24px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;

  &:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(99, 102, 241, 0.5);
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.2);
  }
`;

const PromptHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
`;

const PromptCategory = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const PromptTime = styled.div`
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
`;

const PromptText = styled.div`
  font-size: 15px;
  color: white;
  line-height: 1.6;
  margin-bottom: 16px;
  font-weight: 500;
`;

const PromptFooter = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
`;

const UploadBadge = styled.div<{ $required: boolean }>`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: ${props => props.$required
    ? 'rgba(245, 158, 11, 0.15)'
    : 'rgba(34, 197, 94, 0.15)'};
  border: 1px solid ${props => props.$required
    ? 'rgba(245, 158, 11, 0.3)'
    : 'rgba(34, 197, 94, 0.3)'};
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  color: ${props => props.$required ? '#fbbf24' : '#4ade80'};
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const UploadType = styled.span`
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
`;

const TryButton = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 8px;
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    background: rgba(99, 102, 241, 0.3);
    border-color: rgba(99, 102, 241, 0.6);
    color: white;
  }
`;

const DemoSectionTitle = styled.h3`
  font-size: 24px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
  text-align: center;
  font-family: inherit;
  letter-spacing: -0.5px;
`;

const DemoSectionSubtitle = styled.p`
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 40px;
  text-align: center;
  max-width: 700px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.6;
`;

const DemoCardBody = styled.p`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const CTASection = styled(FullWidthSection)`
  position: relative;
  background: #ffffff;
`;

const CTAContent = styled.div`
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
`;

const CTATitle = styled.h2`
  font-size: clamp(36px, 5vw, 56px);
  font-weight: 500;
  margin-bottom: 24px;
  color: #1a1a2e;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: 1.5px;
`;

const CTASubtitle = styled.p`
  font-size: 19px;
  color: #6b7280;
  line-height: 1.7;
  margin-bottom: 40px;
  font-family: inherit;
  letter-spacing: -0.3px;
`;

const CTAButtons = styled.div`
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
`;

const VideoShowcaseSection = styled(FullWidthSection)`
background: linear-gradient(180deg, #f9fafb 0%, #ffffff 100%);
  padding: 120px 60px;

  @media (max-width: 968px) {
    padding: 80px 24px;
  }
`;

const ShowcaseContainer = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 60px;
  align-items: start;

  @media (max-width: 968px) {
    grid-template-columns: 1fr;
    gap: 40px;
  }
`;

const VideoContainer = styled.div`
  position: sticky;
  top: 120px;
  width: 100%;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  background: #000000;

  @media (max-width: 968px) {
    position: relative;
    top: 0;
  }
`;

const VideoPlayer = styled.video`
  width: 100%;
  height: auto;
  display: block;
`;

const FeaturesColumn = styled.div`
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 20px 0;
`;

const FeatureShowcaseCard = styled.div`
  padding: 40px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 16px;
  transition: all 0.4s ease;
  opacity: 0.4;
  transform: translateY(20px);

  &.active {
    opacity: 1;
    transform: translateY(0);
    border-color: #6366f1;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: 0 10px 40px rgba(99, 102, 241, 0.2);
  }

  &:hover {
    border-color: #6366f1;
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.15);
  }
`;

const FeatureNumber = styled.div`
  display: inline-block;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
`;

const CaseStudiesSection = styled(FullWidthSection)`
  background: linear-gradient(180deg, #f9fafb 0%, #ffffff 100%);
`;

const CaseStudiesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 32px;
  max-width: 1400px;
  margin: 0 auto 80px;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const CaseStudyCard = styled.div`
  padding: 40px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #ef4444, #f59e0b);
  }

  &:hover {
    border-color: #ef4444;
    transform: translateY(-5px);
    box-shadow: 0 20px 40px rgba(239, 68, 68, 0.15);
  }
`;

const CaseStudyLabel = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 6px;
  color: #ef4444;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 20px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;
const CaseStudyLinks = styled.div`
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
`;

const LinksLabel = styled.div`
  font-size: 12px;
  color: #9ca3af;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
`;

const LinksList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const CaseStudyLink = styled.a`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6366f1;
  text-decoration: none;
  transition: all 0.2s ease;
  padding: 6px 0;
  
  &:hover {
    color: #4f46e5;
    transform: translateX(4px);
  }

  svg {
    flex-shrink: 0;
  }
`;

const LinkText = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
`;

const CaseStudyTitle = styled.h3`
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #1a1a2e;
  font-family: inherit;
  letter-spacing: -0.5px;
  line-height: 1.3;
`;

const CaseStudyDescription = styled.p`
  font-size: 15px;
  color: #6b7280;
  line-height: 1.7;
  margin-bottom: 24px;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const CaseStudyImpact = styled.div`
  padding: 20px;
  background: #f9fafb;
  border-radius: 12px;
  border-left: 3px solid #ef4444;
`;

const ImpactLabel = styled.div`
  font-size: 12px;
  color: #9ca3af;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
`;

const ImpactValue = styled.div`
  font-size: 16px;
  color: #1a1a2e;
  font-weight: 600;
  line-height: 1.5;
`;

const SolutionShowcase = styled.div`
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%);
  border-radius: 20px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -50%;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
  }

  @media (max-width: 768px) {
    padding: 40px 24px;
  }
`;

const SolutionContent = styled.div`
  position: relative;
  z-index: 2;
  text-align: center;
`;

const SolutionTitle = styled.h3`
  font-size: clamp(28px, 4vw, 40px);
  font-weight: 700;
  color: white;
  margin-bottom: 24px;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: -1px;
`;

const SolutionSubtitle = styled.p`
  font-size: 18px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.7;
  margin-bottom: 48px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
`;

const SolutionFeaturesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 24px;
  margin-top: 40px;
`;

const SolutionFeatureBox = styled.div`
  padding: 32px 24px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  text-align: left;
  transition: all 0.3s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(99, 102, 241, 0.4);
    transform: translateY(-5px);
  }
`;

const SolutionFeatureIcon = styled.div`
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
`;

const SolutionFeatureTitle = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 8px;
  letter-spacing: -0.3px;
`;

const SolutionFeatureDescription = styled.div`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  letter-spacing: -0.2px;
`;

const Footer = styled.footer`
  position: relative;
  width: 100%;
  padding: 80px 60px 40px;
  background: #1a1a2e;
  color: white;
  overflow: hidden;

  @media (max-width: 768px) {
    padding: 60px 24px 32px;
  }
`;

const FooterBackground = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: clamp(80px, 15vw, 200px);
  font-weight: 700;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  color: rgba(255, 255, 255, 0.03);
  white-space: nowrap;
  letter-spacing: -0.02em;
  user-select: none;
  pointer-events: none;
  z-index: 0;
`;

const FooterContent = styled.div`
  position: relative;
  z-index: 1;
  max-width: 1400px;
  margin: 0 auto;
`;

const FooterGrid = styled.div`
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 60px;
  margin-bottom: 60px;

  @media (max-width: 968px) {
    grid-template-columns: 1fr 1fr;
    gap: 40px;
  }

  @media (max-width: 640px) {
    grid-template-columns: 1fr;
    gap: 32px;
  }
`;

const FooterBrand = styled.div``;

const FooterBrandLogo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
`;

const FooterBrandMark = styled.div`
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 18px;
`;

const FooterBrandName = styled.div`
  font-size: 20px;
  font-weight: 600;
  color: white;
  font-family: inherit;
  letter-spacing: 0.5px;
`;

const FooterBrandDescription = styled.p`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.7;
  max-width: 300px;
`;

const FooterColumn = styled.div``;

const FooterColumnTitle = styled.h4`
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 20px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const FooterLinks = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const FooterLink = styled.a`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  transition: color 0.3s ease;
  cursor: pointer;

  &:hover {
    color: #6366f1;
  }
`;

const FooterBottom = styled.div`
  padding-top: 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;

  @media (max-width: 640px) {
    flex-direction: column;
    text-align: center;
  }
`;

const FooterCopyright = styled.div`
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
`;

const FooterSocial = styled.div`
  display: flex;
  gap: 16px;
`;

const SocialLink = styled.a`
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.6);
  transition: all 0.3s ease;
  cursor: pointer;

  &:hover {
    background: rgba(99, 102, 241, 0.2);
    color: #6366f1;
    transform: translateY(-2px);
  }
`;

const DotGrid: React.FC<{ variant?: 'full' | 'semicircles'; zIndex?: number }> = ({
  variant = 'full',
  zIndex = 1
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    type Dot = {
      x: number;
      y: number;
      baseSize: number;
      phase: number;
    };

    const dots: Dot[] = [];
    const spacing = 30;

    const resizeCanvas = () => {
      const { clientWidth, clientHeight } = canvas;
      const pixelRatio = window.devicePixelRatio || 1;

      canvas.width = clientWidth * pixelRatio;
      canvas.height = clientHeight * pixelRatio;
      ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

      dots.length = 0;

      if (variant === 'semicircles') {
        // Create dots only on left and right semicircles
        const centerY = clientHeight / 2;
        const radius = clientHeight / 2;

        for (let x = -spacing; x < clientWidth + spacing; x += spacing) {
          for (let y = -spacing; y < clientHeight + spacing; y += spacing) {
            // Left semicircle (centered at left edge)
            const distFromLeftCenter = Math.sqrt(Math.pow(x, 2) + Math.pow(y - centerY, 2));

            // Right semicircle (centered at right edge)
            const distFromRightCenter = Math.sqrt(
              Math.pow(x - clientWidth, 2) + Math.pow(y - centerY, 2)
            );

            // Only add dots within the semicircle radius
            if (distFromLeftCenter < radius || distFromRightCenter < radius) {
              dots.push({
                x,
                y,
                baseSize: 1 + Math.random() * 1,
                phase: Math.random() * Math.PI * 2,
              });
            }
          }
        }
      } else {
        // Full canvas coverage (original behavior)
        for (let x = -spacing; x < clientWidth + spacing; x += spacing) {
          for (let y = -spacing; y < clientHeight + spacing; y += spacing) {
            dots.push({
              x,
              y,
              baseSize: 1 + Math.random() * 1,
              phase: Math.random() * Math.PI * 2,
            });
          }
        }
      }
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    let animationFrame = 0;
    let tick = 0;

    const animate = () => {
      const { clientWidth, clientHeight } = canvas;
      ctx.clearRect(0, 0, clientWidth, clientHeight);
      tick += 0.01;

      dots.forEach(dot => {
        const wave = Math.sin(dot.x * 0.045 - tick * 2.4 + dot.phase);
        const size = dot.baseSize + wave * 1.3;
        const opacity = 0.16 + wave * 0.28;

        ctx.fillStyle = `rgba(99, 102, 241, ${Math.max(0.08, Math.min(0.42, opacity))})`;
        ctx.beginPath();
        ctx.arc(dot.x, dot.y, Math.max(0, size), 0, Math.PI * 2);
        ctx.fill();
      });

      animationFrame = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, [variant]);

  return <DotCanvas ref={canvasRef} $zIndex={zIndex} />;
};



const stats = [
  { value: '4+', label: 'Specialist Agents' },
  { value: '12K', label: 'Automation Steps' },
  { value: '3x', label: 'Delivery Velocity' },
  { value: '99.9%', label: 'Uptime SLA' }
];

const features = [
  {
    icon: <BrainCircuit size={28} />,
    title: 'Multi-Agent Orchestration',
    description: 'Coordinated AI specialists handle code generation, research analysis, content creation, and presentation design simultaneously.',
    startTime: 0,
    endTime: 10
  },
  {
    icon: <Layers size={28} />,
    title: 'Unified Knowledge Layer',
    description: 'Every artifact, decision, and insight flows through a synchronized context engine that keeps all agents aligned.',
    startTime: 10,
    endTime: 20
  },
  {
    icon: <Divide size={28} />,
    title: 'Divide and Conquer',
    description: 'Break complex projects into manageable tasks, assign them to the right agents, and watch them execute flawlessly.',
    startTime: 20,
    endTime: 30
  },
  {
    icon: <FileChartLine size={28} />,
    title: 'Data-Driven Approach',
    description: 'Integrate your data sources and let agents analyze, visualize, and derive insights to inform every step of the project.',
    startTime: 30,
    endTime: 120
  },
  {
    icon: <Globe size={28} />,
    title: 'Research and fact-checking',
    description: 'Agents autonomously gather information from the web, validate sources, and ensure all outputs are accurate and up-to-date.',
    startTime: 120,
    endTime: 150
  },
  {
    icon: <Sparkles size={28} />,
    title: 'Creative Content Generation',
    description: 'From drafting reports to designing presentations, specialized agents craft high-quality content tailored to your audience.',
    startTime: 150,
    endTime: 180
  },
  {
    icon: <SquareCheck size={28} />,
    title: 'Evaluation and Quality Control',
    description: 'All outputs undergo rigorous evaluation by specialized agents to ensure they meet your standards and objectives.',
    startTime: 180,
    endTime: 200
  }
];

const demoPrompts = [
  {
    category: "Market Research",
    prompt: "Analyze the enterprise AI market and create a competitive landscape report with top 10 players",
    estimatedTime: "5 min",
    requiresUpload: false,
    icon: <Globe size={18} />
  },
  {
    category: "Financial Analysis",
    prompt: "Compare our Q4 sales performance vs. competitors using uploaded financial data",
    estimatedTime: "3 min",
    requiresUpload: true,
    uploadType: "CSV, XLSX",
    icon: <BarChart3 size={18} />
  },
  {
    category: "Customer Insights",
    prompt: "Analyze customer usage patterns and create segmentation report from uploaded data",
    estimatedTime: "6 min",
    requiresUpload: true,
    uploadType: "CSV, JSON",
    icon: <BrainCircuit size={18} />
  },
  {
    category: "Due Diligence",
    prompt: "Research GDPR and CCPA compliance requirements for our healthcare AI product",
    estimatedTime: "7 min",
    requiresUpload: false,
    icon: <ShieldCheck size={18} />
  },
  {
    category: "Strategy Planning",
    prompt: "Develop go-to-market strategy with pricing analysis for new AI product launch",
    estimatedTime: "8 min",
    requiresUpload: false,
    icon: <Sparkles size={18} />
  },
  {
    category: "Competitive Intel",
    prompt: "Analyze competitor product features and pricing from uploaded market research data",
    estimatedTime: "4 min",
    requiresUpload: true,
    uploadType: "PDF, DOCX",
    icon: <Zap size={18} />
  }
];

const caseStudies = [
  {
    label: 'Healthcare',
    title: 'Medical AI Diagnostic System Faces Regulatory Scrutiny',
    description: 'A hospital\'s AI diagnostic tool made critical treatment recommendations, but auditors couldn\'t verify the reasoning process. Without execution logs, the hospital faced potential liability and had to suspend the system.',
    impact: 'System suspended for 6 months, $2.3M in compliance costs',
    links: [
      'https://www.statnews.com/2018/07/25/ibm-watson-recommended-unsafe-incorrect-treatments/',
      'https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/2781307',
      'https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles'
    ]
  },
  {
    label: 'Financial Services',
    title: 'Bank\'s Credit Scoring AI Under Investigation',
    description: 'Regulators questioned potential bias in loan approvals. The bank couldn\'t produce decision trails or data provenance, resulting in fines and mandated system overhaul.',
    impact: '$15M penalty, 18-month remediation project',
    links: [
      'https://www.dfs.ny.gov/reports_and_publications/202103_report_apple_card_investigation',
      'https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/',
      'https://www.consumerfinance.gov/about-us/newsroom/cfpb-issues-guidance-on-credit-denials-by-lenders-using-artificial-intelligence/'
    ]
  },
  {
    label: 'Legal Tech',
    title: 'Contract Analysis AI Creates Legal Exposure',
    description: 'A law firm\'s AI missed critical clauses in multi-million dollar contracts. Without audit trails of what the AI analyzed and why, the firm couldn\'t defend their due diligence process.',
    impact: 'Malpractice claim, loss of major client accounts',
    links: [
      'https://law.justia.com/cases/federal/district-courts/new-york/nysdce/1%3A2022cv01461/575368/54/',
      'https://www.goldbergsegalla.com/app/uploads/2023/10/Fake-Cases-Real-Consequences-Misuse-of-ChatGPT-Christoper-F.-Lyon-NY-Litigator.pdf'
    ]
  }
];


const solutionFeatures = [
  {
    icon: <BarChart3 size={24} />,
    title: 'Complete Orchestration Logs',
    description: 'Every agent interaction, decision point, and workflow step recorded with timestamps'
  },
  {
    icon: <MessageSquare size={24} />,
    title: 'Code & Execution Traces',
    description: 'Full code generated, evaluation results, and runtime metadata captured automatically'
  },
  {
    icon: <ShieldCheck size={24} />,
    title: 'Data Provenance Tracking',
    description: 'Source attribution, data transformations, and lineage for every insight produced'
  },
  {
    icon: <Layers size={24} />,
    title: 'Versioned Artifacts',
    description: 'Complete history of outputs with rollback capabilities and change tracking'
  }
];

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { addNewChat, activeChat } = useChat();
  const featuresRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [activeFeatureIndex, setActiveFeatureIndex] = useState(0);

  // Video progress tracking
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const currentTime = video.currentTime;

      // Find which feature should be active based on current time
      const activeIndex = features.findIndex(
        (feature) => currentTime >= feature.startTime && currentTime < feature.endTime
      );

      // If a valid feature is found, set it as active, otherwise keep the last one
      if (activeIndex !== -1) {
        setActiveFeatureIndex(activeIndex);
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, []);


  // const canvasRef = useRef<HTMLCanvasElement>(null);
  // const sectionRef = useRef<HTMLDivElement>(null);

  // const frameCount = 226; // The total number of image frames
  // const SCROLL_MULTIPLIER = 1; // try 2–5


  // useEffect(() => {
  //   const canvas = canvasRef.current;
  //   const sectionEl = sectionRef.current;
  //   if (!canvas || !sectionEl) return;
  //   const ctx = canvas.getContext('2d');
  //   if (!ctx) return;

  //   // --- helpers: find actual scroll container & relative offsets ---
  //   const isScrollable = (el: Element) => {
  //     const s = getComputedStyle(el);
  //     return /(auto|scroll)/.test(s.overflowY) || /(auto|scroll)/.test(s.overflow);
  //   };
  //   const getScrollParent = (el: Element | null): HTMLElement | null => {
  //     let p = el?.parentElement || null;
  //     while (p && p !== document.body && p !== document.documentElement) {
  //       if (isScrollable(p)) return p as HTMLElement;
  //       p = p.parentElement;
  //     }
  //     // if body/html are the scroller, return null (means window)
  //     return null;
  //   };
  //   const getOffsetTopWithin = (el: HTMLElement, root: HTMLElement): number => {
  //     let y = 0;
  //     let n: HTMLElement | null = el;
  //     while (n && n !== root) {
  //       y += n.offsetTop;
  //       n = n.offsetParent as HTMLElement | null;
  //     }
  //     return y;
  //   };

  //   // find the real scroller (null => window)
  //   const scrollerEl = getScrollParent(sectionEl);
  //   const useWindow = !scrollerEl;

  //   const dpr = window.devicePixelRatio || 1;
  //   const frame = { current: 0 };

  //   // base path safe URLs
  //   const base =
  //     (import.meta as any)?.env?.BASE_URL ||
  //     (typeof process !== 'undefined' ? (process as any).env?.PUBLIC_URL : '') ||
  //     '';
  //   const urlFor = (n: number) => `${base}/frames/frame_${String(n).padStart(4, '0')}.jpg`;

  //   // preload images
  //   const images: HTMLImageElement[] = new Array(frameCount);
  //   const loadImages = () =>
  //     Promise.all(
  //       Array.from({ length: frameCount }, (_, i) => {
  //         const img = new Image();
  //         const url = urlFor(i + 1);
  //         images[i] = img;
  //         return new Promise<void>((resolve) => {
  //           img.onload = () => resolve();
  //           img.onerror = () => {
  //             console.warn('[frames] failed to load:', url);
  //             resolve();
  //           };
  //           img.src = url;
  //         });
  //       })
  //     );

  //   const sizeCanvas = () => {
  //     const cssW = canvas.clientWidth || 1920;
  //     const cssH = canvas.clientHeight || 1080;
  //     canvas.width = cssW * dpr;
  //     canvas.height = cssH * dpr;
  //     ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  //   };

  //   const draw = () => {
  //     const idx = Math.floor(frame.current);
  //     const img = images[idx];
  //     if (!img || !img.complete || !img.naturalWidth) return;
  //     const w = canvas.clientWidth || 1920;
  //     const h = canvas.clientHeight || 1080;
  //     ctx.clearRect(0, 0, w, h);
  //     ctx.drawImage(img, 0, 0, w, h);
  //   };

  //   // manual progress relative to the real scroller
  //   const manualProgress = () => {
  //     // recompute current dims each time (in case of resize)
  //     const vhNow = useWindow ? window.innerHeight : scrollerEl!.clientHeight;
  //     const realNow = sectionEl.offsetHeight - vhNow;
  //     const virtualNow = Math.max(0, realNow * SCROLL_MULTIPLIER);

  //     if (useWindow) {
  //       const rect = sectionEl.getBoundingClientRect();
  //       const passed = Math.min(Math.max(-rect.top, 0), virtualNow); // clamp 0..virtual
  //       return virtualNow ? passed / virtualNow : 0;
  //     } else {
  //       const sectionTop = getOffsetTopWithin(sectionEl, scrollerEl!);
  //       const rel = Math.min(Math.max(scrollerEl!.scrollTop - sectionTop, 0), virtualNow);
  //       return virtualNow ? rel / virtualNow : 0;
  //     }
  //   };


  //   // clean slate
  //   ScrollTrigger.getAll().forEach(t => t.kill());
  //   sizeCanvas();

  //   loadImages().then(() => {
  //     // draw first available
  //     let first = 0;
  //     for (let i = 0; i < frameCount; i++) {
  //       if (images[i]?.complete && images[i].naturalWidth) { first = i; break; }
  //     }
  //     frame.current = first;
  //     draw();
  //     // after you resolve useWindow / scrollerEl and before creating triggers
  //     const vh = useWindow ? window.innerHeight : scrollerEl!.clientHeight;
  //     const realScrollable = sectionEl.offsetHeight - vh;           // px the section can actually scroll
  //     const VIRTUAL_TOTAL_PX = Math.max(0, realScrollable * SCROLL_MULTIPLIER);

  //     // ScrollTrigger (now pointing at the correct scroller)
  //     const stCfg: any = {
  //       trigger: sectionEl,
  //       start: 'top top',
  //       end: () => '+=' + VIRTUAL_TOTAL_PX,   // exact same virtual distance
  //       scrub: true,
  //       onUpdate: (self: ScrollTrigger) => {
  //         const idx = Math.min(frameCount - 1, Math.floor(self.progress * (frameCount - 1)));
  //         if (idx !== frame.current) { frame.current = idx; draw(); }
  //       },
  //       onLeave: () => {                       // guarantee last frame if user blasts past
  //         frame.current = frameCount - 1;
  //         draw();
  //       },
  //       onLeaveBack: () => {                   // and first frame on reverse
  //         frame.current = 0;
  //         draw();
  //       },
  //     };
  //     if (!useWindow) stCfg.scroller = scrollerEl;
  //     ScrollTrigger.create(stCfg);

  //     // manual fallback (also drives frames; harmless to run alongside ST)
  //     const onScroll = () => {
  //       const p = Math.min(1, Math.max(0, manualProgress()));
  //       const eased = p; // you can apply easing if you like
  //       const idx = (eased > 0.995) ? (frameCount - 1) : Math.floor(eased * (frameCount - 1));
  //       if (idx !== frame.current) {
  //         frame.current = idx;
  //         draw();
  //       }
  //     };

  //     const scrollTarget: any = useWindow ? window : scrollerEl!;
  //     scrollTarget.addEventListener('scroll', onScroll, { passive: true });

  //     const onResize = () => {
  //       sizeCanvas();
  //       draw();
  //       ScrollTrigger.refresh();
  //       onScroll();
  //     };
  //     window.addEventListener('resize', onResize);

  //     // initial sync
  //     ScrollTrigger.refresh();
  //     onScroll();

  //     return () => {
  //       ScrollTrigger.getAll().forEach(t => t.kill());
  //       scrollTarget.removeEventListener('scroll', onScroll);
  //       window.removeEventListener('resize', onResize);
  //     };
  //   });

  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, []);



  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const launchWorkspace = () => {
    const chatId = addNewChat();
    navigate(`/chat/${chatId}`);
  };

  const goToDashboard = () => {
    if (activeChat) {
      navigate(`/chat/${activeChat}`);
    } else {
      launchWorkspace();
    }
  };

  return (
    <LandingWrapper>
      <FloatingNav>
        <NavBrand>
          {/* <BrandMark>AI</BrandMark> */}
          ArrowAI Studio
        </NavBrand>
        <NavLinks>
          <NavLink onClick={() => scrollToSection('features')}>Features</NavLink>
          <NavLink onClick={() => scrollToSection('case-studies')}>Case Studies</NavLink>
          <NavLink onClick={() => scrollToSection('demo')}>Demo</NavLink>
        </NavLinks>
        <NavActions>
          <SecondaryButton onClick={goToDashboard}>Dashboard</SecondaryButton>
          <PrimaryButton onClick={launchWorkspace}>
            Launch
            <ArrowRight size={16} />
          </PrimaryButton>
        </NavActions>
      </FloatingNav>

      <HeroSection>
        <DotGrid variant="full" />
        <DotCanvasOverlay />
        <HeroContent>
          {/* <Badge>
      <Sparkles size={14} />
      Auditable AI Platform
    </Badge> */}
          <HeroTitle>
            AI Consulting <br />Made Effortless
          </HeroTitle>
          <HeroSubtitle>
            Multi-agent AI system that researches, analyzes, and delivers
            publication-ready reports with verified data and full audit trails.
          </HeroSubtitle>
          <HeroButtons>
            <PrimaryButton onClick={launchWorkspace}>
              Get Started
              <ArrowRight size={20} />
            </PrimaryButton>
            <OutlineButton onClick={() => scrollToSection('features')}>
              Demo
              <Play size={20} />
            </OutlineButton>
          </HeroButtons>
          <HeroFeatureBoxes>
            <FeatureBox>
              <FeatureBoxTitle>Auditable</FeatureBoxTitle>
              <FeatureBoxDescription>
                Track every decision and insight with full transparency
              </FeatureBoxDescription>
            </FeatureBox>
            <FeatureBox>
              <FeatureBoxTitle>Fact-Checked</FeatureBoxTitle>
              <FeatureBoxDescription>
                Verified information backed by reliable sources
              </FeatureBoxDescription>
            </FeatureBox>
            <FeatureBox>
              <FeatureBoxTitle>Data-Driven</FeatureBoxTitle>
              <FeatureBoxDescription>
                Insights powered by comprehensive analysis
              </FeatureBoxDescription>
            </FeatureBox>
          </HeroFeatureBoxes>
        </HeroContent>
      </HeroSection>

      <VideoShowcaseSection id="features">
        <SectionHeader>
          <SectionTitle>Works like a team</SectionTitle>
          {/* <SectionSubtitle>
            Specialized AI agents collaborate seamlessly to deliver high-quality, data-driven reports and analyses.
          </SectionSubtitle> */}
        </SectionHeader>

        <ShowcaseContainer>
          <VideoContainer>
            <VideoPlayer
              ref={videoRef}
              controls
              autoPlay
              muted
              loop
            >
              <source src="/videos/features-video.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </VideoPlayer>
          </VideoContainer>

          <FeaturesColumn>
            {features.map((feature, index) => (
              <FeatureShowcaseCard
                key={index}
                className={activeFeatureIndex === index ? 'active' : ''}
                onClick={() => {
                  if (videoRef.current) {
                    videoRef.current.currentTime = feature.startTime;
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <FeatureNumber>{index + 1}</FeatureNumber>
                <FeatureIcon>{feature.icon}</FeatureIcon>
                <FeatureTitle>{feature.title}</FeatureTitle>
                <FeatureDescription>{feature.description}</FeatureDescription>
              </FeatureShowcaseCard>
            ))}
          </FeaturesColumn>
        </ShowcaseContainer>
      </VideoShowcaseSection>

      <CaseStudiesSection id="case-studies">
        <SectionHeader>
          <SectionTitle>Why Auditability Matters</SectionTitle>
        </SectionHeader>

        <CaseStudiesGrid>
          {caseStudies.map((study, index) => (
            <CaseStudyCard key={index}>
              <CaseStudyLabel>{study.label}</CaseStudyLabel>
              <CaseStudyTitle>{study.title}</CaseStudyTitle>
              <CaseStudyDescription>{study.description}</CaseStudyDescription>
              <CaseStudyImpact>
                <ImpactLabel>Impact</ImpactLabel>
                <ImpactValue>{study.impact}</ImpactValue>
              </CaseStudyImpact>

              {study.links && study.links.length > 0 && (
                <CaseStudyLinks>
                  <LinksLabel>References</LinksLabel>
                  <LinksList>
                    {study.links.map((link, linkIndex) => (
                      <CaseStudyLink
                        key={linkIndex}
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink size={14} />
                        <LinkText>{new URL(link).hostname.replace('www.', '')}</LinkText>
                      </CaseStudyLink>
                    ))}
                  </LinksList>
                </CaseStudyLinks>
              )}
            </CaseStudyCard>
          ))}
        </CaseStudiesGrid>

        <SolutionShowcase>
          <SolutionContent>
            <SolutionTitle>ArrowAI Solves This</SolutionTitle>
            <SolutionSubtitle>
              Built-in auditability from the ground up. Every decision, every step, every output —
              fully traceable, explainable, and defensible.
            </SolutionSubtitle>

            <SolutionFeaturesGrid>
              {solutionFeatures.map((feature, index) => (
                <SolutionFeatureBox key={index}>
                  <SolutionFeatureIcon>{feature.icon}</SolutionFeatureIcon>
                  <SolutionFeatureTitle>{feature.title}</SolutionFeatureTitle>
                  <SolutionFeatureDescription>{feature.description}</SolutionFeatureDescription>
                </SolutionFeatureBox>
              ))}
            </SolutionFeaturesGrid>
          </SolutionContent>
        </SolutionShowcase>
      </CaseStudiesSection>

      {/* <VideoFeaturesSection
        ref={sectionRef}
        id="features"
        style={{ height: `${900 * SCROLL_MULTIPLIER}vh` }}   // <-- override the 300vh
      >
        <StickyContainer>
          <VideoCanvas ref={canvasRef} />
          <FeatureTextOverlay>
            {features.map((feature, index) => (
              <FeatureTextItem key={index} className="feature-text-item">
                <FeatureIcon>{feature.icon}</FeatureIcon>
                <FeatureTitle>{feature.title}</FeatureTitle>
                <FeatureDescription>{feature.description}</FeatureDescription>
              </FeatureTextItem>
            ))}
          </FeatureTextOverlay>
        </StickyContainer>
      </VideoFeaturesSection> */}

      <DemoSection id="demo">
        <DotGrid variant="semicircles" zIndex={0} />

        <SectionHeaderLight>
          <SectionTitle>See It In Action</SectionTitle>
        </SectionHeaderLight>

        {/* Example Prompts */}
        <DemoPromptsSection>
          <DemoSectionTitle>Example Consulting Prompts</DemoSectionTitle>
          <DemoSectionSubtitle>
            Click any prompt to see how ArrowAI orchestrates multiple agents, researches data, and delivers comprehensive results
          </DemoSectionSubtitle>

          <PromptsGrid>
            {demoPrompts.map((prompt, index) => (
              <PromptCard key={index} onClick={launchWorkspace}>
                <PromptHeader>
                  <PromptCategory>
                    {prompt.icon}
                    {prompt.category}
                  </PromptCategory>
                  <PromptTime>{prompt.estimatedTime}</PromptTime>
                </PromptHeader>

                <PromptText>{prompt.prompt}</PromptText>

                <PromptFooter>
                  <UploadBadge $required={prompt.requiresUpload}>
                    {prompt.requiresUpload ? (
                      <>
                        <FileUp size={12} />
                        Data Upload
                        {prompt.uploadType && (
                          <UploadType>· {prompt.uploadType}</UploadType>
                        )}
                      </>
                    ) : (
                      <>
                        <CheckCircle2 size={12} />
                        No Upload
                      </>
                    )}
                  </UploadBadge>

                  <TryButton>
                    Try Now
                    <Play size={14} />
                  </TryButton>
                </PromptFooter>
              </PromptCard>
            ))}
          </PromptsGrid>
        </DemoPromptsSection>

        {/* Live Demo Viewport */}
        {/* <DemoContainer>
          <DemoSectionTitle>Live Workspace Demo</DemoSectionTitle>
          <DemoSectionSubtitle>
            See how ArrowAI tracks every step of the process
          </DemoSectionSubtitle>

          <DemoViewport>
            <DemoToolbar>
              <ToolbarTitle>ArrowAI Workspace · Live Demo</ToolbarTitle>
              <LiveTag>
                <BarChart3 size={14} />
                Active Session
              </LiveTag>
            </DemoToolbar>
            <DemoGrid>
              {demoHighlights.map(highlight => (
                <DemoCard key={highlight.title}>
                  <DemoCardTitle>{highlight.title}</DemoCardTitle>
                  <DemoCardBody>{highlight.body}</DemoCardBody>
                </DemoCard>
              ))}
            </DemoGrid>
          </DemoViewport>
        </DemoContainer> */}
      </DemoSection>

      <CTASection id="get-started">
        <CTAContent>
          <CTATitle>Ready to Get Started?</CTATitle>
          <CTASubtitle>
            Join teams building trustworthy AI systems with complete auditability and transparency.
          </CTASubtitle>
          <CTAButtons>
            <PrimaryButton onClick={launchWorkspace}>
              Launch Workspace
              <ArrowRight size={20} />
            </PrimaryButton>
            <OutlineButton onClick={() => { }}>
              Schedule Demo
              <MessageSquare size={20} />
            </OutlineButton>
          </CTAButtons>
        </CTAContent>
      </CTASection>

      <Footer>
        <FooterBackground>ArrowAI</FooterBackground>
        <FooterContent>
          <FooterGrid>
            <FooterBrand>
              <FooterBrandLogo>
                <FooterBrandMark>AI</FooterBrandMark>
                <FooterBrandName>ArrowAI Studio</FooterBrandName>
              </FooterBrandLogo>
              <FooterBrandDescription>
                The trust layer for intelligent systems — recording every reasoning step,
                dataset, and output so decisions are explainable and auditable.
              </FooterBrandDescription>
            </FooterBrand>

            <FooterColumn>

            </FooterColumn>

            <FooterColumn>
              <FooterColumnTitle>Product</FooterColumnTitle>
              <FooterLinks>
                <FooterLink onClick={() => scrollToSection('features')}>Features</FooterLink>
                <FooterLink onClick={() => scrollToSection('demo')}>Demo</FooterLink>
                <FooterLink onClick={() => scrollToSection('case-studies')}>Case Studies</FooterLink>
                <FooterLink onClick={launchWorkspace}>Get Started</FooterLink>
              </FooterLinks>
            </FooterColumn>

            <FooterColumn>
              <FooterColumnTitle>Company</FooterColumnTitle>
              <FooterLinks>
                <FooterLink href="#">About</FooterLink>
                <FooterLink href="#">Blog</FooterLink>
                <FooterLink href="#">Careers</FooterLink>
                <FooterLink href="#">Contact</FooterLink>
              </FooterLinks>
            </FooterColumn>

            {/* <FooterColumn>
              <FooterColumnTitle>Legal</FooterColumnTitle>
              <FooterLinks>
                <FooterLink href="#">Privacy Policy</FooterLink>
                <FooterLink href="#">Terms of Service</FooterLink>
                <FooterLink href="#">Security</FooterLink>
                <FooterLink href="#">Compliance</FooterLink>
              </FooterLinks>
            </FooterColumn> */}
          </FooterGrid>

          <FooterBottom>
            <FooterCopyright>
              © {new Date().getFullYear()} ArrowAI Studio. All rights reserved.
            </FooterCopyright>
            <FooterSocial>
              <SocialLink href="#" target="_blank" rel="noopener noreferrer">
                <Twitter size={18} />
              </SocialLink>
              <SocialLink href="#" target="_blank" rel="noopener noreferrer">
                <Linkedin size={18} />
              </SocialLink>
              <SocialLink href="#" target="_blank" rel="noopener noreferrer">
                <Github size={18} />
              </SocialLink>
              <SocialLink href="#" target="_blank" rel="noopener noreferrer">
                <Mail size={18} />
              </SocialLink>
            </FooterSocial>
          </FooterBottom>
        </FooterContent>
      </Footer>
    </LandingWrapper>
  );
};

export default LandingPage;
