from __future__ import annotations

import argparse
import copy
import gc
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--model', type=str, required=True)
parser.add_argument('--task', type=str, required=True)
parser.add_argument('--gpu', type=int, required=True)
parser.add_argument('--seed', type=int, default=2026)
parser.add_argument('--epochs', type=int, default=15)
parser.add_argument('--patience', type=int, default=5)
parser.add_argument('--batch-size', type=int, default=128)
parser.add_argument('--workers', type=int, default=2)
parser.add_argument('--samples-per-household', type=int, default=48)
parser.add_argument('--eval-origins', type=int, default=24)
parser.add_argument('--localize-nbeats', action='store_true')
parser.add_argument('--localization-epochs', type=int, default=2)
args = parser.parse_args()

os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

ROOT = args.root
DATA_DIR = ROOT / 'data'
RUN_DIR = ROOT / 'runs' / args.model / args.task
RUN_DIR.mkdir(parents=True, exist_ok=True)
METRICS_PATH = RUN_DIR / 'metrics.json'
CHECKPOINT_PATH = RUN_DIR / 'best.pt'
HISTORY_PATH = RUN_DIR / 'history.json'
SAMPLE_PATH = RUN_DIR / 'prediction_sample.npz'

DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
AMP_ENABLED = DEVICE.type == 'cuda'

TASKS = {
    'day_24h': dict(resolution='hourly', lookback=336, horizon=24, seasonal_period=168, cycle_period=24, cycle_context_radius=2),
    'week_168h': dict(resolution='hourly', lookback=336, horizon=168, seasonal_period=168, cycle_period=168, cycle_context_radius=3),
    'month_30d': dict(resolution='daily', lookback=90, horizon=30, seasonal_period=7, cycle_period=7, cycle_context_radius=1),
}
TASK = TASKS[args.task]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


seed_everything(args.seed)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True


def atomic_json(path: Path, payload) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False))
    temporary.replace(path)


def load_bundle():
    resolution = TASK['resolution']
    values = np.load(DATA_DIR / f'{resolution}_raw.npy', mmap_mode='r')
    calendar = np.load(DATA_DIR / f'{resolution}_calendar.npy', mmap_mode='r')
    scaler_file = np.load(DATA_DIR / f'{resolution}_scalers.npz')
    scalers = {name: scaler_file[name].astype(np.float32) for name in ['mean', 'std', 'min', 'max']}
    metadata = json.loads((DATA_DIR / 'prepared.json').read_text())
    prefix = 'hourly' if resolution == 'hourly' else 'daily'
    return {
        'values': values,
        'calendar': calendar,
        'scalers': scalers,
        'train_end': int(metadata[f'{prefix}_train_end']),
        'val_end': int(metadata[f'{prefix}_val_end']),
        'test_end': int(values.shape[1]),
        'known': np.load(DATA_DIR / 'known_households.npy'),
        'cold': np.load(DATA_DIR / 'cold_households.npy'),
        'clusters': np.load(DATA_DIR / 'cluster_labels.npy'),
    }


BUNDLE = load_bundle()
NORMALIZATION = 'minmax' if args.model == 'multicyclenet_adapted' else 'zscore'


def normalize(array, house_index):
    array = np.asarray(array, dtype=np.float32)
    scalers = BUNDLE['scalers']
    if NORMALIZATION == 'minmax':
        return (array - scalers['min'][house_index]) / (scalers['max'][house_index] - scalers['min'][house_index])
    return (array - scalers['mean'][house_index]) / scalers['std'][house_index]


def inverse_normalize(array, house_indices):
    array = np.asarray(array, dtype=np.float64)
    house_indices = np.asarray(house_indices, dtype=np.int64)
    scalers = BUNDLE['scalers']
    if NORMALIZATION == 'minmax':
        minimum = scalers['min'][house_indices][:, None]
        span = (scalers['max'][house_indices] - scalers['min'][house_indices])[:, None]
        return array * span + minimum
    mean = scalers['mean'][house_indices][:, None]
    std = scalers['std'][house_indices][:, None]
    return array * std + mean


def cycle_requirement():
    period = TASK['cycle_period']
    radius = TASK['cycle_context_radius']
    horizon = TASK['horizon']
    max_min_cycle = math.ceil((horizon - 1 + radius + 1) / period)
    return (max_min_cycle + 8) * period + radius


