import React, { useEffect, useRef } from 'react';
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
  max-width: 1200px;
  width: min(calc(100% - clamp(24px, 6vw, 60px) * 2), 1200px);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.32), rgba(255, 255, 255, 0.08));
  backdrop-filter: blur(26px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.32);
  border-radius: 18px;
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
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0 60px;
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

const DotCanvas = styled.canvas`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
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
  color: #4b5563;
  line-height: 1.65;
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
  padding: 120px 60px;
  background: ${props => (props.$isDark ? '#f9fafb' : '#ffffff')};

  @media (max-width: 768px) {
    padding: 80px 24px;
  }
`;

const SectionHeader = styled.div`
  max-width: 800px;
  margin: 0 auto 80px;
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
  object-fit: cover;
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
  background: #f9fafb;
`;

const DemoContainer = styled.div`
  max-width: 1600px;
  margin: 0 auto;
`;

const DemoViewport = styled.div`
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08);
`;

const DemoToolbar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 30px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
`;

const ToolbarTitle = styled.div`
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  font-family: inherit;
  letter-spacing: -0.2px;
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

const DemoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  padding: 40px;
`;

const DemoCard = styled.div`
  padding: 24px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
`;

const DemoCardTitle = styled.div`
  font-size: 15px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 12px;
  font-family: inherit;
  letter-spacing: -0.3px;
`;

const DemoCardBody = styled.p`
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
  font-family: inherit;
  letter-spacing: -0.2px;
`;

const CTASection = styled(FullWidthSection)`
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d44 100%);
`;

const CTAContent = styled.div`
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
`;

const CTATitle = styled.h2`
  font-size: clamp(36px, 5vw, 56px);
  font-weight: 700;
  margin-bottom: 24px;
  color: white;
  font-family: 'Casual', 'Inter', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
  letter-spacing: -1.5px;
`;

const CTASubtitle = styled.p`
  font-size: 19px;
  color: rgba(255, 255, 255, 0.85);
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

const WhiteButton = styled(PrimaryButton)`
  background: white;
  color: #1a1a2e;

  &:hover {
    background: #f9fafb;
    box-shadow: 0 10px 30px rgba(255, 255, 255, 0.2);
  }
`;

const TransparentButton = styled(PrimaryButton)`
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.25);

  &:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.4);
  }
`;

const DotGrid: React.FC = () => {
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
    const spacing = 20;

    const resizeCanvas = () => {
      const { clientWidth, clientHeight } = canvas;
      const pixelRatio = window.devicePixelRatio || 1;

      canvas.width = clientWidth * pixelRatio;
      canvas.height = clientHeight * pixelRatio;
      ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

      dots.length = 0;
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
  }, []);

  return <DotCanvas ref={canvasRef} />;
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
    description: 'Coordinated AI specialists handle code generation, research analysis, content creation, and presentation design simultaneously.'
  },
  {
    icon: <Layers size={28} />,
    title: 'Unified Knowledge Layer',
    description: 'Every artifact, decision, and insight flows through a synchronized context engine that keeps all agents aligned.'
  },
  {
    icon: <ShieldCheck size={28} />,
    title: 'Enterprise-Grade Security',
    description: 'End-to-end encryption, audit trails, and compliance controls ensure your data stays protected at every layer.'
  },
  {
    icon: <Zap size={28} />,
    title: 'Real-Time Execution',
    description: 'Watch your workflows come to life with live status updates, progress tracking, and instant artifact generation.'
  },
  {
    icon: <Globe size={28} />,
    title: 'Global Infrastructure',
    description: 'Deploy across multiple regions with automatic failover and edge optimization for lightning-fast performance.'
  },
  {
    icon: <Lock size={28} />,
    title: 'Access Control',
    description: 'Granular permissions, role-based access, and team management built for organizations of any size.'
  }
];

