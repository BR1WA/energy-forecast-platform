'use client';

import React, { useState, useCallback, useEffect } from 'react';
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

import { forecastApi } from '@/lib/api';
import { toast } from 'sonner';

// Icon and color mapping for models
const modelMeta: Record<string, { icon: typeof Brain; color: string }> = {
  patchtst: { icon: Sparkles, color: '#10B981' },
  sota: { icon: Cpu, color: '#06B6D4' },
  cnn_bilstm: { icon: Brain, color: '#3B82F6' },
};

// Real training metrics for deterministic display
const trainingMetrics: Record<string, { mae: string; rmse: string; mape: string; r2_score: string }> = {
  patchtst: { mae: '0.4519 kW', rmse: '0.6445 kW', mape: '55.97%', r2_score: '0.8142' },
  sota: { mae: '0.4614 kW', rmse: '0.6623 kW', mape: '55.13%', r2_score: '0.8407' },
  cnn_bilstm: { mae: '0.5335 kW', rmse: '0.7072 kW', mape: '77.36%', r2_score: '0.6914' },
};

interface ModelInfo {
  name: string;
  display_name: string;
  description: string;
  architecture_type: string;
  training_metrics: { mae: number; rmse: number; mape: number; r2_score: number };
  is_active: boolean;
}

interface SampleInfo {
  name: string;
  description: string;
  season: string;
  date_range: string;
}

