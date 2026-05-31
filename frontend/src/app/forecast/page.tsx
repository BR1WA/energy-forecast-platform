'use client';

import React, { useState, useCallback } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  LineChart as LineChartIcon,
  Upload,
  Database,
  Play,
  Download,
  Layers,
  Brain,
  Cpu,
  Sparkles,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  Legend,
} from 'recharts';

// Demo models
const models = [
  {
    id: 'cnn-bilstm',
    name: 'CNN-BiLSTM',
    description: 'Convolutional + Bidirectional LSTM hybrid architecture',
    accuracy: 96.2,
    icon: Brain,
    color: '#3B82F6',
  },
  {
    id: 'sota-hybrid',
    name: 'SOTA Hybrid',
    description: 'State-of-the-art ensemble hybrid model',
    accuracy: 95.8,
    icon: Cpu,
    color: '#06B6D4',
  },
  {
    id: 'patchtst',
    name: 'PatchTST',
    description: 'Patch Time Series Transformer model',
    accuracy: 97.1,
    icon: Sparkles,
    color: '#10B981',
  },
];

// Demo forecast data
const generateForecastData = () => {
  const data = [];
  const base = new Date(2025, 0, 1);
  for (let i = 0; i < 168; i++) {
    const date = new Date(base.getTime() + i * 3600000);
    const hour = date.getHours();
    const dayFactor = Math.sin((hour - 6) * (Math.PI / 12)) * 0.5 + 0.5;
    const noise = () => (Math.random() - 0.5) * 200;
    const actual = 2500 + dayFactor * 3000 + noise();
    data.push({
      time: `${String(Math.floor(i / 24) + 1).padStart(2, '0')}d ${String(
        hour
      ).padStart(2, '0')}h`,
      actual: Math.round(actual),
      'CNN-BiLSTM': Math.round(actual + noise() * 0.5),
      'SOTA Hybrid': Math.round(actual + noise() * 0.6),
      PatchTST: Math.round(actual + noise() * 0.4),
    });
  }
  return data;
};

const sampleDatasets = [
  {
    id: 'household-daily',
    name: 'Household Daily',
    rows: 1460,
    description: '4 years daily household consumption',
  },
  {
    id: 'household-hourly',
    name: 'Household Hourly',
    rows: 8760,
    description: '1 year hourly readings',
  },
  {
    id: 'industrial',
    name: 'Industrial Plant',
    rows: 4380,
    description: '6 months 30-min intervals',
  },
];

