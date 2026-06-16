'use client';

import React, { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { AlertCircle, RotateCcw, Home } from 'lucide-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Next.js Global Error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#0A0F1C] text-slate-200 px-4">
      <div className="max-w-md w-full text-center space-y-6 p-8 rounded-3xl border border-white/[0.06] bg-[#111827]/40 backdrop-blur-xl">
        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-500/10 text-red-400">
          <AlertCircle className="h-8 w-8" />
        </div>
        
        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-white">Something went wrong</h2>
          <p className="text-sm text-slate-400">
            An unexpected error occurred while loading this page. Please try resetting the view or return to the dashboard.
          </p>
        </div>

        {error.message && (
          <div className="text-left bg-black/40 border border-white/[0.04] p-4 rounded-xl max-h-36 overflow-auto text-xs font-mono text-slate-400">
            <span className="text-red-400 font-bold">Error:</span> {error.message}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Button
            onClick={() => reset()}
            className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-5 rounded-xl flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Try Again
          </Button>
          <Button
            onClick={() => window.location.href = '/dashboard'}
            variant="outline"
            className="flex-1 border-white/10 hover:bg-white/[0.04] text-slate-300 font-semibold py-5 rounded-xl flex items-center justify-center gap-2"
          >
            <Home className="w-4 h-4" />
            Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
}
