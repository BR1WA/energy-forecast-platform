import Link from 'next/link';


export function PolicyLinks({ className = '' }: { className?: string }) {
  return (
    <nav aria-label="Legal and support" className={`flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500 ${className}`}>
      <Link className="hover:text-slate-300" href="/privacy">Privacy</Link>
      <Link className="hover:text-slate-300" href="/terms">Terms</Link>
      <Link className="hover:text-slate-300" href="/support">Support</Link>
    </nav>
  );
}
