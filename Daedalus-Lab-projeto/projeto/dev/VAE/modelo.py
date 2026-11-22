"""VAE condicional para composições de ligas metálicas (% em massa).

Condição: máscara binária com os elementos permitidos (os que a Atena informar).
Saída do decodificador: softmax mascarado -> frações >= 0 que somam exatamente 1 (100 %)
e são zero em qualquer elemento fora da máscara.
"""
import torch
import torch.nn as nn


class VAEComposicao(nn.Module):
    def __init__(self, n_elementos: int, latente: int = 8, oculto: int = 64):
        super().__init__()
        self.n_elementos, self.latente, self.oculto = n_elementos, latente, oculto
        self.codificador = nn.Sequential(
            nn.Linear(2 * n_elementos, oculto), nn.SiLU(),
            nn.Linear(oculto, oculto), nn.SiLU(),
            nn.Linear(oculto, 2 * latente),
        )
        self.decodificador = nn.Sequential(
            nn.Linear(latente + n_elementos, oculto), nn.SiLU(),
            nn.Linear(oculto, oculto), nn.SiLU(),
            nn.Linear(oculto, n_elementos),
        )

    def codificar(self, x, mascara):
        mu, logvar = self.codificador(torch.cat([x.clamp_min(0).sqrt(), mascara], 1)).chunk(2, 1)
        return mu, logvar.clamp(-10, 10)

    def decodificar(self, z, mascara):
        logits = self.decodificador(torch.cat([z, mascara], 1))
        logits = logits.masked_fill(mascara <= 0, float("-inf"))
        return torch.softmax(logits, 1)

    def forward(self, x, mascara):
        mu, logvar = self.codificar(x, mascara)
        z = mu + torch.randn_like(mu) * (0.5 * logvar).exp()
        return self.decodificar(z, mascara), mu, logvar


def contar_parametros(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters())


def oculto_para_alvo(n_elementos: int, latente: int, alvo: int) -> int:
    """Escolhe a largura da camada oculta que deixa o modelo mais perto de `alvo` parâmetros."""
    return min(range(8, 1025),
               key=lambda h: abs(contar_parametros(VAEComposicao(n_elementos, latente, h)) - alvo))


def perda(x, p, mu, logvar, beta, free_bits=0.0):
    """free_bits: KL mínimo (nats) por dimensão latente, evita colapso do posterior."""
    eps = 1e-12
    entropia_cruzada = -(x * (p + eps).log()).sum(1)
    hellinger = ((x.sqrt() - (p + eps).sqrt()) ** 2).sum(1)  # dá peso aos elementos minoritários
    kl = -0.5 * (1 + logvar - mu.pow(2) - logvar.exp()).sum(1)
    rec = entropia_cruzada + hellinger
    kl_dim = (-0.5 * (1 + logvar - mu.pow(2) - logvar.exp())).mean(0)
    kl_otim = kl_dim.clamp_min(free_bits).sum()
    return rec.mean() + beta * kl_otim, rec.mean(), kl.mean()


def carregar(caminho, dispositivo="cpu"):
    ck = torch.load(caminho, map_location=dispositivo, weights_only=False)
    cfg = ck["config"]
    m = VAEComposicao(len(ck["elementos"]), cfg["latente"], cfg["oculto"]).to(dispositivo)
    m.load_state_dict(ck["estado"])
    m.eval()
    return m, ck
