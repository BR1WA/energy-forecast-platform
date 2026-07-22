"""Horizon-dynamic inference architecture for fixed production Global TFT artifacts."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class GatedResidualNetwork(nn.Module):
    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int | None = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        output_size = output_size or input_size
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size * 2)
        self.dropout = nn.Dropout(dropout)
        self.skip = nn.Identity() if input_size == output_size else nn.Linear(input_size, output_size)
        self.norm = nn.LayerNorm(output_size)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        residual = self.skip(values)
        hidden = self.dropout(F.elu(self.fc1(values)))
        value, gate = self.fc2(hidden).chunk(2, dim=-1)
        return self.norm(residual + value * torch.sigmoid(gate))


class VariableSelectionNetwork(nn.Module):
    def __init__(self, variable_count: int, hidden_size: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.embeddings = nn.ModuleList(
            [nn.Linear(1, hidden_size) for _ in range(variable_count)]
        )
        self.grns = nn.ModuleList(
            [
                GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
                for _ in range(variable_count)
            ]
        )
        self.weight_network = nn.Sequential(
            nn.Linear(variable_count, hidden_size),
            nn.ELU(),
            nn.Linear(hidden_size, variable_count),
        )

    def forward(self, variables: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        weights = torch.softmax(self.weight_network(variables), dim=-1)
        transformed = [
            grn(embedding(variables[..., index : index + 1]))
            for index, (embedding, grn) in enumerate(zip(self.embeddings, self.grns))
        ]
        stacked = torch.stack(transformed, dim=-2)
        return (stacked * weights.unsqueeze(-1)).sum(dim=-2), weights


class GlobalTFT(nn.Module):
    """Architecture shared by the independently packaged 24h and 168h checkpoints."""

    def __init__(
        self,
        hidden_size: int = 128,
        n_heads: int = 4,
        dropout: float = 0.1,
        quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
    ) -> None:
        super().__init__()
        self.quantiles = quantiles
        self.past_selection = VariableSelectionNetwork(10, hidden_size, dropout)
        self.future_selection = VariableSelectionNetwork(9, hidden_size, dropout)
        self.encoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.decoder_lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.post_lstm = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout)
        self.attention = nn.MultiheadAttention(
            hidden_size, n_heads, dropout=dropout, batch_first=True
        )
        self.post_attention = GatedResidualNetwork(
            hidden_size, hidden_size, hidden_size, dropout
        )
        self.output = nn.Linear(hidden_size, len(quantiles))

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        past, past_weights = self.past_selection(
            torch.cat([batch["x"], batch["x_calendar"]], dim=-1)
        )
        future, future_weights = self.future_selection(batch["y_calendar"])
        encoded, state = self.encoder_lstm(past)
        decoded, _ = self.decoder_lstm(future, state)
        sequence = self.post_lstm(torch.cat([encoded, decoded], dim=1))
        length = sequence.size(1)
        mask = torch.triu(
            torch.ones(length, length, device=sequence.device, dtype=torch.bool),
            diagonal=1,
        )
        attended, _ = self.attention(
            sequence, sequence, sequence, attn_mask=mask, need_weights=False
        )
        quantiles = self.output(self.post_attention(attended)[:, -decoded.size(1) :])
        return {
            "quantiles": quantiles,
            "prediction": quantiles[..., 1],
            "past_variable_weights": past_weights,
            "future_variable_weights": future_weights,
        }
