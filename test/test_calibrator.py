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
        true_ps = [0.25]  # , 0.5, 0.75]
        prior = torch.distributions.Normal(0.0, 1.0)
        for true_p in true_ps:
            data = rw.run_and_observe(torch.tensor([true_p]))
            posterior_estimator = TrainableGaussian([0.4], 0.1)
            posterior_estimator.sigma.requires_grad = False
            optimizer = torch.optim.Adam(posterior_estimator.parameters(), lr=5e-3)
            calib = Calibrator(
                model=rw,
                posterior_estimator=posterior_estimator,
                prior=prior,
                data=data,
                optimizer=optimizer,
                diff_mode=diff_mode,
                w=0.0,
                progress_bar=False,
                n_samples_per_epoch=5,
            )
            calib.run(25, max_epochs_without_improvement=100)
            ## check correct result is within 2 sigma
            assert np.isclose(posterior_estimator.mu.item(), true_p, atol = 0.1)

    def test__train_regularisation_only(self):
        rw = RandomWalk(2)
        data = rw.run_and_observe(torch.tensor([0.5]))

        prior = torch.distributions.Normal(3.0, 1)

        posterior_estimator = TrainableGaussian([0.0], 1.0)
        posterior_estimator.sigma.requires_grad = False

        optimizer = torch.optim.Adam(posterior_estimator.parameters(), lr=5e-2)
        calib = Calibrator(
            model=rw,
            posterior_estimator=posterior_estimator,
            prior=prior,
            data=data,
            optimizer=optimizer,
            n_samples_per_epoch=1,
            w=10000.0,
            progress_bar=False,
        )
        calib.run(100, max_epochs_without_improvement=np.inf)
        posterior_estimator.load_state_dict(calib.best_model_state_dict)
        assert np.isclose(posterior_estimator.mu.item(), 3, rtol=0.1)
        assert np.isclose(posterior_estimator.sigma.item(), 1, rtol=0.1)