def build_cycle_tensor(values, origin):
    period = TASK['cycle_period']
    radius = TASK['cycle_context_radius']
    horizon = TASK['horizon']
    tensor = np.empty((horizon, 9, 2 * radius + 1), dtype=np.float32)
    for future_step in range(horizon):
        minimum_cycle = max(1, math.ceil((future_step + radius + 1) / period))
        for cycle_slot in range(9):
            center = origin + future_step - (minimum_cycle + cycle_slot) * period
            start = center - radius
            end = center + radius + 1
            if start < 0 or end > origin:
                return None
            tensor[future_step, cycle_slot] = values[start:end]
    return tensor


def baseline_forecast(raw_values, origin):
    horizon = TASK['horizon']
    period = TASK['seasonal_period']
    profile = raw_values[origin - period:origin]
    if len(profile) != period or not np.isfinite(profile).all():
        return None
    return profile[np.arange(horizon) % period].astype(np.float32)


def make_sample(house_index, origin):
    values = BUNDLE['values'][house_index]
    lookback = TASK['lookback']
    horizon = TASK['horizon']
    x_raw = np.asarray(values[origin - lookback:origin], dtype=np.float32)
    y_raw = np.asarray(values[origin:origin + horizon], dtype=np.float32)
    if not np.isfinite(x_raw).all() or not np.isfinite(y_raw).all():
        return None
    baseline = baseline_forecast(values, origin)
    if baseline is None:
        return None
    cycle_tensor = np.zeros((1, 1, 1), dtype=np.float32)
    if args.model == 'multicyclenet_adapted':
        cycle_raw = build_cycle_tensor(values, origin)
        if cycle_raw is None or not np.isfinite(cycle_raw).all():
            return None
        cycle_tensor = normalize(cycle_raw, house_index).astype(np.float32)
    x = normalize(x_raw, house_index).astype(np.float32)
    y = normalize(y_raw, house_index).astype(np.float32)
    # Calendar arrays come from a read-only memory map. Copy them before
    # torch.from_numpy so PyTorch never receives a non-writable array.
    x_calendar = np.array(
        BUNDLE['calendar'][origin - lookback:origin],
        dtype=np.float32,
        copy=True,
    )
    y_calendar = np.array(
        BUNDLE['calendar'][origin:origin + horizon],
        dtype=np.float32,
        copy=True,
    )
    return {
        'x': torch.from_numpy(x[:, None]),
        'y': torch.from_numpy(y),
        'x_calendar': torch.from_numpy(x_calendar),
        'y_calendar': torch.from_numpy(y_calendar),
        'cycle': torch.from_numpy(cycle_tensor),
        'house': torch.tensor(house_index, dtype=torch.long),
        'cluster': torch.tensor(int(BUNDLE['clusters'][house_index]), dtype=torch.long),
        'baseline': torch.from_numpy(baseline),
    }


class BalancedWindowDataset(Dataset):
    def __init__(self, household_indices, samples_per_household):
        requested_households = np.asarray(
            household_indices,
            dtype=np.int32,
        )
        self.samples_per_household = int(samples_per_household)

        minimum_history = TASK['lookback']
        if args.model == 'multicyclenet_adapted':
            minimum_history = max(
                minimum_history,
                cycle_requirement(),
            )

        self.minimum_origin = int(minimum_history)
        self.maximum_origin = int(
            BUNDLE['train_end'] - TASK['horizon']
        )

        if self.maximum_origin < self.minimum_origin:
            raise RuntimeError(
                'The training split is too short for the requested '
                'lookback, cycles and forecast horizon.'
            )

        candidate_origins = np.arange(
            self.minimum_origin,
            self.maximum_origin + 1,
            dtype=np.int64,
        )
        required_values = (
            self.minimum_origin + TASK['horizon']
        )

        self.valid_origins = {}
        valid_households = []

        for raw_house_index in requested_households:
            house_index = int(raw_house_index)
            raw_values = np.asarray(
                BUNDLE['values'][house_index]
            )
            finite = np.isfinite(raw_values).astype(
                np.int32,
                copy=False,
            )
            prefix = np.concatenate(
                [
                    np.zeros(1, dtype=np.int64),
                    np.cumsum(finite, dtype=np.int64),
                ]
            )

            valid_counts = (
                prefix[candidate_origins + TASK['horizon']]
                - prefix[candidate_origins - self.minimum_origin]
            )
            house_origins = candidate_origins[
                valid_counts == required_values
            ]

            if house_origins.size:
                self.valid_origins[house_index] = house_origins
                valid_households.append(house_index)

        self.households = np.asarray(
            valid_households,
            dtype=np.int32,
        )

        if self.households.size == 0:
            raise RuntimeError(
                'No training household has a fully finite window for '
                'this model and task.'
            )

        removed = len(requested_households) - len(self.households)
        if removed:
            print(
                f'Filtered {removed} household(s) without a valid '
                f'{args.model}/{args.task} training window.',
                flush=True,
            )

    def __len__(self):
        return len(self.households) * self.samples_per_household

    def __getitem__(self, index):
        house_index = int(
            self.households[index % len(self.households)]
        )
        origins = self.valid_origins[house_index]
        rng = np.random.default_rng(
            args.seed * 1_000_003
            + index * 97
            + int(time.time_ns() % 10_000)
        )
        origin = int(origins[rng.integers(0, len(origins))])
        sample = make_sample(house_index, origin)

        if sample is None:
            raise RuntimeError(
                'A prevalidated training origin unexpectedly became invalid.'
            )

        return sample


