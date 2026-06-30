'use client';

import React from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function ConsumptionPage() {
  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Consumption</h1>
          <p className="text-slate-400">View current and historical consumption data.</p>
        </div>

        <Card className="bg-[#111827] border-white/10">
          <CardHeader>
            <CardTitle className="text-white">Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-slate-400">Coming soon...</div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
