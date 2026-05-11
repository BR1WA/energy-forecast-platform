"""PyTorch model definitions — must match training notebook exactly."""
import torch
import torch.nn as nn


class ResBlock(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(d, d), nn.BatchNorm1d(d), nn.ReLU(),
                                 nn.Linear(d, d), nn.BatchNorm1d(d))
        self.act = nn.ReLU()

    def forward(self, x):
        return self.act(self.net(x) + x)


class CascadedResNet(nn.Module):
    def __init__(self, inp, hid=128, blocks=4, out=32):
        super().__init__()
        self.proj = nn.Sequential(nn.Linear(inp, hid), nn.BatchNorm1d(hid), nn.ReLU())
        self.blocks = nn.Sequential(*[ResBlock(hid) for _ in range(blocks)])
        self.fc = nn.Linear(hid, out)

    def forward(self, x):
        return self.fc(self.blocks(self.proj(x)))


class DNN(nn.Module):
    def __init__(self, inp, hid=128, layers=5, drop=0.3):
        super().__init__()
        mods = [nn.Linear(inp, hid), nn.BatchNorm1d(hid), nn.ReLU(), nn.Dropout(drop)]
        for _ in range(layers - 2):
            mods += [nn.Linear(hid, hid), nn.BatchNorm1d(hid), nn.ReLU(), nn.Dropout(drop)]
        mods += [nn.Linear(hid, 1), nn.Sigmoid()]
        self.net = nn.Sequential(*mods)

    def forward(self, x):
        return self.net(x).squeeze(-1)

    def features(self, x):
        for m in list(self.net.children())[:-2]:
            x = m(x)
        return x


class RNNModel(nn.Module):
    def __init__(self, inp, hid=128, rnn_type='lstm', bidir=False, drop=0.3):
        super().__init__()
        RNN = {'lstm': nn.LSTM, 'gru': nn.GRU}[rnn_type]
        self.rnn = RNN(1, hid, num_layers=2, batch_first=True,
                       dropout=drop, bidirectional=bidir)
        mult = 2 if bidir else 1
        self.head = nn.Sequential(nn.Linear(hid * mult, 64), nn.ReLU(),
                                  nn.Dropout(drop), nn.Linear(64, 1), nn.Sigmoid())
        self.feat_layer = nn.Sequential(nn.Linear(hid * mult, 64), nn.ReLU())

    def forward(self, x):
        x = x.unsqueeze(-1)
        out, _ = self.rnn(x)
        return self.head(out[:, -1, :]).squeeze(-1)

    def features(self, x):
        x = x.unsqueeze(-1)
        out, _ = self.rnn(x)
        return self.feat_layer(out[:, -1, :])


def make_model(name, inp):
    m = {
        'DNN': lambda: DNN(inp),
        'LSTM': lambda: RNNModel(inp, rnn_type='lstm', bidir=False),
        'BiLSTM': lambda: RNNModel(inp, rnn_type='lstm', bidir=True),
        'GRU': lambda: RNNModel(inp, rnn_type='gru', bidir=False),
        'BiGRU': lambda: RNNModel(inp, rnn_type='gru', bidir=True),
    }
    return m[name]()