class FixedWindowDataset(Dataset):
    def __init__(self, household_indices, segment_start, segment_end, origins_per_household):
        self.samples = []
        minimum_history = TASK['lookback']
        if args.model == 'multicyclenet_adapted':
            minimum_history = max(minimum_history, cycle_requirement())
        earliest = max(segment_start, minimum_history)
        latest = segment_end - TASK['horizon']
        origins = np.unique(np.linspace(earliest, latest, num=max(1, origins_per_household), dtype=np.int64))
        for house_index in household_indices:
            for origin in origins:
                if make_sample(int(house_index), int(origin)) is not None:
                    self.samples.append((int(house_index), int(origin)))
        if not self.samples:
            raise RuntimeError('No valid fixed evaluation windows were found.')

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        house_index, origin = self.samples[index]
        sample = make_sample(house_index, origin)
        if sample is None:
            raise RuntimeError('A previously valid sample became invalid.')
        return sample


def make_loader(dataset, shuffle, batch_size=None):
    kwargs = dict(
        dataset=dataset,
        batch_size=batch_size or args.batch_size,
        shuffle=shuffle,
        num_workers=args.workers,
        pin_memory=True,
        persistent_workers=args.workers > 0,
        drop_last=shuffle,
    )
    if args.workers > 0:
        kwargs['prefetch_factor'] = 2
    return DataLoader(**kwargs)


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, maximum_length=4096):
        super().__init__()
        positions = torch.arange(maximum_length).unsqueeze(1)
        divisors = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10_000.0) / d_model))
        encoding = torch.zeros(maximum_length, d_model)
        encoding[:, 0::2] = torch.sin(positions * divisors)
        encoding[:, 1::2] = torch.cos(positions * divisors)
        self.register_buffer('encoding', encoding[None], persistent=False)

    def forward(self, x):
        return x + self.encoding[:, :x.size(1)]


class GatedResidualNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, output_size=None, dropout=0.1):
        super().__init__()
        output_size = output_size or input_size
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size * 2)
        self.dropout = nn.Dropout(dropout)
        self.skip = nn.Identity() if input_size == output_size else nn.Linear(input_size, output_size)
        self.norm = nn.LayerNorm(output_size)

    def forward(self, x):
        residual = self.skip(x)
        hidden = self.dropout(F.elu(self.fc1(x)))
        value, gate = self.fc2(hidden).chunk(2, dim=-1)
        return self.norm(residual + value * torch.sigmoid(gate))


class VariableSelectionNetwork(nn.Module):
    def __init__(self, n_variables, hidden_size, dropout=0.1):
        super().__init__()
        self.embeddings = nn.ModuleList([nn.Linear(1, hidden_size) for _ in range(n_variables)])
        self.grns = nn.ModuleList([GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout) for _ in range(n_variables)])
        self.weight_network = nn.Sequential(nn.Linear(n_variables, hidden_size), nn.ELU(), nn.Linear(hidden_size, n_variables))

    def forward(self, variables):
        weights = torch.softmax(self.weight_network(variables), dim=-1)
        transformed = []
        for index, (embedding, grn) in enumerate(zip(self.embeddings, self.grns)):
            transformed.append(grn(embedding(variables[..., index:index + 1])))
        stacked = torch.stack(transformed, dim=-2)
        return (stacked * weights.unsqueeze(-1)).sum(dim=-2), weights


