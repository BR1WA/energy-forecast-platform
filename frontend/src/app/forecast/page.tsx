'use client';

import React, { useState, useCallback, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useI18n } from '@/lib/i18n';
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
import { useAuth } from '@/lib/auth';

// Icon and color mapping for models
const modelMeta: Record<string, { icon: typeof Brain; color: string }> = {
  patchtst: { icon: Sparkles, color: '#10B981' },
  sota: { icon: Cpu, color: '#06B6D4' },
  cnn_bilstm: { icon: Brain, color: '#3B82F6' },
  patchtst_168: { icon: Sparkles, color: '#10B981' },
  itransformer_168: { icon: Cpu, color: '#8B5CF6' },
  patchtst_720: { icon: Sparkles, color: '#10B981' },
  itransformer_720: { icon: Cpu, color: '#F59E0B' },
};

// Real training metrics for deterministic display
const trainingMetrics: Record<string, { mae: string; rmse: string; mape: string; r2_score: string }> = {
  patchtst: { mae: '0.4519 kW', rmse: '0.6445 kW', mape: '55.97%', r2_score: '0.8142' },
  sota: { mae: '0.4614 kW', rmse: '0.6623 kW', mape: '55.13%', r2_score: '0.8407' },
  cnn_bilstm: { mae: '0.5335 kW', rmse: '0.7072 kW', mape: '77.36%', r2_score: '0.6914' },
  patchtst_168: { mae: '0.4320 kW', rmse: '0.6120 kW', mape: '51.20%', r2_score: '0.8250' },
  itransformer_168: { mae: '0.4210 kW', rmse: '0.6010 kW', mape: '49.80%', r2_score: '0.8320' },
  patchtst_720: { mae: '0.4850 kW', rmse: '0.6850 kW', mape: '58.70%', r2_score: '0.7840' },
  itransformer_720: { mae: '0.4680 kW', rmse: '0.6540 kW', mape: '56.20%', r2_score: '0.8050' },
};

interface ModelInfo {
  name: string;
  display_name: string;
  description: string;
  architecture_type: string;
  training_metrics?: { mae: number; rmse: number; mape: number; r2_score: number };
  is_active: boolean;
  parameters?: Record<string, string>;
}

interface SampleInfo {
  name: string;
  description: string;
  season: string;
  date_range: string;
}

