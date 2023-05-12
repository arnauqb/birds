import torch

class RandomWalk(torch.nn.Module):
    def __init__(self, n_timesteps, tau_softmax=0.1):
        r"""Implements a differentiable random walk.

        .. math:: X_t = \sum_{i=1}^t (2U_i - 1) where :math:`U_i \sim \text{Bernoulli}(p)`.

        Arguments:
            n_timesteps (int): Number of timesteps to simulate.
            p (float): Probability of moving right at each timestep.
            tau_softmax (float): Temperature parameter for the Gumbel-Softmax
        """
        super().__init__()
        self.n_timesteps = n_timesteps
        self.tau_softmax = tau_softmax

    def forward(self, p):
        r"""Simulates a random walk using the Gumbel-Softmax trick.
        Returns:
            torch.Tensor: Random walk trajectory of shape
                ``(n_timesteps, )``.
        """
        p = torch.clip(p, min=0.0, max=1.0) #torch.nn.functional.softmax(p[0])
        probs = p * torch.ones(self.n_timesteps)
        logits = torch.vstack((probs, 1 - probs)).log()
        steps = torch.nn.functional.gumbel_softmax(
            logits, dim=0, tau=self.tau_softmax, hard=True
        )
        steps_forward = steps[0, :]
        steps_backward = steps[1, :]
        trajectory = steps_forward - steps_backward
        return [trajectory.cumsum(dim=0)]
