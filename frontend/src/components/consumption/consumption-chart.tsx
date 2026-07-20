'use client';

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ConsumptionPeriodSummary } from '@/types';

function formatTick(value: string, timeframe: ConsumptionPeriodSummary['timeframe']) {
  const date = new Date(value);
  if (timeframe === 'live' || timeframe === 'today') {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  if (timeframe === 'year' || timeframe === 'all') {
    return date.toLocaleDateString([], { month: 'short', year: '2-digit' });
  }
  return date.toLocaleDateString([], { day: '2-digit', month: 'short' });
}

export function ConsumptionChart({ summary }: { summary: ConsumptionPeriodSummary }) {
  const data = summary.points.map((point) => ({
    ...point,
    label: formatTick(point.timestamp, summary.timeframe),
  }));

  return (
    <div className="h-80 w-full min-w-0">
      <ResponsiveContainer height="100%" width="100%">
        <AreaChart data={data} margin={{ bottom: 0, left: -16, right: 12, top: 10 }}>
          <defs>
            <linearGradient id="measuredPower" x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" fontSize={11} minTickGap={28} stroke="#64748b" tickLine={false} />
          <YAxis fontSize={11} stroke="#64748b" tickLine={false} unit=" kW" width={52} />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 8 }}
            formatter={(value) => [`${Number(value).toFixed(3)} kW`, 'Average load']}
            labelFormatter={(_, payload) => payload[0]?.payload?.timestamp
              ? new Date(payload[0].payload.timestamp).toLocaleString()
              : ''}
          />
          <Area
            dataKey="average_kw"
            dot={false}
            fill="url(#measuredPower)"
            isAnimationActive={false}
            name="Average load"
            stroke="#22d3ee"
            strokeWidth={2}
            type="monotone"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