class GlobalPatchTST(nn.Module):
    def __init__(self, lookback, horizon, calendar_size=9, patch_length=16, stride=8, d_model=128, n_heads=8, n_layers=3, dropout=0.1):
        super().__init__()
        self.patch_length = min(patch_length, lookback)
        self.stride = min(stride, self.patch_length)
        self.n_patches = (lookback - self.patch_length) // self.stride + 1
        self.patch_projection = nn.Linear(self.patch_length, d_model)
        self.position = nn.Parameter(torch.zeros(1, self.n_patches, d_model))
        nn.init.trunc_normal_(self.position, std=0.02)
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=d_model * 4, dropout=dropout, activation='gelu', batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.history_head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, horizon))
        self.calendar_projection = nn.Sequential(nn.Linear(calendar_size, d_model), nn.GELU(), nn.Linear(d_model, 1))

    def forward(self, batch):
        x = batch['x'].squeeze(-1)
        patches = x.unfold(1, self.patch_length, self.stride)
        encoded = self.encoder(self.patch_projection(patches) + self.position)
        return self.history_head(encoded.mean(dim=1)) + self.calendar_projection(batch['y_calendar']).squeeze(-1)


class GlobalEncoderDecoderTransformer(nn.Module):
    def __init__(self, horizon, input_size=10, d_model=128, n_heads=8, n_layers=3, dropout=0.1):
        super().__init__()
        self.encoder_projection = nn.Linear(input_size, d_model)
        self.decoder_projection = nn.Linear(input_size, d_model)
        self.position = PositionalEncoding(d_model)
        self.transformer = nn.Transformer(d_model=d_model, nhead=n_heads, num_encoder_layers=n_layers, num_decoder_layers=n_layers, dim_feedforward=d_model * 4, dropout=dropout, activation='gelu', batch_first=True, norm_first=True)
        self.output = nn.Linear(d_model, 1)

    def forward(self, batch):
        encoder_input = torch.cat([batch['x'], batch['x_calendar']], dim=-1)
        zeros = torch.zeros(batch['y_calendar'].size(0), batch['y_calendar'].size(1), 1, device=batch['y_calendar'].device, dtype=batch['y_calendar'].dtype)
        decoder_input = torch.cat([zeros, batch['y_calendar']], dim=-1)
        source = self.position(self.encoder_projection(encoder_input))
        target = self.position(self.decoder_projection(decoder_input))
        causal_mask = nn.Transformer.generate_square_subsequent_mask(target.size(1), device=target.device)
        return self.output(self.transformer(source, target, tgt_mask=causal_mask)).squeeze(-1)


class NBeatsBlock(nn.Module):
    def __init__(self, input_size, lookback, horizon, hidden_size=256, n_layers=4):
        super().__init__()
        layers = []
        current = input_size
        for _ in range(n_layers):
            layers += [nn.Linear(current, hidden_size), nn.ReLU()]
            current = hidden_size
        self.mlp = nn.Sequential(*layers)
        self.backcast = nn.Linear(hidden_size, lookback)
        self.forecast = nn.Linear(hidden_size, horizon)

    def forward(self, x):
        hidden = self.mlp(x)
        return self.backcast(hidden), self.forecast(hidden)


class GlobalNBeatsLocalized(nn.Module):
    def __init__(self, lookback, horizon, calendar_size=9, n_blocks=8, hidden_size=256):
        super().__init__()
        self.first = NBeatsBlock(lookback + horizon * calendar_size, lookback, horizon, hidden_size)
        self.blocks = nn.ModuleList([NBeatsBlock(lookback, lookback, horizon, hidden_size) for _ in range(n_blocks - 1)])

    def forward(self, batch):
        lags = batch['x'].squeeze(-1)
        backcast, forecast = self.first(torch.cat([lags, batch['y_calendar'].flatten(1)], dim=1))
        residual = lags - backcast
        for block in self.blocks:
            backcast, partial = block(residual)
            residual = residual - backcast
            forecast = forecast + partial
        return forecast