const processForecastChartData = (
  horizon: number,
  inputData: number[] | undefined,
  predictionsOrModels: number[][] | Record<string, number[][]> | undefined,
  isComparison: boolean,
  modelsList: ModelInfo[],
  selectedModelName: string,
  createdAtStr?: string
) => {
  const chartData: Array<Record<string, any>> = [];
  const createdDate = createdAtStr ? new Date(createdAtStr) : new Date();
  
  if (!inputData || !Array.isArray(inputData)) return chartData;
  if (!predictionsOrModels) return chartData;

  const getModelDisplayName = (modelKey: string, h: number) => {
    return modelsList.find((m) => {
      const matchName = m.name === modelKey || m.name === `${modelKey}_${h}`;
      if (!matchName) return false;
      const hParam = m.parameters?.forecast_horizon;
      if (hParam) {
        if (hParam.includes(String(h)) || hParam.toLowerCase().includes(h === 168 ? 'week' : h === 720 ? 'month' : 'day')) return true;
      }
      if (h === 168 && m.name.endsWith('_168')) return true;
      if (h === 720 && m.name.endsWith('_720')) return true;
      if (h === 24 && !m.name.endsWith('_168') && !m.name.endsWith('_720')) return true;
      return false;
    })?.display_name || modelKey;
  };

  // Determine lookback based on horizon
  let lookback = 96;
  if (horizon === 168) lookback = 512;
  else if (horizon === 720) lookback = 1440;

  // Slice inputData to match the expected lookback just in case
  const slicedInput = inputData.slice(-lookback);

  if (horizon === 24) {
    // --- Day Horizon: Hourly view, keep last 24h of history + 24h prediction ---
    const historyToShow = slicedInput.slice(-24);
    
    // 1. Add historical hours
    for (let i = 0; i < historyToShow.length; i++) {
      const pointTime = new Date(createdDate.getTime() - (historyToShow.length - i) * 3600 * 1000);
      const timeLabel = pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      chartData.push({
        time: timeLabel,
        historical: Number(historyToShow[i].toFixed(3)),
      });
    }

    // Bridge point at H0
    const bridgeTimeLabel = createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const bridgePoint: Record<string, any> = {
      time: bridgeTimeLabel,
      historical: Number(historyToShow[historyToShow.length - 1].toFixed(3)),
    };

    if (isComparison) {
      const modelsData = predictionsOrModels as Record<string, number[][]>;
      for (const modelKey of Object.keys(modelsData)) {
        const mDisplayName = getModelDisplayName(modelKey, horizon);
        if (modelsData[modelKey] && modelsData[modelKey].length > 0) {
          bridgePoint[mDisplayName] = Number(modelsData[modelKey][0][0].toFixed(3));
        }
      }
    } else {
      const predictions = predictionsOrModels as number[][];
      const modelDisplayName = modelsList.find(m => m.name === selectedModelName)?.display_name || selectedModelName;
      if (predictions && predictions.length > 0) {
        bridgePoint[modelDisplayName] = Number(predictions[0][0].toFixed(3));
      }
    }
    chartData.push(bridgePoint);

    // 2. Add predictions
    if (isComparison) {
      const modelsData = predictionsOrModels as Record<string, number[][]>;
      const firstModel = Object.keys(modelsData)[0];
      const length = modelsData[firstModel]?.length || 0;
      for (let i = 0; i < length; i++) {
        const pointTime = new Date(createdDate.getTime() + (i + 1) * 3600 * 1000);
        const timeLabel = pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const rowData: Record<string, any> = { time: timeLabel };
        for (const modelKey of Object.keys(modelsData)) {
          const mDisplayName = getModelDisplayName(modelKey, horizon);
          if (modelsData[modelKey] && modelsData[modelKey][i]) {
            rowData[mDisplayName] = Number(modelsData[modelKey][i][0].toFixed(3));
          }
        }
        chartData.push(rowData);
      }
    } else {
      const predictions = predictionsOrModels as number[][];
      const modelDisplayName = modelsList.find(m => m.name === selectedModelName)?.display_name || selectedModelName;
      for (let i = 0; i < predictions.length; i++) {
        const pointTime = new Date(createdDate.getTime() + (i + 1) * 3600 * 1000);
        const timeLabel = pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        chartData.push({
          time: timeLabel,
          [modelDisplayName]: Number(predictions[i][0].toFixed(3)),
        });
      }
    }

  } else {
    // --- Week (168h) / Month (720h) Horizon: Daily aggregation view ---
    const historyHours = horizon === 168 ? 168 : 720;
    const historyToShow = slicedInput.slice(-historyHours);
    const numDays = horizon === 168 ? 7 : 30;

    const formatDateLabel = (d: Date) => {
      return d.toLocaleDateString([], { day: '2-digit', month: 'short' });
    };

    // 1. Add aggregated daily history
    for (let d = 0; d < numDays; d++) {
      const daySlice = historyToShow.slice(d * 24, (d + 1) * 24);
      if (daySlice.length === 0) continue;
      const dailySum = daySlice.reduce((a, b) => a + b, 0);
      const dayDate = new Date(createdDate.getTime() - (numDays - d) * 24 * 3600 * 1000);
      chartData.push({
        time: formatDateLabel(dayDate),
        historical: Number(dailySum.toFixed(2)),
      });
    }

    // Bridge point at Today (connect history end day to prediction start day)
    const lastDayHistorySlice = historyToShow.slice(-24);
    const lastDayHistorySum = lastDayHistorySlice.reduce((a, b) => a + b, 0);
    
    const bridgePoint: Record<string, any> = {
      time: formatDateLabel(createdDate),
      historical: Number(lastDayHistorySum.toFixed(2)),
    };

    if (isComparison) {
      const modelsData = predictionsOrModels as Record<string, number[][]>;
      for (const modelKey of Object.keys(modelsData)) {
        const mDisplayName = getModelDisplayName(modelKey, horizon);
        if (modelsData[modelKey]) {
          const dayPredictSlice = modelsData[modelKey].slice(0, 24);
          const dayPredictSum = dayPredictSlice.reduce((a, b) => a + b[0], 0);
          bridgePoint[mDisplayName] = Number(dayPredictSum.toFixed(2));
        }
      }
    } else {
      const predictions = predictionsOrModels as number[][];
      const modelDisplayName = modelsList.find(m => m.name === selectedModelName)?.display_name || selectedModelName;
      if (predictions) {
        const dayPredictSlice = predictions.slice(0, 24);
        const dayPredictSum = dayPredictSlice.reduce((a, b) => a + b[0], 0);
        bridgePoint[modelDisplayName] = Number(dayPredictSum.toFixed(2));
      }
    }
    chartData.push(bridgePoint);

    // 2. Add aggregated daily predictions
    for (let d = 0; d < numDays; d++) {
      const dayDate = new Date(createdDate.getTime() + (d + 1) * 24 * 3600 * 1000);
      const rowData: Record<string, any> = { time: formatDateLabel(dayDate) };

      if (isComparison) {
        const modelsData = predictionsOrModels as Record<string, number[][]>;
        for (const modelKey of Object.keys(modelsData)) {
          const mDisplayName = getModelDisplayName(modelKey, horizon);
          if (modelsData[modelKey]) {
            const dayPredictSlice = modelsData[modelKey].slice(d * 24, (d + 1) * 24);
            if (dayPredictSlice.length === 0) continue;
            const dayPredictSum = dayPredictSlice.reduce((a, b) => a + b[0], 0);
            rowData[mDisplayName] = Number(dayPredictSum.toFixed(2));
          }
        }
      } else {
        const predictions = predictionsOrModels as number[][];
        const modelDisplayName = modelsList.find(m => m.name === selectedModelName)?.display_name || selectedModelName;
        if (predictions) {
          const dayPredictSlice = predictions.slice(d * 24, (d + 1) * 24);
          if (dayPredictSlice.length === 0) continue;
          const dayPredictSum = dayPredictSlice.reduce((a, b) => a + b[0], 0);
          rowData[modelDisplayName] = Number(dayPredictSum.toFixed(2));
        }
      }
      chartData.push(rowData);
    }
  }

  return chartData;
};

