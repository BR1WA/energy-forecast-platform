'use client';

import { useEffect, useRef, type CSSProperties } from 'react';
import { Activity, Cpu, Zap } from 'lucide-react';
import styles from './landing.module.css';
import { ProjectedSite } from './projected-site';

/** A CSS 3D model: decorative only, with no meter or forecast requests. */
export function EnergyScene({ paused }: { paused: boolean }) {
  const sceneRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    // Some software renderers advertise preserve-3d but flatten child depth.
    // Test rendered geometry, not the user agent, and use a projected SVG there.
    const roof = scene.querySelector<HTMLElement>('[data-depth-probe]');
    if (roof) {
      const elevated = roof.getBoundingClientRect().top;
      roof.style.transform = 'translateZ(0)';
      const flat = roof.getBoundingClientRect().top;
      roof.style.removeProperty('transform');
      scene.dataset.flat = String(Math.abs(elevated - flat) < 1);
    }
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(pointer: fine)');
    let frame = 0;
    let visible = true;
    let pointerX = 0;
    let pointerY = 0;
    const render = () => {
      frame = 0;
      if (!visible || document.hidden) return;
      const still = paused || preference.matches;
      const progress = still ? 0 : Math.min(window.scrollY / Math.max(window.innerHeight, 1), 1.5);
      scene.style.setProperty('--scene-turn', `${-34 + progress * 22 + (still ? 0 : pointerX * 5)}deg`);
      scene.style.setProperty('--scene-tilt', `${58 + (still ? 0 : pointerY * 3) - progress * 6}deg`);
      scene.style.setProperty('--scene-rise', `${progress * -24}px`);
      scene.style.setProperty('--scene-sway', `${progress * 3 + (still ? 0 : pointerX * 2)}deg`);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(render); };
    const onPointer = (event: PointerEvent) => {
      if (!finePointer.matches || paused || preference.matches) return;
      const rect = scene.getBoundingClientRect();
      pointerX = (event.clientX - rect.left) / rect.width - 0.5;
      pointerY = (event.clientY - rect.top) / rect.height - 0.5;
      schedule();
    };
    const resetPointer = () => { pointerX = 0; pointerY = 0; schedule(); };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      scene.dataset.offscreen = String(!visible);
      if (visible) schedule();
    });
    observer.observe(scene);
    scene.addEventListener('pointermove', onPointer);
    scene.addEventListener('pointerleave', resetPointer);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    document.addEventListener('visibilitychange', schedule);
    preference.addEventListener('change', schedule);
    schedule();
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
      scene.removeEventListener('pointermove', onPointer);
      scene.removeEventListener('pointerleave', resetPointer);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      document.removeEventListener('visibilitychange', schedule);
      preference.removeEventListener('change', schedule);
    };
  }, [paused]);
  return (
    <div ref={sceneRef} className={styles.scene} aria-hidden="true" data-testid="energy-scene">
      <div className={styles.sceneHalo} /><div className={styles.orbitOne} /><div className={styles.orbitTwo} />
      <div className={styles.sceneModel}><div className={styles.platform}>
        <div className={styles.platformEdge} />
        <svg className={styles.energyPaths} viewBox="0 0 360 360"><path d="M0 265H100V230H180V160H300V0M0 120H65V160H180M180 360V270H290V160H360" /><path className={styles.energyPulse} d="M0 265H100V230H180V160H300V0M0 120H65V160H180M180 360V270H290V160H360" /><circle cx="180" cy="230" r="5" /><circle cx="290" cy="270" r="5" /><circle cx="65" cy="120" r="5" /></svg>
        <div className={`${styles.building} ${styles.mainBuilding}`} style={{ '--height': '116px' } as CSSProperties}><div className={styles.buildingFront} /><div className={styles.buildingSide} /><div className={styles.buildingRoof} data-depth-probe><span className={styles.roofMark}>E / 01</span><div className={styles.roofEquipment} /></div></div>
        <div className={`${styles.building} ${styles.annex}`} style={{ '--height': '55px' } as CSSProperties}><div className={styles.buildingFront} /><div className={styles.buildingSide} /><div className={styles.buildingRoof}><div className={styles.solarPanels} /></div></div>
        <div className={`${styles.building} ${styles.battery}`} style={{ '--height': '42px' } as CSSProperties}><div className={styles.buildingFront} /><div className={styles.buildingSide} /><div className={styles.buildingRoof}><Zap size={18} /></div></div>
        <div className={styles.groundPanels}><div /><div /><div /></div><div className={styles.siteLabel}>ENERGYAI / CONNECTED SITE</div><div className={styles.siteTrees}><i /><i /><i /></div>
      </div></div>
      <ProjectedSite />
      <div className={`${styles.sceneTag} ${styles.sourceTag}`}><span className={styles.tagIcon}><Zap size={15} /></span><div><small>01 / CONNECT</small><strong>Meter readings</strong></div><span className={styles.tagDot} /></div>
      <div className={`${styles.sceneTag} ${styles.forecastTag}`}><span className={styles.tagIcon}><Cpu size={15} /></span><div><small>02 / UNDERSTAND</small><strong>Forecast intelligence</strong></div></div>
      <div className={`${styles.sceneTag} ${styles.actionTag}`}><Activity size={14} /><span>Measure. Understand. Act.</span></div>
      <div className={styles.sceneCoordinates}>SINGLE SITE<br /><span>ISOMETRIC VIEW / 01</span></div>
    </div>
  );
}
