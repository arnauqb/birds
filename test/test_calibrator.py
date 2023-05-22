import torch
import pytest
import numpy as np

from birds.models.random_walk import RandomWalk
from birds.calibrator import Calibrator
from birds.posterior_estimators import TrainableGaussian

class TestCalibrator:
    @pytest.mark.parametrize("diff_mode", ["forward", "reverse"])
    def test_random_walk(self, diff_mode):
        """
        Tests inference in a random walk model.
        """
        rw = RandomWalk(100)
        true_ps = [0.25] #, 0.5, 0.75]
        prior = torch.distributions.Normal(0.0, 1.0)
        for true_p in true_ps:
            data = rw.run_and_observe(torch.tensor([true_p]))
            posterior_estimator = TrainableGaussian([0.5], 0.1)
            posterior_estimator.sigma.requires_grad = False
            optimizer = torch.optim.Adam(posterior_estimator.parameters(), lr=1e-2)
            calib = Calibrator(
                model=rw,
                posterior_estimator=posterior_estimator,
                prior=prior,
                data=data,
                optimizer=optimizer,
                diff_mode=diff_mode,
                w=10.0,
                progress_bar=False,
            )
            calib.run(50, max_epochs_without_improvement=100)
            posterior_estimator.load_state_dict(calib.best_model_state_dict)
            ## check correct result is within 2 sigma
            assert np.isclose(posterior_estimator.mu.item(), true_p, rtol=0.25)
