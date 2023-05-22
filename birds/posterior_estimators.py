import torch


class TrainableGaussian(torch.nn.Module):
    def __init__(self, mu=[0.0], sigma=1.0):
        super().__init__()
        self.mu = torch.nn.Parameter(torch.tensor(mu))
        self.sigma = torch.nn.Parameter(sigma * torch.eye(len(mu)))

    def clamp_sigma(self):
        sigma = self.sigma.clone()
        mask = torch.eye(len(self.mu)).bool()
        sigma[mask] = torch.clamp(
            self.sigma[mask], min=1e-3
        )
        return sigma

    def log_prob(self, x):
        sigma = self.clamp_sigma()
        return torch.distributions.MultivariateNormal(self.mu, sigma).log_prob(x)

    def rsample(self, n=()):
        sigma = self.clamp_sigma()
        dist = torch.distributions.MultivariateNormal(self.mu, sigma)
        return dist.rsample(n)

    def sample(self, n=()):
        sigma = self.clamp_sigma()
        dist = torch.distributions.MultivariateNormal(self.mu, sigma)
        return dist.sample(n)

    def __call__(self, x=None):
        return self