class MultiCycleNetAdapted(nn.Module):
    def __init__(self, horizon, context_width, calendar_size=9, hidden_size=160, dropout=0.15):
        super().__init__()
        self.horizon = horizon
        self.cycle_lstm = nn.LSTM(context_width, hidden_size, num_layers=2, dropout=dropout, batch_first=True, bidirectional=True)
        self.cycle_attention = nn.Linear(hidden_size * 2, 1)
        self.recent_lstm = nn.LSTM(1, hidden_size, num_layers=2, dropout=dropout, batch_first=True)
        self.calendar = nn.Sequential(nn.Linear(calendar_size, hidden_size), nn.GELU(), nn.Dropout(dropout))
        self.output = nn.Sequential(nn.Linear(hidden_size * 4, hidden_size * 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden_size * 2, 1))

    def forward(self, batch):
        cycle = batch['cycle']
        batch_size, horizon, n_cycles, context_width = cycle.shape
        cycle_output, _ = self.cycle_lstm(cycle.reshape(batch_size * horizon, n_cycles, context_width))
        weights = torch.softmax(self.cycle_attention(cycle_output).squeeze(-1), dim=1)
        cycle_context = (cycle_output * weights.unsqueeze(-1)).sum(dim=1).reshape(batch_size, horizon, -1)
        _, (hidden, _) = self.recent_lstm(batch['x'])
        recent_context = hidden[-1][:, None, :].expand(-1, horizon, -1)
        calendar_context = self.calendar(batch['y_calendar'])
        return self.output(torch.cat([cycle_context, recent_context, calendar_context], dim=-1)).squeeze(-1)


class GlobalTFT(nn.Module):
    def __init__(self, hidden_size=128, n_heads=4, dropout=0.1, quantiles=(0.1, 0.5, 0.9)):
        super().__init__()
        self.quantiles = tuple(quantiles)
        self.past_selection = VariableSelectionNetwork(10, hidden_size, dropout)
        self.future_selection = VariableSelectionNetwork(9, hidden_size, dropout)
        self.encoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.decoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.post_lstm = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.attention = nn.MultiheadAttention(hidden_size, n_heads, dropout=dropout, batch_first=True)
        self.post_attention = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.output = nn.Linear(hidden_size, len(self.quantiles))

    def forward(self, batch):
        past, past_weights = self.past_selection(torch.cat([batch['x'], batch['x_calendar']], dim=-1))
        future, future_weights = self.future_selection(batch['y_calendar'])
        encoded, state = self.encoder_lstm(past)
        decoded, _ = self.decoder_lstm(future, state)
        sequence = self.post_lstm(torch.cat([encoded, decoded], dim=1))
        length = sequence.size(1)
        mask = torch.triu(torch.ones(length, length, device=sequence.device, dtype=torch.bool), diagonal=1)
        attended, _ = self.attention(sequence, sequence, sequence, attn_mask=mask, need_weights=False)
        quantiles = self.output(self.post_attention(attended)[:, -decoded.size(1):])
        return {'quantiles': quantiles, 'prediction': quantiles[..., 1], 'past_variable_weights': past_weights, 'future_variable_weights': future_weights}


def build_model():
    lookback = TASK['lookback']
    horizon = TASK['horizon']
    if args.model == 'global_patchtst':
        return GlobalPatchTST(lookback, horizon, patch_length=16 if lookback >= 16 else 7, stride=8 if lookback >= 16 else 4)
    if args.model == 'global_transformer':
        return GlobalEncoderDecoderTransformer(horizon)
    if args.model == 'global_nbeats_localized':
        return GlobalNBeatsLocalized(lookback, horizon)
    if args.model == 'multicyclenet_adapted':
        return MultiCycleNetAdapted(horizon, 2 * TASK['cycle_context_radius'] + 1)
    if args.model == 'global_tft':
        return GlobalTFT()
    raise KeyError(args.model)


def model_prediction(output):
    return output['prediction'] if isinstance(output, dict) else output


def quantile_loss(predictions, target, quantiles):
    losses = []
    for index, quantile in enumerate(quantiles):
        error = target - predictions[..., index]
        losses.append(torch.maximum((quantile - 1.0) * error, quantile * error))
    return torch.stack(losses, dim=-1).mean()


def compute_loss(model, output, target):
    if args.model == 'global_tft':
        return quantile_loss(output['quantiles'], target, model.quantiles)
    return F.mse_loss(model_prediction(output), target)


def learning_rate():
    return {'global_patchtst': 1e-4, 'global_transformer': 1e-4, 'global_nbeats_localized': 5e-4, 'multicyclenet_adapted': 3e-4, 'global_tft': 3e-4}[args.model]


def move_batch(batch):
    return {key: value.to(DEVICE, non_blocking=True) for key, value in batch.items()}


def count_parameters(model):
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


