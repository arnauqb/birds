import torch
import numpy as np

from birds.models.random_walk import RandomWalk
from birds.infer import Calibrator


class TrainableGaussian(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.mu = torch.nn.Parameter(0.5 * torch.ones(1))
        self.sigma = torch.nn.Parameter(0.1 * torch.ones(1))

    def log_prob(self, x):
        sigma = torch.clip(self.sigma, min=1e-3)
        return torch.distributions.Normal(self.mu, sigma).log_prob(x)

    def rsample(self, x):
        sigma = torch.clip(self.sigma, min=1e-3)
        return torch.distributions.Normal(self.mu, sigma).rsample(x)

    def sample(self, x):
        sigma = torch.clip(self.sigma, min=1e-3)
        return torch.distributions.Normal(self.mu, sigma).sample(x)


class TestInfer:
    def test_infer(self):
        rw = RandomWalk(100)
        true_ps = [0.25, 0.5, 0.75]
        prior = torch.distributions.Normal(0.0, 1.0)
        for true_p in true_ps:
            data = rw(torch.tensor([true_p]))
            posterior_estimator = TrainableGaussian()
            optimizer = torch.optim.Adam(posterior_estimator.parameters(), lr=1e-2)
            calib = Calibrator(
                model=rw,
                posterior_estimator=posterior_estimator,
                prior=prior,
                data=data,
                optimizer=optimizer,
            )
            calib.run(1000)
            assert np.isclose(calib.posterior_estimator.mu.item(), true_p, rtol=0.25)