const demoHighlights = [
  {
    title: 'Artifact Timeline',
    body: 'Track every generated asset—code, documents, visualizations—with full version history and instant rollback capabilities.'
  },
  {
    title: 'Live Execution Monitor',
    body: 'Observe agent activities in real-time with detailed logs, performance metrics, and resource utilization insights.'
  },
  {
    title: 'Collaborative Workspace',
    body: 'Review, approve, and refine agent outputs with contextual feedback loops and team annotation tools.'
  }
];

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { addNewChat, activeChat } = useChat();
  const featuresRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
          }
        });
      },
      { threshold: 0.2 }
    );

    const featureRows = featuresRef.current?.querySelectorAll('[data-feature-row]');
    featureRows?.forEach((row) => observer.observe(row));

    return () => observer.disconnect();
  }, []);


  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  const frameCount = 226; // The total number of image frames
  const SCROLL_MULTIPLIER = 3; // try 2–5


  useEffect(() => {
    const canvas = canvasRef.current;
    const sectionEl = sectionRef.current;
    if (!canvas || !sectionEl) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // --- helpers: find actual scroll container & relative offsets ---
    const isScrollable = (el: Element) => {
      const s = getComputedStyle(el);
      return /(auto|scroll)/.test(s.overflowY) || /(auto|scroll)/.test(s.overflow);
    };
    const getScrollParent = (el: Element | null): HTMLElement | null => {
      let p = el?.parentElement || null;
      while (p && p !== document.body && p !== document.documentElement) {
        if (isScrollable(p)) return p as HTMLElement;
        p = p.parentElement;
      }
      // if body/html are the scroller, return null (means window)
      return null;
    };
    const getOffsetTopWithin = (el: HTMLElement, root: HTMLElement): number => {
      let y = 0;
      let n: HTMLElement | null = el;
      while (n && n !== root) {
        y += n.offsetTop;
        n = n.offsetParent as HTMLElement | null;
      }
      return y;
    };

    // find the real scroller (null => window)
    const scrollerEl = getScrollParent(sectionEl);
    const useWindow = !scrollerEl;

    const dpr = window.devicePixelRatio || 1;
    const frame = { current: 0 };

    // base path safe URLs
    const base =
      (import.meta as any)?.env?.BASE_URL ||
      (typeof process !== 'undefined' ? (process as any).env?.PUBLIC_URL : '') ||
      '';
    const urlFor = (n: number) => `${base}/frames/frame_${String(n).padStart(4, '0')}.jpg`;

    // preload images
    const images: HTMLImageElement[] = new Array(frameCount);
    const loadImages = () =>
      Promise.all(
        Array.from({ length: frameCount }, (_, i) => {
          const img = new Image();
          const url = urlFor(i + 1);
          images[i] = img;
          return new Promise<void>((resolve) => {
            img.onload = () => resolve();
            img.onerror = () => {
              console.warn('[frames] failed to load:', url);
              resolve();
            };
            img.src = url;
          });
        })
      );

    const sizeCanvas = () => {
      const cssW = canvas.clientWidth || 1920;
      const cssH = canvas.clientHeight || 1080;
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      const idx = Math.floor(frame.current);
      const img = images[idx];
      if (!img || !img.complete || !img.naturalWidth) return;
      const w = canvas.clientWidth || 1920;
      const h = canvas.clientHeight || 1080;
      ctx.clearRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
    };

    // manual progress relative to the real scroller
    const manualProgress = () => {
      if (useWindow) {
        const rect = sectionEl.getBoundingClientRect();
        const vh = window.innerHeight;
        const total = (rect.height - vh) * SCROLL_MULTIPLIER; if (total <= 0) return 0;
        // how far the viewport top is past the section top
        const passed = -rect.top; // negative until section top crosses viewport top
        const p = Math.min(Math.max(passed / total, 0), 1);
        return p;
      } else {
        const vh = scrollerEl!.clientHeight;
        const sectionTop = getOffsetTopWithin(sectionEl, scrollerEl!);
        const scrollTop = scrollerEl!.scrollTop;
        const rel = scrollTop - sectionTop; // <0 before reaching the section
        const total = (sectionEl.offsetHeight - vh) * SCROLL_MULTIPLIER;
        if (total <= 0) return 0;
        const p = Math.min(Math.max(rel / total, 0), 1);
        return p;
      }
    };

    // clean slate
    ScrollTrigger.getAll().forEach(t => t.kill());
    sizeCanvas();

    loadImages().then(() => {
      // draw first available
      let first = 0;
      for (let i = 0; i < frameCount; i++) {
        if (images[i]?.complete && images[i].naturalWidth) { first = i; break; }
      }
      frame.current = first;
      draw();

      // ScrollTrigger (now pointing at the correct scroller)
      const stCfg: any = {
        trigger: sectionEl,
        start: 'top top',
        end: () =>
          '+=' + ((useWindow ? window.innerHeight : scrollerEl!.clientHeight) * SCROLL_MULTIPLIER * 2), // longer distance
        scrub: true,
        // markers: true,
        onUpdate: (self: ScrollTrigger) => {
          const idx = Math.min(frameCount - 1, Math.floor(self.progress * (frameCount - 1)));
          if (idx !== frame.current) { frame.current = idx; draw(); }
        },
      };
      if (!useWindow) stCfg.scroller = scrollerEl;
      ScrollTrigger.create(stCfg);

      // manual fallback (also drives frames; harmless to run alongside ST)
      const onScroll = () => {
        const p = manualProgress();
        const idx = Math.min(frameCount - 1, Math.floor(p * (frameCount - 1)));
        if (idx !== frame.current) {
          frame.current = idx;
          draw();
        }
      };

      const scrollTarget: any = useWindow ? window : scrollerEl!;
      scrollTarget.addEventListener('scroll', onScroll, { passive: true });

      const onResize = () => {
        sizeCanvas();
        draw();
        ScrollTrigger.refresh();
        onScroll();
      };
      window.addEventListener('resize', onResize);

      // initial sync
      ScrollTrigger.refresh();
      onScroll();

      return () => {
        ScrollTrigger.getAll().forEach(t => t.kill());
        scrollTarget.removeEventListener('scroll', onScroll);
        window.removeEventListener('resize', onResize);
      };
    });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);



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
          <BrandMark>AI</BrandMark>
          ArrowAI Studio
        </NavBrand>
        <NavLinks>
          <NavLink onClick={() => scrollToSection('features')}>Features</NavLink>
          <NavLink onClick={() => scrollToSection('demo')}>Demo</NavLink>
          <NavLink onClick={() => scrollToSection('cta')}>Contact</NavLink>
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
        <DotGrid />
        <DotCanvasOverlay />
        <HeroContent>
          <Badge>
            <Sparkles size={14} />
            Auditable AI Platform
          </Badge>
          <HeroTitle>
            AI you can trust, prove, and replay.
          </HeroTitle>
          <HeroSubtitle>
            The trust layer for intelligent systems — recording every reasoning step, dataset, and output so decisions are explainable, defensible and most importantly, auditable.
          </HeroSubtitle>
          <HeroButtons>
            <PrimaryButton onClick={launchWorkspace}>
              Get Started
              <ArrowRight size={20} />
            </PrimaryButton>
            <OutlineButton onClick={() => scrollToSection('demo')}>
              Live Demo
              <Play size={20} />
            </OutlineButton>
          </HeroButtons>
        </HeroContent>
      </HeroSection>

      <VideoFeaturesSection ref={sectionRef} id="features">
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
      </VideoFeaturesSection>

      <DemoSection id="demo">
        <SectionHeader>
          <SectionTitle>See It In Action</SectionTitle>
          <SectionSubtitle>
            Experience the ArrowAI platform with our interactive workspace demonstration.
          </SectionSubtitle>
        </SectionHeader>
        <DemoContainer>
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
        </DemoContainer>
      </DemoSection>

      <CTASection id="cta">
        <CTAContent>
          <CTAButtons>
            <WhiteButton onClick={launchWorkspace}>
              Get Started Free
              <ArrowRight size={18} />
            </WhiteButton>
            <TransparentButton onClick={goToDashboard}>
              Schedule Demo
              <MessageSquare size={18} />
            </TransparentButton>
          </CTAButtons>
        </CTAContent>
      </CTASection>
    </LandingWrapper>
  );
};

export default LandingPage;
