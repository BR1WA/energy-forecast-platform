import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const outputPath = "C:/Users/salah/Documents/MASTER/PFE2/data/history_test_1year.csv";
const previewPath = "C:/Users/salah/Documents/MASTER/PFE2/csv_builder/history_test_1year_preview.png";
const headers = ["timestamp", "active_power_kw", "voltage_v", "current_a"];

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

const rows = [headers];
const start = new Date("2025-07-24T00:00:00Z");

for (let index = 0; index < 365 * 24; index += 1) {
  const timestamp = new Date(start.getTime() + index * 60 * 60 * 1000);
  const hour = timestamp.getUTCHours();
  const day = timestamp.getUTCDay();
  const weekend = day === 0 || day === 6;
  const morningPeak = Math.max(0, 1 - Math.abs(hour - 8) / 3);
  const eveningPeak = Math.max(0, 1 - Math.abs(hour - 19) / 4);
  const daytimeLoad = hour >= 9 && hour <= 17 ? 0.55 : 0.2;
  const seasonal = 0.12 * Math.sin((2 * Math.PI * index) / (24 * 365));
  const variation = 0.08 * Math.sin(index * 0.73);
  const weekendAdjustment = weekend ? -0.18 : 0;
  const activePower = round(Math.max(
    0.42,
    0.72 + seasonal + daytimeLoad + morningPeak * 1.65 + eveningPeak * 1.95 + weekendAdjustment + variation,
  ));
  const voltage = round(231.5 + 2.2 * Math.sin(index * 0.41) + (weekend ? 0.7 : 0), 1);
  const current = round((activePower * 1000) / voltage, 2);
  rows.push([timestamp.toISOString().replace(".000Z", "+00:00"), activePower, voltage, current]);
}

const csvText = `${rows.map((row) => row.join(",")).join("\n")}\n`;
await fs.writeFile(outputPath, csvText, "utf8");

const workbook = await Workbook.fromCSV(csvText, { sheetName: "History" });
const inspection = await workbook.inspect({
  kind: "table",
  range: "History!A1:D8761",
  include: "values",
  tableMaxRows: 3,
  tableMaxCols: 4,
});
console.log(inspection.ndjson);
const preview = await workbook.render({ sheetName: "History", range: "A1:D12", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
console.log(`Generated ${rows.length - 1} data rows at ${outputPath}`);