class WarmupCosineScheduler:
    def __init__(self, optimizer, total_steps, warmup_steps):
        self.optimizer = optimizer
        self.total_steps = max(total_steps, 1)
        self.warmup_steps = min(warmup_steps, max(self.total_steps - 1, 0))
        self.step_number = 0
        self.initial_lrs = [group['lr'] for group in optimizer.param_groups]

    def step(self):
        self.step_number += 1
        if self.step_number <= self.warmup_steps:
            scale = self.step_number / max(self.warmup_steps, 1)
        else:
            progress = (self.step_number - self.warmup_steps) / max(self.total_steps - self.warmup_steps, 1)
            scale = 0.05 + 0.95 * 0.5 * (1.0 + math.cos(math.pi * progress))
        for initial_lr, group in zip(self.initial_lrs, self.optimizer.param_groups):
            group['lr'] = initial_lr * scale


@torch.no_grad()
def validation_loss(model, loader):
    model.eval()
    total = 0.0
    count = 0
    for batch in loader:
        batch = move_batch(batch)
        with torch.autocast(device_type='cuda', dtype=torch.float16, enabled=AMP_ENABLED):
            output = model(batch)
            loss = compute_loss(model, output, batch['y'])
        total += float(loss.item()) * batch['y'].numel()
        count += batch['y'].numel()
    return total / max(count, 1)


class HouseholdMetricAccumulator:
    def __init__(self, n_households):
        self.count = np.zeros(n_households, dtype=np.int64)
        self.absolute = np.zeros(n_households)
        self.squared = np.zeros(n_households)
        self.signed = np.zeros(n_households)
        self.smape = np.zeros(n_households)
        self.y_sum = np.zeros(n_households)
        self.y_squared = np.zeros(n_households)
        self.baseline_absolute = np.zeros(n_households)

    def update(self, prediction, target, baseline, households):
        for row, house in enumerate(np.asarray(households, dtype=np.int64)):
            error = prediction[row] - target[row]
            baseline_error = baseline[row] - target[row]
            n = target.shape[1]
            self.count[house] += n
            self.absolute[house] += np.abs(error).sum()
            self.squared[house] += np.square(error).sum()
            self.signed[house] += error.sum()
            self.smape[house] += (2.0 * np.abs(error) / (np.abs(prediction[row]) + np.abs(target[row]) + 1e-8)).sum()
            self.y_sum[house] += target[row].sum()
            self.y_squared[house] += np.square(target[row]).sum()
            self.baseline_absolute[house] += np.abs(baseline_error).sum()

    def compute(self):
        valid = self.count > 0
        count = self.count[valid].astype(np.float64)
        house_mae = self.absolute[valid] / count
        house_rmse = np.sqrt(self.squared[valid] / count)
        house_smape = 100.0 * self.smape[valid] / count
        house_bias = self.signed[valid] / count
        baseline_mae = self.baseline_absolute[valid] / count
        sst = self.y_squared[valid] - np.square(self.y_sum[valid]) / count
        house_r2 = np.full_like(sst, np.nan)
        r2_valid = sst > 1e-12
        house_r2[r2_valid] = 1.0 - self.squared[valid][r2_valid] / sst[r2_valid]
        total_count = count.sum()
        global_sse = self.squared[valid].sum()
        global_y_sum = self.y_sum[valid].sum()
        global_y_squared = self.y_squared[valid].sum()
        global_sst = global_y_squared - global_y_sum**2 / max(total_count, 1)
        macro_mae = float(np.mean(house_mae))
        macro_baseline = float(np.mean(baseline_mae))
        return {
            'n_evaluated_households': int(valid.sum()),
            'macro_mae_kwh': macro_mae,
            'median_mae_kwh': float(np.median(house_mae)),
            'macro_rmse_kwh': float(np.mean(house_rmse)),
            'macro_smape_percent': float(np.mean(house_smape)),
            'macro_bias_kwh': float(np.mean(house_bias)),
            'macro_r2': float(np.nanmean(house_r2)),
            'median_r2': float(np.nanmedian(house_r2)),
            'global_r2': float(1.0 - global_sse / max(global_sst, 1e-12)),
            'seasonal_naive_macro_mae_kwh': macro_baseline,
            'mae_improvement_over_seasonal_percent': float(100.0 * (macro_baseline - macro_mae) / max(macro_baseline, 1e-12)),
            'households_beating_seasonal_percent': float(100.0 * np.mean(house_mae < baseline_mae)),
            'p75_household_mae_kwh': float(np.percentile(house_mae, 75)),
            'p90_household_mae_kwh': float(np.percentile(house_mae, 90)),
        }