export default function ForecastPage() {
  const [selectedModel, setSelectedModel] = useState('cnn-bilstm');
  const [selectedSample, setSelectedSample] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [forecastData, setForecastData] = useState<ReturnType<typeof generateForecastData> | null>(null);
  const [activeTab, setActiveTab] = useState('single');
  const [error, setError] = useState('');

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setUploadedFile(file);
        setSelectedSample('');
        setError('');
      }
    },
    []
  );

  const handleRunForecast = async () => {
    if (!selectedModel) {
      setError('Please select a model');
      return;
    }
    if (!uploadedFile && !selectedSample) {
      setError('Please upload data or select a sample dataset');
      return;
    }

    setError('');
    setIsRunning(true);

    // Simulate API call
    await new Promise((r) => setTimeout(r, 2500));
    setForecastData(generateForecastData());
    setIsRunning(false);
  };

  const currentModel = models.find((m) => m.id === selectedModel);

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <LineChartIcon className="w-6 h-6 text-blue-400" />
            Energy Forecaster
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Run predictive models and analyze forecast results
          </p>
        </div>

        {/* Tabs: Single Model / Comparison */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <TabsList className="bg-white/[0.04] border border-white/[0.06] p-1">
            <TabsTrigger
              id="tab-single"
              value="single"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              <LineChartIcon className="w-4 h-4 mr-2" />
              Single Model
            </TabsTrigger>
            <TabsTrigger
              id="tab-comparison"
              value="comparison"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              <Layers className="w-4 h-4 mr-2" />
              3-Way Comparison
            </TabsTrigger>
          </TabsList>

          {/* Configuration Panel */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Model Selection */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-white flex items-center gap-2">
                  <Brain className="w-4 h-4 text-blue-400" />
                  Select Model
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {models.map((model) => (
                  <button
                    key={model.id}
                    id={`model-${model.id}`}
                    onClick={() => setSelectedModel(model.id)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all duration-200 text-left ${
                      selectedModel === model.id
                        ? 'border-blue-500/30 bg-blue-500/10'
                        : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]'
                    }`}
                  >
                    <div
                      className="flex items-center justify-center w-9 h-9 rounded-lg"
                      style={{ backgroundColor: `${model.color}20` }}
                    >
                      <model.icon
                        className="w-4 h-4"
                        style={{ color: model.color }}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white">
                        {model.name}
                      </p>
                      <p className="text-xs text-slate-500 truncate">
                        {model.description}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[10px] shrink-0"
                    >
                      {model.accuracy}%
                    </Badge>
                  </button>
                ))}
              </CardContent>
            </Card>

            {/* Data Input */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  Data Source
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* File Upload */}
                <div>
                  <label
                    htmlFor="file-upload"
                    className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-white/[0.08] rounded-xl cursor-pointer hover:border-blue-500/30 hover:bg-blue-500/5 transition-all duration-200"
                  >
                    <Upload className="w-8 h-8 text-slate-500 mb-2" />
                    <p className="text-sm font-medium text-white">
                      {uploadedFile ? uploadedFile.name : 'Upload CSV / JSON'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Drag & drop or click to browse
                    </p>
                  </label>
                  <input
                    id="file-upload"
                    type="file"
                    accept=".csv,.json"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex-1 h-px bg-white/[0.06]" />
                  <span className="text-xs text-slate-500">or</span>
                  <div className="flex-1 h-px bg-white/[0.06]" />
                </div>

                {/* Sample Dataset */}
                <Select
                  value={selectedSample}
                  onValueChange={(v) => {
                    setSelectedSample(v ?? '');
                    setUploadedFile(null);
                    setError('');
                  }}
                >
                  <SelectTrigger
                    id="sample-dataset-select"
                    className="bg-white/[0.04] border-white/[0.08] text-white"
                  >
                    <SelectValue placeholder="Choose sample dataset" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#111827] border-white/10">
                    {sampleDatasets.map((ds) => (
                      <SelectItem
                        key={ds.id}
                        value={ds.id}
                        className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
                      >
                        <div>
                          <span className="font-medium">{ds.name}</span>
                          <span className="text-xs text-slate-500 ml-2">
                            ({ds.rows.toLocaleString()} rows)
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            {/* Run Controls */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-white flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  Run Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Summary */}
                <div className="space-y-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Model</span>
                    <span className="text-white font-medium">
                      {currentModel?.name || '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Data</span>
                    <span className="text-white font-medium">
                      {uploadedFile
                        ? uploadedFile.name
                        : selectedSample
                        ? sampleDatasets.find((d) => d.id === selectedSample)
                            ?.name
                        : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Mode</span>
                    <span className="text-white font-medium">
                      {activeTab === 'single'
                        ? 'Single Model'
                        : '3-Way Compare'}
                    </span>
                  </div>
                </div>

                {error && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
                    <AlertCircle className="w-3 h-3 shrink-0" />
                    {error}
                  </div>
                )}

                <Button
                  id="run-forecast-btn"
                  onClick={handleRunForecast}
                  disabled={isRunning}
                  className="w-full h-11 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white font-medium shadow-lg shadow-blue-500/20 transition-all duration-300"
                >
                  {isRunning ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Running Forecast...
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Play className="w-4 h-4" />
                      Run Forecast
                    </div>
                  )}
                </Button>

                {forecastData && (
                  <Button
                    id="download-results"
                    variant="outline"
                    className="w-full border-white/[0.08] text-slate-300 hover:text-white hover:bg-white/[0.04]"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download Results
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Results */}
          {forecastData && (
            <>
              <TabsContent value="single" className="space-y-6 mt-0">
                {/* Single Model Chart */}
                <Card className="glass-card border-white/[0.06]">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base font-semibold text-white">
                        Forecast Results — {currentModel?.name}
                      </CardTitle>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-blue-500" />
                          <span className="text-slate-400">Actual</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{
                              backgroundColor: currentModel?.color || '#3B82F6',
                            }}
                          />
                          <span className="text-slate-400">Predicted</span>
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[400px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={forecastData.slice(0, 48)}>
                          <defs>
                            <linearGradient
                              id="gradActual"
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop
                                offset="0%"
                                stopColor="#3B82F6"
                                stopOpacity={0.2}
                              />
                              <stop
                                offset="100%"
                                stopColor="#3B82F6"
                                stopOpacity={0}
                              />
                            </linearGradient>
                          </defs>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(59,130,246,0.06)"
                            vertical={false}
                          />
                          <XAxis
                            dataKey="time"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748B', fontSize: 11 }}
                            interval={5}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748B', fontSize: 11 }}
                            width={50}
                          />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#111827',
                              border: '1px solid rgba(59,130,246,0.15)',
                              borderRadius: '12px',
                              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                              color: '#E2E8F0',
                              fontSize: '13px',
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="actual"
                            stroke="#3B82F6"
                            strokeWidth={2}
                            fill="url(#gradActual)"
                            name="Actual"
                          />
                          <Line
                            type="monotone"
                            dataKey={currentModel?.name || 'CNN-BiLSTM'}
                            stroke={currentModel?.color || '#3B82F6'}
                            strokeWidth={2}
                            strokeDasharray="5 3"
                            dot={false}
                            name="Predicted"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: 'MAE', value: '142.3 Wh', color: 'blue' },
                    { label: 'RMSE', value: '198.7 Wh', color: 'cyan' },
                    { label: 'MAPE', value: '3.8%', color: 'emerald' },
                    { label: 'R² Score', value: '0.962', color: 'violet' },
                  ].map((metric) => (
                    <Card
                      key={metric.label}
                      id={`metric-${metric.label.toLowerCase()}`}
                      className="glass-card border-white/[0.06]"
                    >
                      <CardContent className="p-4 text-center">
                        <p className="text-xs text-slate-400 uppercase tracking-wider">
                          {metric.label}
                        </p>
                        <p className="text-xl font-bold text-white mt-1">
                          {metric.value}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="comparison" className="space-y-6 mt-0">
                {/* Comparison Chart */}
                <Card className="glass-card border-white/[0.06]">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base font-semibold text-white">
                        3-Way Model Comparison
                      </CardTitle>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-slate-400" />
                          <span className="text-slate-400">Actual</span>
                        </div>
                        {models.map((m) => (
                          <div
                            key={m.id}
                            className="flex items-center gap-1.5"
                          >
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: m.color }}
                            />
                            <span className="text-slate-400">{m.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[400px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={forecastData.slice(0, 48)}>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(59,130,246,0.06)"
                            vertical={false}
                          />
                          <XAxis
                            dataKey="time"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748B', fontSize: 11 }}
                            interval={5}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748B', fontSize: 11 }}
                            width={50}
                          />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#111827',
                              border: '1px solid rgba(59,130,246,0.15)',
                              borderRadius: '12px',
                              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                              color: '#E2E8F0',
                              fontSize: '13px',
                            }}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="actual"
                            stroke="#94A3B8"
                            strokeWidth={2}
                            dot={false}
                            name="Actual"
                          />
                          {models.map((m) => (
                            <Line
                              key={m.id}
                              type="monotone"
                              dataKey={m.name}
                              stroke={m.color}
                              strokeWidth={2}
                              dot={false}
                              strokeDasharray={
                                m.id !== 'cnn-bilstm' ? '5 3' : undefined
                              }
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Comparison Metrics Table */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {models.map((model) => (
                    <Card
                      key={model.id}
                      className="glass-card border-white/[0.06]"
                    >
                      <CardContent className="p-5">
                        <div className="flex items-center gap-3 mb-4">
                          <div
                            className="w-9 h-9 rounded-lg flex items-center justify-center"
                            style={{ backgroundColor: `${model.color}20` }}
                          >
                            <model.icon
                              className="w-4 h-4"
                              style={{ color: model.color }}
                            />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {model.name}
                            </p>
                            <p className="text-xs text-slate-500">
                              Accuracy: {model.accuracy}%
                            </p>
                          </div>
                        </div>
                        <div className="space-y-2">
                          {[
                            { label: 'MAE', value: `${(130 + Math.random() * 40).toFixed(1)} Wh` },
                            { label: 'RMSE', value: `${(180 + Math.random() * 40).toFixed(1)} Wh` },
                            { label: 'MAPE', value: `${(3 + Math.random() * 2).toFixed(1)}%` },
                          ].map((m) => (
                            <div
                              key={m.label}
                              className="flex justify-between text-sm"
                            >
                              <span className="text-slate-400">{m.label}</span>
                              <span className="text-white font-medium">
                                {m.value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>
            </>
          )}

          {/* Empty State */}
          {!forecastData && !isRunning && (
            <Card className="glass-card border-white/[0.06]">
              <CardContent className="flex flex-col items-center justify-center py-20">
                <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center mb-4">
                  <LineChartIcon className="w-8 h-8 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-1">
                  No forecast results yet
                </h3>
                <p className="text-sm text-slate-400 text-center max-w-md">
                  Select a model, choose your data source, and click
                  &quot;Run Forecast&quot; to see predictions.
                </p>
              </CardContent>
            </Card>
          )}

          {/* Loading State */}
          {isRunning && (
            <Card className="glass-card border-white/[0.06]">
              <CardContent className="flex flex-col items-center justify-center py-20">
                <div className="relative w-16 h-16 mb-4">
                  <div className="absolute inset-0 rounded-full border-2 border-blue-500/20" />
                  <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" />
                  <div className="absolute inset-2 rounded-full border-2 border-transparent border-t-cyan-400 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
                </div>
                <h3 className="text-lg font-semibold text-white mb-1">
                  Running Forecast
                </h3>
                <p className="text-sm text-slate-400">
                  Processing your data through {currentModel?.name}...
                </p>
              </CardContent>
            </Card>
          )}
        </Tabs>
      </div>
    </AppLayout>
  );
}
