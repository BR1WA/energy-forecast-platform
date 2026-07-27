export const dynamic = 'force-dynamic';

function hourlyLoad(index: number) {
  const hour = index % 24;
  const morning = Math.exp(-Math.pow((hour - 8) / 2.2, 2)) * 0.55;
  const evening = Math.exp(-Math.pow((hour - 20) / 2.8, 2)) * 0.9;
  const dailyVariation = Math.sin((index / 24) * Math.PI * 2 / 7) * 0.08;
  return Math.max(0.25, 0.48 + morning + evening + dailyVariation);
}

export async function GET() {
  const now = new Date();
  const origin = new Date(now);
  origin.setUTCMinutes(0, 0, 0);
  const start = new Date(origin.getTime() - 336 * 60 * 60 * 1000);
  const rows = ['timestamp,active_power_kw,voltage_v,current_a'];

  for (let index = 0; index <= 336; index += 1) {
    const timestamp = new Date(start.getTime() + index * 60 * 60 * 1000);
    const activePower = hourlyLoad(index);
    const voltage = 230 + Math.sin(index / 9) * 2.4;
    const current = activePower * 1000 / voltage;
    rows.push(`${timestamp.toISOString()},${activePower.toFixed(3)},${voltage.toFixed(1)},${current.toFixed(2)}`);
  }

  return new Response(`${rows.join('\n')}\n`, {
    headers: {
      'Cache-Control': 'no-store',
      'Content-Disposition': 'attachment; filename="energyai-forecast-ready-14-days.csv"',
      'Content-Type': 'text/csv; charset=utf-8',
    },
  });
}
