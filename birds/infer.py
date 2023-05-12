import numpy as np
import torch
from tqdm import tqdm
import logging

from birds.mpi_setup import mpi_rank
from birds.forecast import compute_forecast_loss_and_jacobian
from birds.regularisation import compute_regularisation_loss

logger = logging.getLogger("calibrator")


class Calibrator:
    def __init__(
        self,
        model,
        prior,
        posterior_estimator,
        data,
        w=0.0,
        gradient_clipping_norm=np.inf,
        forecast_loss=None,
        optimizer=None,
        n_samples_per_epoch=5,
        n_samples_regularisation=10_000,
        progress_bar=True,
    ):
        """
        Class that handles the training of the posterior_estimator given the model, data, and prior.

        Arguments:
            model (torch.nn.Module): The simulator model.
            prior (torch.distributions.Distribution): The prior distribution.
            posterior_estimator (torch.distributions.Distribution): The variational distribution that approximates the generalised posterior.
            data (List[torch.Tensor]): The observed data to calibrate against. It must be given as a list of tensors that matches the output of the model.
            w (float): The weight of the regularisation loss in the total loss.
            gradient_clipping_norm (float): The norm to which the gradients are clipped.
            forecast_loss (function): The loss function to use for the forecast loss.
            n_samples_per_epoch (int): The number of samples to draw from the variational distribution per epoch.
            n_samples_regularisation (int): The number of samples used to evaluate the regularisation loss.
            progress_bar (bool): Whether to display a progress bar during training.
        """
        self.model = model
        self.prior = prior
        self.posterior_estimator = posterior_estimator
        self.data = data
        self.w = w
        self.gradient_clipping_norm = gradient_clipping_norm
        if forecast_loss is None:
            forecast_loss = torch.nn.MSELoss()
        self.forecast_loss = forecast_loss
        if optimizer is None:
            optimizer = torch.optim.Adam(posterior_estimator.parameters(), lr=1e-3)
        self.optimizer = optimizer
        self.n_samples_per_epoch = n_samples_per_epoch
        self.n_samples_regularisation = n_samples_regularisation
        self.progress_bar = progress_bar

    def _differentiate_loss(
        self, forecast_parameters, forecast_jacobians, regularisation_loss
    ):
        """
        Differentiates forecast loss and regularisation loss through the flows and the simulator.

        Arguments:
            forecast_parameters (List[torch.Tensor]): The parameters of the simulator that are differentiated through.
            forecast_jacobians (List[torch.Tensor]): The jacobians of the simulator that are differentiated through.
            regularisation_loss (torch.Tensor): The regularisation loss that is differentiated through.

        Example:
            >>> forecast_parameters = [torch.tensor([1.0, 2.0]), torch.tensor([3.0, 4.0])]
            >>> forecast_jacobians = [torch.tensor([[1.0, 2.0], [3.0, 4.0]]), torch.tensor([[5.0, 6.0], [7.0, 8.0]])]
            >>> regularisation_loss = torch.tensor(1.0)
            >>> _differentiate_loss(forecast_parameters, forecast_jacobians, regularisation_loss)
        """
        # first we just differentiate the loss through reverse-diff
        regularisation_loss.backward()
        # then we differentiate the parameters through the flows but also tkaing into account the jacobians of the simulator
        to_diff = torch.zeros(1)
        for i in range(len(forecast_jacobians)):
            to_diff += torch.dot(forecast_jacobians[i], forecast_parameters[i,:])
        to_diff.backward()

    def step(self):
        """
        Performs one training step.
        """
        self.optimizer.zero_grad()
        (
            forecast_parameters,
            forecast_loss,
            forecast_jacobians,
        ) = compute_forecast_loss_and_jacobian(
            loss_fn=self.forecast_loss,
            model=self.model,
            parameter_generator=lambda x: self.posterior_estimator.rsample((x,)),
            observed_outputs=self.data,
            n_samples=self.n_samples_per_epoch,
        )
        regularisation_loss = self.w * compute_regularisation_loss(
            posterior_estimator=self.posterior_estimator,
            prior=self.prior,
            n_samples=self.n_samples_regularisation,
        )
        self._differentiate_loss(
            forecast_parameters, forecast_jacobians, regularisation_loss
        )
        self.optimizer.step()
        loss = forecast_loss + regularisation_loss
        return loss, forecast_loss, regularisation_loss

    def run(self, n_epochs, max_epochs_without_improvement=20):
        """
        Runs the calibrator for {n_epochs} epochs. Stops if the loss does not improve for {max_epochs_without_improvement} epochs.

        Arguments:
            n_epochs (int): The number of epochs to run the calibrator for.
            max_epochs_without_improvement (int): The number of epochs without improvement after which the calibrator stops.
        """
        best_loss = np.inf
        num_epochs_without_improvement = 0
        iterator = range(n_epochs)
        if self.progress_bar and mpi_rank == 0:
            iterator = tqdm(iterator)
        for _ in tqdm(range(n_epochs)):
            loss, forecast_loss, regularisation_loss = self.step()
            if loss < best_loss:
                best_loss = loss
                num_epochs_without_improvement = 0
            else:
                num_epochs_without_improvement += 1
            if self.progress_bar:
                iterator.set_postfix(
                    {
                        "Forecast": forecast_loss.item(),
                        "Reg.": regularisation_loss.item(),
                        "total": loss.item(),
                        "best loss": best_loss,
                        "epochs since improv.": num_epochs_without_improvement,
                    }
                )
            if num_epochs_without_improvement >= max_epochs_without_improvement:
                logger.info(
                    "Stopping early because the loss did not improve for {} epochs.".format(
                        max_epochs_without_improvement
                    )
                )
                break
