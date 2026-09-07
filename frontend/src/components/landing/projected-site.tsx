import { useId } from 'react';
import styles from './landing.module.css';

type Point = [number, number, number];
// Project the same site coordinates into SVG when a renderer flattens CSS depth.
function project([x, y, z]: Point) {
  const turn = -34 * Math.PI / 180;
  const tilt = 58 * Math.PI / 180;
  const rx = (x - 180) * Math.cos(turn) - (y - 180) * Math.sin(turn);
  const ry = (x - 180) * Math.sin(turn) + (y - 180) * Math.cos(turn);
  return `${(260 + rx).toFixed(2)},${(250 + ry * Math.cos(tilt) - z * Math.sin(tilt)).toFixed(2)}`;
}
const polygon = (points: Point[]) => points.map(project).join(' ');
const line = (points: Point[]) => `M${points.map(project).join('L')}`;

function SolarPanel({ x, y, width, depth, z }: { x: number; y: number; width: number; depth: number; z: number }) {
  return <g stroke="#8abed8" strokeWidth=".7"><polygon fill="#173e69" points={polygon([[x, y, z], [x + width, y, z], [x + width, y + depth, z], [x, y + depth, z]])} />{Array.from({ length: 4 }, (_, i) => <path key={i} fill="none" d={line([[x, y + depth * (i + 1) / 5, z], [x + width, y + depth * (i + 1) / 5, z]])} />)}<path fill="none" d={line([[x + width / 2, y, z], [x + width / 2, y + depth, z]])} /></g>;
}

function Building({ x, y, width, depth, height, windows = false }: { x: number; y: number; width: number; depth: number; height: number; windows?: boolean }) {
  return <g stroke="#4f83ad" strokeWidth=".8">
    <polygon fill="#1c4068" points={polygon([[x, y, 0], [x, y + depth, 0], [x, y + depth, height], [x, y, height]])} />
    <polygon fill="#32618f" points={polygon([[x, y + depth, 0], [x + width, y + depth, 0], [x + width, y + depth, height], [x, y + depth, height]])} />
    {windows && Array.from({ length: 5 }, (_, row) => Array.from({ length: 5 }, (_, column) => {
      const z = 6 + row * 22;
      const dx = x + 5 + column * 20;
      const dy = y + 4 + column * 18;
      return <g key={`${row}-${column}`} stroke="#163252" strokeWidth="2"><polygon fill="#8abedf" points={polygon([[dx, y + depth, z], [dx + 15, y + depth, z], [dx + 15, y + depth, z + 16], [dx, y + depth, z + 16]])} /><polygon fill="#4d83ae" points={polygon([[x, dy, z], [x, dy + 13, z], [x, dy + 13, z + 16], [x, dy, z + 16]])} /></g>;
    }))}
    <polygon fill="#52799f" points={polygon([[x, y, height], [x + width, y, height], [x + width, y + depth, height], [x, y + depth, height]])} />
    <polygon fill="none" stroke="#a9c5df" points={polygon([[x + 4, y + 4, height], [x + width - 4, y + 4, height], [x + width - 4, y + depth - 4, height], [x + 4, y + depth - 4, height]])} />
  </g>;
}

export function ProjectedSite() {
  const id = useId();
  const routes: Point[][] = [
    [[0, 265, 1], [100, 265, 1], [100, 230, 1], [180, 230, 1], [180, 160, 1], [300, 160, 1], [300, 0, 1]],
    [[0, 120, 1], [65, 120, 1], [65, 160, 1], [180, 160, 1]],
    [[180, 360, 1], [180, 270, 1], [290, 270, 1], [290, 160, 1], [360, 160, 1]],
  ];
  return <svg className={styles.projectedSite} viewBox="0 0 520 440" aria-hidden="true" data-testid="projected-site">
    <defs><radialGradient id={`${id}-tree`} cx="30%" cy="30%"><stop stopColor="#8fd0ee" /><stop offset="1" stopColor="#2f6794" /></radialGradient></defs>
    <polygon fill="#091629" stroke="#35689a" strokeWidth="2" points={polygon([[0, 0, -10], [360, 0, -10], [360, 360, -10], [0, 360, -10]])} />
    <polygon fill="#0e1d35" stroke="#6c99c0" points={polygon([[0, 0, 0], [360, 0, 0], [360, 360, 0], [0, 360, 0]])} />
    <g stroke="#60a5fa17" fill="none">{Array.from({ length: 11 }, (_, i) => <path key={i} d={`${line([[(i + 1) * 30, 0, 0], [(i + 1) * 30, 360, 0]])}${line([[0, (i + 1) * 30, 0], [360, (i + 1) * 30, 0]])}`} />)}</g>
    <g fill="none" stroke="#3ea4df55" strokeWidth="2">{routes.map((points, i) => <g key={i}><path d={line(points)} /><path className={styles.energyPulse} d={line(points)} /></g>)}</g>
    {[0, 1, 2].map((i) => <SolarPanel key={i} x={28 + i * 27} y={54} width={22} depth={52} z={7} />)}
    {[0, 1, 2].map((i) => { const [cx, cy] = project([320, 50 + i * 39, 12]).split(','); return <ellipse key={i} cx={cx} cy={cy} rx="12" ry="7" fill={`url(#${id}-tree)`} />; })}
    <Building x={115} y={86} width={105} depth={94} height={116} windows />
    <SolarPanel x={132} y={100} width={65} depth={36} z={117} />
    <Building x={112} y={180} width={103} depth={76} height={55} />
    <SolarPanel x={121} y={189} width={85} depth={58} z={56} />
    <Building x={264} y={215} width={37} depth={43} height={42} />
    <path fill="none" stroke="#7dd3fc" strokeWidth="2" d={line([[283, 226, 43], [275, 237, 43], [287, 237, 43], [280, 247, 43]])} />
    {[[65, 120, 1], [290, 270, 1], [100, 265, 1]].map((point, i) => { const [cx, cy] = project(point as Point).split(','); return <ellipse key={i} cx={cx} cy={cy} rx="4" ry="2.5" fill="#7dd3fc" stroke="#7dd3fc33" strokeWidth="5" />; })}
  </svg>;
}
