'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowRight, ArrowUpRight, Check, Database, Fingerprint, Layers3, Pause, Play, Radio, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { authApi } from '@/lib/api';
import { EnergyScene } from '@/components/landing/energy-scene';
import styles from '@/components/landing/landing.module.css';

const workflows = [
  { icon: Database, number: '01', title: 'Connect the source.', text: 'Import a validated CSV, connect authenticated push readings, or explore the explicitly labelled simulator.', detail: 'Your meter. Your records.' },
  { icon: Radio, number: '02', title: 'See the whole picture.', text: 'Move from live consumption to long-term patterns, with tariff cost, data source, and freshness in view.', detail: 'From live to all history.' },
  { icon: Sparkles, number: '03', title: 'Make your next move.', text: 'Review high-load and missing-data incidents, then use rule-based recommendations grounded in your readings.', detail: 'Evidence before action.' },
];
const horizons = [
  { label: '24 hours', value: '24', unit: 'hourly targets', model: 'Global TFT', text: 'A closer look at the day ahead.', gate: '336 hours of history', bars: [28, 24, 22, 26, 36, 55, 72, 60, 48, 42, 40, 44, 52, 48, 44, 52, 68, 90, 82, 70, 58, 44, 36, 30] },
  { label: '7 days', value: '168', unit: 'hourly targets', model: 'Global TFT', text: 'A wider perspective on the week.', gate: '336 hours of history', bars: [38, 54, 70, 46, 36, 52, 66, 44, 32, 48, 62, 42, 38, 60, 84, 56, 34, 50, 74, 46, 32, 44, 62, 40] },
  { label: '30 days', value: '30', unit: 'daily targets', model: 'Chronos-2 LoRA', text: 'Longer-term planning. Daily resolution.', gate: 'At least 270 daily blocks', bars: [40, 48, 44, 52, 62, 56, 46, 50, 58, 66, 60, 52, 56, 64, 74, 68, 60, 62, 72, 82, 76, 68, 74, 80] },
];