@torch.no_grad()
def evaluate(model, loader, routed_models=None):
    if routed_models is None:
        model.eval()
    else:
        for routed_model in routed_models.values():
            routed_model.eval()
    accumulator = HouseholdMetricAccumulator(BUNDLE['values'].shape[0])
    saved_prediction, saved_target, saved_house = [], [], []
    started = time.perf_counter()
    for batch in loader:
        house_cpu = batch['house'].numpy()
        baseline_cpu = batch['baseline'].numpy()
        batch = move_batch(batch)
        if routed_models is None:
            with torch.autocast(device_type='cuda', dtype=torch.float16, enabled=AMP_ENABLED):
                prediction_z = model_prediction(model(batch))
        else:
            prediction_z = torch.empty_like(batch['y'])
            for cluster_id, routed_model in routed_models.items():
                mask = batch['cluster'] == int(cluster_id)
                if mask.any():
                    sub_batch = {key: value[mask] for key, value in batch.items()}
                    with torch.autocast(
                        device_type='cuda',
                        dtype=torch.float16,
                        enabled=AMP_ENABLED,
                    ):
                        routed_prediction = model_prediction(
                            routed_model(sub_batch)
                        )

                    # Autocast may return float16 while prediction_z follows
                    # the float32 target dtype. Explicit casting is required
                    # before boolean indexed assignment.
                    prediction_z[mask] = routed_prediction.to(
                        dtype=prediction_z.dtype
                    )
        prediction = inverse_normalize(prediction_z.float().cpu().numpy(), house_cpu)
        target = inverse_normalize(batch['y'].float().cpu().numpy(), house_cpu)
        accumulator.update(prediction, target, baseline_cpu, house_cpu)
        remaining = 24 - len(saved_prediction)
        if remaining > 0:
            take = min(remaining, len(house_cpu))
            saved_prediction.extend(prediction[:take])
            saved_target.extend(target[:take])
            saved_house.extend(house_cpu[:take])
    metrics = accumulator.compute()
    metrics['inference_seconds'] = time.perf_counter() - started
    metrics['evaluation_windows'] = len(loader.dataset)
    if saved_prediction:
        np.savez_compressed(SAMPLE_PATH, prediction=np.asarray(saved_prediction, dtype=np.float32), target=np.asarray(saved_target, dtype=np.float32), household=np.asarray(saved_house, dtype=np.int32))
    return metrics


def train_model(model, train_loader, validation_loader, epochs, checkpoint_path):
    model = model.to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate(), weight_decay=1e-4)
    total_steps = max(1, len(train_loader) * epochs)
    scheduler = WarmupCosineScheduler(optimizer, total_steps, min(1000, max(10, int(total_steps * 0.1))))
    try:
        amp_scaler = torch.amp.GradScaler('cuda', enabled=AMP_ENABLED)
    except (AttributeError, TypeError):
        amp_scaler = torch.cuda.amp.GradScaler(enabled=AMP_ENABLED)
    best_validation = float('inf')
    bad_epochs = 0
    history = []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        running_count = 0
        epoch_started = time.perf_counter()
        for batch in train_loader:
            batch = move_batch(batch)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type='cuda', dtype=torch.float16, enabled=AMP_ENABLED):
                output = model(batch)
                loss = compute_loss(model, output, batch['y'])
            amp_scaler.scale(loss).backward()
            amp_scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            amp_scaler.step(optimizer)
            amp_scaler.update()
            scheduler.step()
            running_loss += float(loss.item()) * batch['y'].numel()
            running_count += batch['y'].numel()
        train_loss = running_loss / max(running_count, 1)
        val_loss = validation_loss(model, validation_loader)
        row = {'epoch': epoch, 'training_loss': train_loss, 'validation_loss': val_loss, 'learning_rate': optimizer.param_groups[0]['lr'], 'seconds': time.perf_counter() - epoch_started}
        history.append(row)
        atomic_json(HISTORY_PATH, history)
        print(json.dumps(row), flush=True)
        if val_loss < best_validation - 1e-7:
            best_validation = val_loss
            bad_epochs = 0
            torch.save({'model_state_dict': model.state_dict(), 'model': args.model, 'task': args.task, 'best_validation_loss': best_validation, 'normalization': NORMALIZATION, 'seed': args.seed}, checkpoint_path)
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                print(f'Early stopping after epoch {epoch}', flush=True)
                break
    try:
        checkpoint = torch.load(checkpoint_path, map_location=DEVICE, weights_only=False)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
    model.load_state_dict(checkpoint['model_state_dict'])
    return {'model': model, 'best_validation_loss': best_validation, 'history': history, 'training_seconds': time.perf_counter() - started}