export default function ForecastPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [sampleDatasets, setSampleDatasets] = useState<SampleInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedSample, setSelectedSample] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [forecastData, setForecastData] = useState<Array<Record<string, unknown>> | null>(null);
  const [activeTab, setActiveTab] = useState('single');
  const [error, setError] = useState('');

  // Fetch models and samples from API on mount
  useEffect(() => {
    forecastApi.getModels()
      .then((data) => {
        const parsed = data as unknown as ModelInfo[];
        setModels(parsed);
        if (parsed.length > 0) setSelectedModel(parsed[0].name);
      })
      .catch(() => {});

    forecastApi.getSamples()
      .then((data) => setSampleDatasets(data as unknown as SampleInfo[]))
      .catch(() => {});
  }, []);

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

    try {
      if (activeTab === 'single') {
        const result = await forecastApi.predict(selectedModel, uploadedFile || selectedSample) as unknown as Record<string, unknown>;
        const predictions = result.predictions as number[][] | undefined;
        const inputData = result.input_data as number[] | undefined;
        
        if (predictions && Array.isArray(predictions)) {
          const chartData: Array<Record<string, unknown>> = [];
          const modelDisplayName = currentModel?.display_name || selectedModel;
          
          // Show full lookback window of real historical data
          if (inputData && Array.isArray(inputData)) {
            for (let i = 0; i < inputData.length; i++) {
              chartData.push({
                time: `H-${inputData.length - i}`,
                historical: Number(inputData[i].toFixed(3)),
              });
            }
            // Bridge point at H0: connects historical end to prediction start
            chartData.push({
              time: 'H',
              historical: Number(inputData[inputData.length - 1].toFixed(3)),
              [modelDisplayName]: Number(predictions[0][0].toFixed(3)),
            });
          }
          
          // Then append the 24h predictions
          for (let i = 0; i < predictions.length; i++) {
            chartData.push({
              time: `H+${i + 1}`,
              [modelDisplayName]: Number(predictions[i][0].toFixed(3)),
            });
          }
          
          setForecastData(chartData);
        }
      } else {
        // Comparison mode
        const result = await forecastApi.compare(uploadedFile || selectedSample);
        const modelsData = result.models as Record<string, number[][]>;
        const inputData = result.input_data as number[] | undefined;
        
        if (modelsData && Object.keys(modelsData).length > 0) {
          const firstModel = Object.keys(modelsData)[0];
          const length = modelsData[firstModel].length;
          const chartData: Array<Record<string, unknown>> = [];
          
          // Show full lookback window of real historical data
          if (inputData && Array.isArray(inputData)) {
            for (let i = 0; i < inputData.length; i++) {
              chartData.push({
                time: `H-${inputData.length - i}`,
                historical: Number(inputData[i].toFixed(3)),
              });
            }
            // Bridge point at H0
            const bridgePoint: Record<string, unknown> = {
              time: 'H',
              historical: Number(inputData[inputData.length - 1].toFixed(3)),
            };
            for (const modelKey of Object.keys(modelsData)) {
              const mDisplayName = models.find(m => m.name === modelKey)?.display_name || modelKey;
              bridgePoint[mDisplayName] = Number(modelsData[modelKey][0][0].toFixed(3));
            }
            chartData.push(bridgePoint);
          }
          
          // Then append predictions from each model
          for (let i = 0; i < length; i++) {
            const rowData: Record<string, unknown> = { time: `H+${i + 1}` };
            
            for (const modelKey of Object.keys(modelsData)) {
              const mDisplayName = models.find(m => m.name === modelKey)?.display_name || modelKey;
              rowData[mDisplayName] = Number(modelsData[modelKey][i][0].toFixed(3));
            }
            chartData.push(rowData);
          }
          setForecastData(chartData);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prediction failed. Check your data format.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleDownloadCSV = () => {
    if (!forecastData || forecastData.length === 0) return;
    
    try {
      const keys = Object.keys(forecastData[0]);
      const headers = keys.join(',');
      const rows = forecastData.map(row => 
        keys.map(k => JSON.stringify(row[k] ?? '')).join(',')
      );
      
      const csvContent = [headers, ...rows].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      
      const modelName = currentModel?.display_name || selectedModel;
      link.setAttribute('download', `forecast_${modelName.toLowerCase().replace(/\s+/g, '_')}_results.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success('Forecast results CSV downloaded successfully');
    } catch (e) {
      console.error(e);
      toast.error('Failed to download CSV results');
    }
  };

  const currentModel = models.find((m) => m.name === selectedModel);

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
                {models.map((model) => {
                  const meta = modelMeta[model.name] || { icon: Brain, color: '#3B82F6' };
                  const Icon = meta.icon;
                  return (
                    <button
                      key={model.name}
                      id={`model-${model.name}`}
                      onClick={() => setSelectedModel(model.name)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all duration-200 text-left ${
                        selectedModel === model.name
                          ? 'border-blue-500/30 bg-blue-500/10'
                          : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]'
                      }`}
                    >
                      <div
                        className="flex items-center justify-center w-9 h-9 rounded-lg"
                        style={{ backgroundColor: `${meta.color}20` }}
                      >
                        <Icon
                          className="w-4 h-4"
                          style={{ color: meta.color }}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white">
                          {model.display_name}
                        </p>
                        <p className="text-xs text-slate-500 truncate">
                          {model.description}
                        </p>
                      </div>
                      <Badge
                        variant="outline"
                        className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[10px] shrink-0"
                      >
                        MAE: {model.training_metrics.mae.toFixed(3)}
                      </Badge>
                    </button>
                  );
                })}
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
                        key={ds.name}
                        value={ds.name}
                        className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
                      >
                        <div>
                          <span className="font-medium">{ds.name.replace(/_/g, ' ')}</span>
                          <span className="text-xs text-slate-500 ml-2">
                            ({ds.season} — {ds.date_range})
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
                        ? selectedSample.replace(/_/g, ' ')
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
                    onClick={handleDownloadCSV}
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
                        Forecast Results — {currentModel?.display_name || selectedModel}
                      </CardTitle>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-blue-500" />
                          <span className="text-slate-400">Historical (kW)</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{
                              backgroundColor: modelMeta[selectedModel]?.color || '#3B82F6',
                            }}
                          />
                          <span className="text-slate-400">Predicted (kW)</span>
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[400px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={forecastData}>
                          <defs>
                            <linearGradient
                              id="gradHistorical"
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
                            <linearGradient
                              id="gradPredicted"
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop
                                offset="0%"
                                stopColor={modelMeta[selectedModel]?.color || '#10B981'}
                                stopOpacity={0.15}
                              />
                              <stop
                                offset="100%"
                                stopColor={modelMeta[selectedModel]?.color || '#10B981'}
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
                            dataKey="historical"
                            stroke="#3B82F6"
                            strokeWidth={2}
                            fill="url(#gradHistorical)"
                            name="Historical (kW)"
                            connectNulls={false}
                          />
                          <Area
                            type="monotone"
                            dataKey={currentModel?.display_name || selectedModel}
                            stroke={modelMeta[selectedModel]?.color || '#10B981'}
                            strokeWidth={2}
                            strokeDasharray="5 3"
                            fill="url(#gradPredicted)"
                            name="Predicted (kW)"
                            connectNulls={false}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {(() => {
                    const m = trainingMetrics[selectedModel] || trainingMetrics.cnn_bilstm;
                    return [
                      { label: 'MAE', value: m.mae },
                      { label: 'RMSE', value: m.rmse },
                      { label: 'MAPE', value: m.mape },
                      { label: 'R²', value: m.r2_score },
                    ];
                  })().map((metric) => (
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
                          <span className="text-slate-400">Historical</span>
                        </div>
                        {models.map((m) => (
                          <div
                            key={m.name}
                            className="flex items-center gap-1.5"
                          >
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: modelMeta[m.name]?.color || '#3B82F6' }}
                            />
                            <span className="text-slate-400">{m.display_name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[400px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={forecastData}>
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
                            dataKey="historical"
                            stroke="#94A3B8"
                            strokeWidth={2}
                            dot={false}
                            name="Historical"
                          />
                          {models.map((m) => (
                            <Line
                              key={m.name}
                              type="monotone"
                              dataKey={m.display_name}
                              stroke={modelMeta[m.name]?.color || '#3B82F6'}
                              strokeWidth={2}
                              dot={false}
                              strokeDasharray={
                                m.name !== 'cnn_bilstm' ? '5 3' : undefined
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
                  {models.map((model) => {
                    const meta = modelMeta[model.name] || { icon: Brain, color: '#3B82F6' };
                    const Icon = meta.icon;
                    const metrics = trainingMetrics[model.name] || trainingMetrics.cnn_bilstm;
                    return (
                      <Card
                        key={model.name}
                        className="glass-card border-white/[0.06]"
                      >
                        <CardContent className="p-5">
                          <div className="flex items-center gap-3 mb-4">
                            <div
                              className="w-9 h-9 rounded-lg flex items-center justify-center"
                              style={{ backgroundColor: `${meta.color}20` }}
                            >
                              <Icon
                                className="w-4 h-4"
                                style={{ color: meta.color }}
                              />
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-white">
                                {model.display_name}
                              </p>
                              <p className="text-xs text-slate-500">
                                {model.architecture_type}
                              </p>
                            </div>
                          </div>
                          <div className="space-y-2">
                            {[
                              { label: 'MAE', value: metrics.mae },
                              { label: 'RMSE', value: metrics.rmse },
                              { label: 'MAPE', value: metrics.mape },
                              { label: 'R²', value: metrics.r2_score },
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
                    );
                  })}
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