export default function ProductLandingPage() {
  const { isAuthenticated } = useAuth();
  const [registrationAvailable, setRegistrationAvailable] = useState<boolean | null>(null);
  const [paused, setPaused] = useState(false);
  const [horizonIndex, setHorizonIndex] = useState(0);
  const rootRef = useRef<HTMLElement>(null);
  const horizon = horizons[horizonIndex];
  useEffect(() => {
    if (isAuthenticated) return;
    let active = true;
    authApi.getCapabilities()
      .then((capabilities) => { if (active) setRegistrationAvailable(capabilities.email_delivery_enabled); })
      .catch(() => { if (active) setRegistrationAvailable(false); });
    return () => { active = false; };
  }, [isAuthenticated]);
  useEffect(() => {
    const root = rootRef.current;
    if (!root || !('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.setAttribute('data-visible', 'true'); observer.unobserve(entry.target); }
      });
    }, { threshold: 0.12 });
    root.querySelectorAll('[data-reveal]').forEach((element) => observer.observe(element));
    root.dataset.enhanced = 'true';
    return () => { observer.disconnect(); delete root.dataset.enhanced; };
  }, []);
  const primaryHref = isAuthenticated ? '/dashboard' : registrationAvailable ? '/register' : '/login';
  const primaryLabel = isAuthenticated ? 'Open dashboard' : registrationAvailable ? 'Create account' : 'Sign in';
  return (
    <main ref={rootRef} className={styles.landing} data-paused={paused}>
      <a href="#overview" className={styles.skipLink} tabIndex={0}>Skip to content</a>
      <header className={styles.header}>
        <Link href="/" className={styles.brand} aria-label="EnergyAI home"><span className={styles.brandMark}><Zap size={20} fill="currentColor" /></span>EnergyAI</Link>
        <nav className={styles.navigation} aria-label="Main navigation"><a href="#workflow">How it works</a><a href="#forecasts">Forecasting</a></nav>
        <div className={styles.headerActions}>{!isAuthenticated && registrationAvailable && <Link href="/login" className={styles.textCta}>Sign in</Link>}<Link href={primaryHref} className={styles.headerCta}>{primaryLabel}<ArrowUpRight size={16} /></Link></div>
      </header>
      <section id="overview" className={styles.hero} aria-labelledby="hero-title">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}><span className={styles.statusDot} /> ENERGY INTELLIGENCE, IN FOCUS</p>
          <h1 id="hero-title">Your energy.<br />A clearer<br /><span>perspective.</span></h1>
          <p className={styles.heroDescription}>Make sense of every kilowatt-hour. Monitor your electricity, uncover patterns, and look ahead with machine-learning forecasts.</p>
          <div className={styles.heroActions}><Link href={primaryHref} className={styles.primaryCta}>{primaryLabel}<ArrowUpRight size={19} /></Link><a href="#workflow" className={styles.textCta}>Explore the platform<ArrowDown size={16} /></a></div>
          {!isAuthenticated && registrationAvailable === false ? <p className={styles.accessNote}>Public registration is currently unavailable. Existing verified users can sign in; contact support if you need access.</p> : null}
          <div className={styles.heroFootnote}><Fingerprint size={18} /><span>One private site. A complete energy story.</span></div>
        </div>
        <div className={styles.heroVisual}>
          <div className={styles.sceneHeading}><span>THE CONNECTED SITE</span><span>FIG. 01 / ENERGY FLOW</span></div>
          <EnergyScene paused={paused} />
          <div className={styles.sceneFooter}><span>Conceptual illustration · not live data</span><button type="button" className={styles.motionToggle} onClick={() => setPaused(!paused)} aria-pressed={paused} aria-label={paused ? 'Resume decorative motion' : 'Pause decorative motion'}>{paused ? <Play size={13} /> : <Pause size={13} />}<span>{paused ? 'Resume' : 'Pause'} motion</span></button></div>
        </div>
        <div className={styles.heroBottom}><span>BUILT AROUND YOUR METER</span><a href="#workflow">Scroll to discover <ArrowDown size={14} /></a><span>MONITOR / FORECAST / ACT</span></div>
      </section>
      <div className={styles.capabilityStrip} aria-label="Platform capabilities"><span><Radio size={17} />Electricity monitoring</span><span><Layers3 size={17} />Multi-horizon forecasts</span><span><ShieldCheck size={17} />Account-scoped records</span></div>
      <section id="workflow" className={styles.section} aria-labelledby="workflow-title">
        <div className={styles.sectionHeading} data-reveal><p className={styles.eyebrow}>01 / FROM READINGS TO REASONING</p><div><h2 id="workflow-title">Less guesswork.<br /><span>More understanding.</span></h2><p>One connected workflow. Every chart, incident, forecast, and export traces back to your persisted meter records.</p></div></div>
        <div className={styles.workflowGrid}>{workflows.map(({ icon: Icon, number, title, text, detail }) => <article className={styles.workflowCard} key={number} data-reveal><div className={styles.cardTop}><Icon size={24} strokeWidth={1.4} /><span>{number}</span></div><h3>{title}</h3><p>{text}</p><div className={styles.cardDetail}><span>{detail}</span><ArrowUpRight size={17} /></div></article>)}</div>
      </section>
      <section id="forecasts" className={`${styles.section} ${styles.forecastSection}`} aria-labelledby="forecast-title">
        <div className={styles.forecastCopy} data-reveal><p className={styles.eyebrow}>02 / A VIEW OF WHAT COMES NEXT</p><h2 id="forecast-title">Look ahead.<br /><span>Know the limits.</span></h2><p>Different horizons need different models. Explore the forecast contracts, with explicit history requirements and transparent provenance.</p><div className={styles.modelNote}><Layers3 size={20} /><p>Versioned Global TFT artifacts for hourly forecasts. A separately gated Chronos-2 LoRA artifact for daily forecasts. Seasonal fallback is always labelled.</p></div><Link href={primaryHref} className={styles.textCta}>Explore your forecasts<ArrowUpRight size={17} /></Link></div>
        <div className={styles.forecastPanel} data-reveal>
          <div className={styles.panelHeading}><span>FORECAST EXPLORER</span><span className={styles.exampleBadge}>ILLUSTRATIVE</span></div>
          <div className={styles.horizonSwitch} role="group" aria-label="Forecast horizon">{horizons.map((item, index) => <button key={item.label} type="button" aria-pressed={index === horizonIndex} onClick={() => setHorizonIndex(index)}>{item.label}</button>)}</div>
          <div className={styles.forecastDetails} aria-live="polite"><div><strong>{horizon.value}</strong><span>{horizon.unit}</span></div><span className={styles.modelTag}>{horizon.model}</span></div>
          <div className={styles.barChart} aria-hidden="true">{horizon.bars.map((height, index) => <span key={index} style={{ height: `${height}%`, transitionDelay: `${index * 12}ms` }} />)}</div>
          <div className={styles.chartCaption}><span>{horizon.text}</span><span>→</span></div>
          <p className={styles.chartDisclaimer}>Illustrative pattern, not a prediction or measured consumption.</p>
          <div className={styles.readiness}><span><Check size={14} />{horizon.gate}</span><span><Check size={14} />≥95% observed coverage</span><span><Check size={14} />Finite energy values in kWh</span></div>
          {horizonIndex === 2 && <p className={styles.dailyNote}>30 daily targets — not a 720-step hourly forecast.</p>}
        </div>
      </section>
      <section className={`${styles.section} ${styles.closing}`} data-reveal aria-labelledby="closing-title"><div className={styles.closingOrb} aria-hidden="true"><Zap size={42} strokeWidth={1} /></div><p className={styles.eyebrow}>YOUR RECORDS. YOUR PERSPECTIVE.</p><h2 id="closing-title">See your energy<br />in a <span>new light.</span></h2><p>{isAuthenticated ? 'Your private workspace brings your readings, forecasts, and actions together.' : registrationAvailable ? 'Start with your timezone and tariff. Then connect your primary meter and build a picture from your own records.' : 'Your private energy workspace is ready for existing verified users.'}</p><Link href={primaryHref} className={styles.primaryCta}>{primaryLabel}<ArrowRight size={18} /></Link></section>
      <footer className={styles.footer}><Link href="/" className={styles.brand}><Zap size={19} />EnergyAI</Link><span>Master&apos;s PFE · Electricity monitoring & forecasting</span><a href="#overview">Back to top ↑</a></footer>
    </main>
  );
}