def localized_nbeats_models(global_model):
    routed_models = {}
    for cluster_id in np.unique(BUNDLE['clusters'][BUNDLE['known']]):
        cluster_houses = BUNDLE['known'][BUNDLE['clusters'][BUNDLE['known']] == cluster_id]
        local_model = copy.deepcopy(global_model).to(DEVICE)
        if len(cluster_houses) >= 5:
            local_loader = make_loader(BalancedWindowDataset(cluster_houses, max(4, args.samples_per_household // 4)), shuffle=True)
            optimizer = torch.optim.AdamW(local_model.parameters(), lr=learning_rate() * 0.2, weight_decay=1e-4)
            try:
                scaler = torch.amp.GradScaler('cuda', enabled=AMP_ENABLED)
            except (AttributeError, TypeError):
                scaler = torch.cuda.amp.GradScaler(enabled=AMP_ENABLED)
            for _ in range(args.localization_epochs):
                local_model.train()
                for batch in local_loader:
                    batch = move_batch(batch)
                    optimizer.zero_grad(set_to_none=True)
                    with torch.autocast(device_type='cuda', dtype=torch.float16, enabled=AMP_ENABLED):
                        loss = compute_loss(local_model, local_model(batch), batch['y'])
                    scaler.scale(loss).backward()
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(local_model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
        torch.save(local_model.state_dict(), RUN_DIR / f'localized_cluster_{int(cluster_id)}.pt')
        routed_models[int(cluster_id)] = local_model
    return routed_models


def main():
    started = time.time()
    train_dataset = BalancedWindowDataset(BUNDLE['known'], args.samples_per_household)
    validation_dataset = FixedWindowDataset(BUNDLE['known'], BUNDLE['train_end'], BUNDLE['val_end'], args.eval_origins)
    known_test_dataset = FixedWindowDataset(BUNDLE['known'], BUNDLE['val_end'], BUNDLE['test_end'], args.eval_origins)
    cold_test_dataset = FixedWindowDataset(BUNDLE['cold'], BUNDLE['val_end'], BUNDLE['test_end'], args.eval_origins)
    train_loader = make_loader(train_dataset, True)
    validation_loader = make_loader(validation_dataset, False)
    known_test_loader = make_loader(known_test_dataset, False)
    cold_test_loader = make_loader(cold_test_dataset, False)
    model = build_model()
    parameter_count = count_parameters(model)
    print(model, flush=True)
    print(f'Trainable parameters: {parameter_count:,}', flush=True)
    trained = train_model(model, train_loader, validation_loader, args.epochs, CHECKPOINT_PATH)
    model = trained['model']
    metrics = {
        'status': 'success',
        'model': args.model,
        'task': args.task,
        'resolution': TASK['resolution'],
        'lookback': TASK['lookback'],
        'horizon': TASK['horizon'],
        'normalization': NORMALIZATION,
        'seed': args.seed,
        'trainable_parameters': parameter_count,
        'best_validation_loss': trained['best_validation_loss'],
        'epochs_completed': len(trained['history']),
        'training_seconds': trained['training_seconds'],
        'total_wall_seconds': time.time() - started,
        'known_households': evaluate(model, known_test_loader),
        'cold_start_households': evaluate(model, cold_test_loader),
    }
    if args.model == 'global_nbeats_localized' and args.localize_nbeats:
        routed = localized_nbeats_models(model)
        metrics['localized_known_households'] = evaluate(model, known_test_loader, routed_models=routed)
        metrics['localized_cold_start_households'] = evaluate(model, cold_test_loader, routed_models=routed)
    atomic_json(METRICS_PATH, metrics)
    print('\nFINAL_METRICS', flush=True)
    print(json.dumps(metrics, indent=2), flush=True)
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        failure = {'status': 'failed', 'model': args.model, 'task': args.task, 'error_type': type(error).__name__, 'error': str(error), 'traceback': traceback.format_exc()}
        atomic_json(METRICS_PATH, failure)
        print(failure['traceback'], file=sys.stderr, flush=True)
        sys.exit(1)