export default function ForecastPage() {
  const { t, language } = useI18n();
  const { user } = useAuth();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [sampleDatasets, setSampleDatasets] = useState<SampleInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedSample, setSelectedSample] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [forecastData, setForecastData] = useState<Array<Record<string, unknown>> | null>(null);
  const [activeTab, setActiveTab] = useState('single');
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [useSmartMeter, setUseSmartMeter] = useState(false);
  const [inputMethod, setInputMethod] = useState<'upload' | 'sample' | 'meter'>('upload');
  const [selectedHorizon, setSelectedHorizon] = useState<number>(24);

  const getHorizonForModel = useCallback((model: ModelInfo): number => {
    const horizonParam = model.parameters?.forecast_horizon;
    if (horizonParam) {
      if (horizonParam.includes('168') || horizonParam.toLowerCase().includes('week')) return 168;
      if (horizonParam.includes('720') || horizonParam.toLowerCase().includes('month')) return 720;
      if (horizonParam.includes('24') || horizonParam.toLowerCase().includes('day')) return 24;
    }
    if (model.name.endsWith('_168')) return 168;
    if (model.name.endsWith('_720')) return 720;
    return 24;
  }, []);

  const getTickInterval = useCallback((dataLength: number, horizon: number): number => {
    if (horizon === 24) return 6; // Show ticks every 6 hours
    if (horizon === 168) return 1; // Show daily ticks since there are only 15 points
    if (horizon === 720) return 5; // Show ticks every 5 days
    return 6;
  }, []);

  // Update selectedModel when selectedHorizon or models change
  useEffect(() => {
    const filtered = models.filter(m => getHorizonForModel(m) === selectedHorizon);
    if (filtered.length > 0) {
      let preferredModelName = '';
      if (selectedHorizon === 24) preferredModelName = user?.preferences?.default_model_24 || 'sota';
      else if (selectedHorizon === 168) preferredModelName = user?.preferences?.default_model_168 || 'itransformer_168';
      else if (selectedHorizon === 720) preferredModelName = user?.preferences?.default_model_720 || 'itransformer_720';
      
      const hasPreferred = filtered.some(m => m.name === preferredModelName);
      if (hasPreferred) {
        setSelectedModel(preferredModelName);
      } else if (!filtered.some(m => m.name === selectedModel)) {
        setSelectedModel(filtered[0].name);
      }
    }
    setForecastData(null);
  }, [selectedHorizon, models, selectedModel, getHorizonForModel, user?.preferences]);



  // Fetch models and samples from API on mount
  useEffect(() => {
    forecastApi.getModels()
      .then((data) => {
        const parsed = data as unknown as ModelInfo[];
        setModels(parsed);
        if (parsed.length > 0) {
          const filtered = parsed.filter(m => getHorizonForModel(m) === selectedHorizon);
          let preferredModelName = '';
          if (selectedHorizon === 24) preferredModelName = user?.preferences?.default_model_24 || 'sota';
          else if (selectedHorizon === 168) preferredModelName = user?.preferences?.default_model_168 || 'itransformer_168';
          else if (selectedHorizon === 720) preferredModelName = user?.preferences?.default_model_720 || 'itransformer_720';
          
          const hasPreferred = filtered.some(m => m.name === preferredModelName);
          if (hasPreferred) {
            setSelectedModel(preferredModelName);
          } else if (filtered.length > 0) {
            setSelectedModel(filtered[0].name);
          } else {
            setSelectedModel(parsed[0].name);
          }
        }
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

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setUploadedFile(file);
      setSelectedSample('');
      setError('');
    }
  }, []);

  const handleRunForecast = async () => {
    if (!selectedModel) {
      setError('Please select a model');
      return;
    }
    if (!uploadedFile && !selectedSample && !useSmartMeter) {
      setError('Please upload data, select a sample dataset, or sync Smart Meter');
      return;
    }

    setError('');
    setIsRunning(true);

    try {
      if (activeTab === 'single') {
        const result = useSmartMeter
          ? await forecastApi.predictSmartMeter(selectedModel, selectedHorizon)
          : await forecastApi.predict(selectedModel, uploadedFile || selectedSample, selectedHorizon) as unknown as Record<string, unknown>;
        const predictions = result.predictions as number[][] | undefined;
        const inputData = result.input_data as number[] | undefined;
        const createdAt = result.created_at as string | undefined;
        
        if (predictions && Array.isArray(predictions)) {
          const chartData = processForecastChartData(
            selectedHorizon,
            inputData,
            predictions,
            false,
            models,
            selectedModel,
            createdAt
          );
          setForecastData(chartData);
        }
      } else {
        // Comparison mode
        const result = useSmartMeter
          ? await forecastApi.compareSmartMeter(selectedHorizon)
          : await forecastApi.compare(uploadedFile || selectedSample, selectedHorizon);
        const modelsData = result.models as Record<string, number[][]>;
        const inputData = result.input_data as number[] | undefined;
        const createdAt = result.created_at as string | undefined;
        
        if (modelsData && Object.keys(modelsData).length > 0) {
          const chartData = processForecastChartData(
            selectedHorizon,
            inputData,
            modelsData,
            true,
            models,
            selectedModel,
            createdAt
          );
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
            {t('forecast.title')}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {t('forecast.subtitle')}
          </p>
        </div>

        {/* Tabs: Single Model / Comparison */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <TabsList className="bg-white/[0.04] border border-white/[0.06] p-1 w-fit">
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
                Model Comparison
              </TabsTrigger>
            </TabsList>

            {/* Horizon Selector */}
            <div className="flex items-center gap-2 bg-white/[0.02] border border-white/[0.06] rounded-xl p-1.5 shrink-0">
              <span className="text-xs text-slate-400 px-2 font-medium">Forecast Horizon:</span>
              <div className="flex gap-1">
                {[
                  { label: '24 Hours', value: 24 },
                  { label: '1 Week', value: 168 },
                  { label: '1 Month', value: 720 },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedHorizon(opt.value)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      selectedHorizon === opt.value
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'text-slate-400 hover:text-white border border-transparent disabled:opacity-30 disabled:hover:text-slate-400'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

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
                {models
                  .filter((m) => getHorizonForModel(m) === selectedHorizon)
                  .map((model) => {
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
                        MAE: {model.training_metrics?.mae !== undefined ? model.training_metrics.mae.toFixed(3) : 'N/A'}
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
                {/* Input Method Switcher */}
                <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <button
                    onClick={() => {
                      setInputMethod('upload');
                      setUseSmartMeter(false);
                      setSelectedSample('');
                    }}
                    className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      inputMethod === 'upload'
                        ? 'bg-blue-500/15 text-blue-400'
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.02]'
                    }`}
                  >
                    Upload File
                  </button>
                  <button
                    onClick={() => {
                      setInputMethod('sample');
                      setUseSmartMeter(false);
                      setUploadedFile(null);
                    }}
                    className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      inputMethod === 'sample'
                        ? 'bg-blue-500/15 text-blue-400'
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.02]'
                    }`}
                  >
                    Samples
                  </button>
                  <button
                    onClick={() => {
                      setInputMethod('meter');
                      setUseSmartMeter(true);
                      setUploadedFile(null);
                      setSelectedSample('');
                    }}
                    className={`px-2 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      inputMethod === 'meter'
                        ? 'bg-blue-500/15 text-blue-400'
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.02]'
                    }`}
                  >
                    Smart Meter
                  </button>
                </div>

                {inputMethod === 'upload' && (
                  <div>
                    <label
                      htmlFor="file-upload"
                      onDragEnter={handleDrag}
                      onDragOver={handleDrag}
                      onDragLeave={handleDrag}
                      onDrop={handleDrop}
                      className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200 ${
                        isDragging
                          ? 'border-blue-500 bg-blue-500/10'
                          : 'border-white/[0.08] hover:border-blue-500/30 hover:bg-blue-500/5'
                      }`}
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
                )}

                {inputMethod === 'sample' && (
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
                )}

                {inputMethod === 'meter' && (
                  <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02] space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">Meter Provider</span>
                      <span className="text-xs font-semibold text-white">Enedis Linky</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">Meter Serial</span>
                      <span className="text-xs font-mono font-medium text-white">LNK-4829-1092</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-400">Connection</span>
                      <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Live Online
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 text-center border-t border-white/[0.04] pt-2">
                      Will fetch the last 96 hours of real-time electricity consumption readings.
                    </div>
                  </div>
                )}
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
                      {currentModel?.display_name || currentModel?.name || '—'}
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
                            interval={getTickInterval(forecastData.length, selectedHorizon)}
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
                            name={selectedHorizon === 24 ? "Historical (kW)" : "Historical (kWh)"}
                            connectNulls={false}
                          />
                          <Area
                            type="monotone"
                            dataKey={currentModel?.display_name || selectedModel}
                            stroke={modelMeta[selectedModel]?.color || '#10B981'}
                            strokeWidth={2}
                            strokeDasharray="5 3"
                            fill="url(#gradPredicted)"
                            name={selectedHorizon === 24 ? "Predicted (kW)" : "Predicted (kWh)"}
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
                    const dbMetrics = currentModel?.training_metrics;
                    const m = dbMetrics ? {
                      mae: `${dbMetrics.mae.toFixed(4)} kW`,
                      rmse: `${dbMetrics.rmse.toFixed(4)} kW`,
                      mape: `${dbMetrics.mape.toFixed(2)}%`,
                      r2_score: dbMetrics.r2_score.toFixed(4)
                    } : (trainingMetrics[selectedModel] || trainingMetrics.cnn_bilstm);
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
                        Model Comparison ({selectedHorizon}h Horizon)
                      </CardTitle>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-slate-400" />
                          <span className="text-slate-400">Historical</span>
                        </div>
                        {models.filter(m => getHorizonForModel(m) === selectedHorizon).map((m) => (
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
                            interval={getTickInterval(forecastData.length, selectedHorizon)}
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
                          {models.filter(m => getHorizonForModel(m) === selectedHorizon).map((m) => (
                            <Line
                              key={m.name}
                              type="monotone"
                              dataKey={m.display_name}
                              stroke={modelMeta[m.name]?.color || '#3B82F6'}
                              strokeWidth={2}
                              dot={false}
                              strokeDasharray={
                                !m.name.includes('cnn_bilstm') ? '5 3' : undefined
                              }
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Comparison Metrics Table */}
                <div className={models.filter(m => getHorizonForModel(m) === selectedHorizon).length === 2 
                  ? "grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl mx-auto" 
                  : "grid grid-cols-1 md:grid-cols-3 gap-4"
                }>
                  {models.filter(m => getHorizonForModel(m) === selectedHorizon).map((model) => {
                    const meta = modelMeta[model.name] || { icon: Brain, color: '#3B82F6' };
                    const Icon = meta.icon;
                    const dbMetrics = model.training_metrics;
                    const metrics = dbMetrics ? {
                      mae: `${dbMetrics.mae.toFixed(4)} kW`,
                      rmse: `${dbMetrics.rmse.toFixed(4)} kW`,
                      mape: `${dbMetrics.mape.toFixed(2)}%`,
                      r2_score: dbMetrics.r2_score.toFixed(4)
                    } : (trainingMetrics[model.name] || trainingMetrics.cnn_bilstm);
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
                  Processing your data through {currentModel?.display_name || currentModel?.name}...
                </p>
              </CardContent>
            </Card>
          )}
        </Tabs>
      </div>
    </AppLayout>
  );
}
