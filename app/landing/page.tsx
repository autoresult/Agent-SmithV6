'use client';

import Script from 'next/script';
import { HeroSection } from '@/components/HeroSection';

export default function LandingPage() {
  return (
    <>
      <HeroSection />
      <Script
        id="mw"
        src="https://smith-v2-theta.vercel.app/widget.js"
        strategy="afterInteractive"
        onLoad={() => {
          // @ts-ignore
          window.mw && window.mw('init', { agentId: '67449923-b499-4f7a-a706-02a90accb54d' });
        }}
      />
    </>
  );
}
