"""
The trough model.
"""
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline as IUS
from scipy.interpolate import RectBivariateSpline as RBS

from mars_troughs import ACCUMULATION_MODEL_MAP, DATAPATHS, LAG_MODEL_MAP


class Trough:
    """
    This object models trough migration patterns (TMPs). It is composed of
    a model for the accumulation of ice on the surface of the trough, accessible
    as the :attr:`accuModel` attribute, as well as a model for the lag
    that builds up over time, accesible as the :attr:`lagModel` attribute.

    Args:
      acc_params (List[float]): model parameters for accumulation
      lag_params (List[float]): model parameters for lag(t)
      acc_model_name (str): name of the accumulation model
        (linear, quadratic, etc)
      lag_model_name (str): name of the lag(t) model (constant, linear, etc)
      errorbar (float, optional): errorbar of the datapoints in pixels; default=1
      angle (float, optional): south-facing slope angle in degrees. Default is 2.9.
      insolation_path (Union[str, Path], optional): path to the file with
        insolation data.
      retreat_path (Union[str, Path], optional): path to the file with
        retreat data
    """

    def __init__(
        self,
        acc_params: List[float],
        lag_params: List[float],
        acc_model_name: str,
        lag_model_name: str,
        errorbar: float = 1.0,
        angle: float = 2.9,
        insolation_path: Union[str, Path] = DATAPATHS.INSOLATION,
        retreat_path: Union[str, Path] = DATAPATHS.RETREAT,
    ):
        # Load in all data
        insolation, ins_times = np.loadtxt(insolation_path, skiprows=1).T
        retreats = np.loadtxt(retreat_path).T

        # Trough angle
        self.angle = angle

        # Set up the trough model
        self.acc_model_name = acc_model_name
        self.lag_model_name = lag_model_name
        self.errorbar = errorbar
        self.meters_per_pixel = np.array([500.0, 20.0])  # meters per pixel

        # Positive times are now in the past
        ins_times = -ins_times

        # Attach data to this object
        self.insolation = insolation
        self.ins_times = ins_times
        self.retreats = retreats

        # Set range of lag values
        self.lags = np.arange(16) + 1
        self.lags[0] -= 1
        self.lags[-1] = 20

        # Create data splines of retreat of ice (no dependency
        # on model parameters)
        self.ret_data_spline = RBS(self.lags, self.ins_times, self.retreats)
        self.re2_data_spline = RBS(self.lags, self.ins_times, self.retreats ** 2)

        # Create submodels
        self.accuModel = ACCUMULATION_MODEL_MAP[self.acc_model_name](
            self.ins_times, self.insolation, *acc_params
        )
        self.lagModel = LAG_MODEL_MAP[self.lag_model_name](*lag_params)

        # Calculate model of lag per time
        self.lag_model_t = self.lagModel.get_lag_at_t(self.ins_times)

        # Calculate the model of retreat of ice per time
        self.retreat_model_t = self.get_retreat_model_t(
            self.lag_model_t, self.ins_times
        )

        # Compute splines of models of lag and retreat of ice per time
        self.compute_model_splines()

    def set_model(self, acc_params, lag_params, errorbar):
        """
        Updates trough model with new accumulation and lag parameters.
        Model number is kept the same for both acumulation and lag.
        Args:
            acc_params (list): Accumulation parameter(s) (same length
                                     as current acumulation parameter(s)).
            lag_params (list): Lag parameter(s) (same length
                                     as current lag parameter(s)).
            errorbar (float): Errorbar of the datapoints in pixels
        Output:
            None
        """
        # Set the new errorbar
        self.errorbar = errorbar

        # Update submodels
        self.accuModel.parameters = acc_params
        self.lagModel.parameters = lag_params

        # Update the model of lag at all times
        self.lag_model_t = self.lagModel.get_lag_at_t(self.ins_times)

        # Update the model of retreat of ice per time
        self.retreat_model_t = self.get_retreat_model_t(
            self.lag_model_t, self.ins_times
        )
        return

    def compute_model_splines(self):  # To be called after set_model
        """
        Computes splines of models of 1) lag per time and
        2) retreat of ice per time.
        Args:
            None
        Output:
            None
        """
        # spline of lag model per time
        self.lag_model_t_spline = IUS(self.ins_times, self.lag_model_t)
        # spline of retreat model of ice per time
        self.retreat_model_t_spline = IUS(self.ins_times, self.retreat_model_t)
        self.int_retreat_model_t_spline = (
            self.retreat_model_t_spline.antiderivative()
        )
        return

    def get_insolation(self, time):
        """
        Calculates the values of insolation (in W/m^2) per time.
        These values are obtained from splines of the
        times and insolation data in the Insolation.txt file.
        Args:
            time (np.ndarray): times at which we want to calculate the Insolation.
        Output:
            insolation values (np.ndarray) of the same size as time input
        """
        return self.ins_data_spline(time)

    def get_retreat_model_t(self, lag_t, time):
        """
        Calculates the values of retreat of ice per time (mm/year).
        These values are obtained by evaluating self.ret_data_spline using
        the lag_model_t and time values.
        Args:
            lag_t (np.ndarray): lag at time
            time (np.ndarray): times at which we want to calculate the retreat
        Output:
            retreat values (np.ndarray) of the same size as time input
        """
        return self.ret_data_spline.ev(lag_t, time)

    def get_trajectory(self, times: Optional[np.ndarray] = None):
        """
        Obtains the x and y coordinates (in m) of the trough model as a
        function of time.
        Args:
            times (Optional[np.ndarray]): if ``None``, default to the
                times of the observed solar insolation.
        Output:
            x and y coordinates (tuple) of size 2 x len(times) (in m).
        """
        if np.all(times) is None:
            times = self.ins_times

        int_retreat_model_t_spline = self.int_retreat_model_t_spline
        cot_angle = self.cot_angle
        csc_angle = self.csc_angle

        y = self.accuModel.get_yt(times)
        x = self.accuModel.get_xt(
            times, int_retreat_model_t_spline, cot_angle, csc_angle
        )

        return x, y

    @staticmethod
    def _L2_distance(x1, x2, y1, y2) -> Union[float, np.ndarray]:
        """
        The L2 (Eulerean) distance (squared) between two 2D vectors.
        Args:
            x1 (Union[float, np.ndarray]): x-coordinate of the first vector
            x2 (Union[float, np.ndarray]): x-coordinate of the second vector
            y1 (Union[float, np.ndarray]): y-coordinate of the first vector
            y2 (Union[float, np.ndarray]): y-coordinate of the second vector
        Output: L2 distance (int or float)
        """
        return (x1 - x2) ** 2 + (y1 - y2) ** 2

    def get_nearest_points(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        dist_func: Optional[Callable] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Finds the coordinates of the nearest points between the model TMP
        and the data TMP.
        Args:
            x_data (np.ndarray): x-coordinates of the data
            y_data (np.ndarray): y-coordinatse of the data
            dist_func (Optional[Callable]): function to compute distances,
                defaults to the L2 distance
                :meth:`mars_troughs.trough.Trough._L2_distance`
        Output:
            x and y coordinates of the model TMP that are closer to the data TMP.
            (Tuple), size 2 x len(x_data)
        """
        dist_func = dist_func or Trough._L2_distance
        x_model, y_model = self.get_trajectory()
        x_out = np.zeros_like(x_data)
        y_out = np.zeros_like(y_data)
        for i, (xdi, ydi) in enumerate(zip(x_data, y_data)):
            dist = dist_func(x_model, xdi, y_model, ydi)
            ind = np.argmin(dist)
            x_out[i] = x_model[ind]
            y_out[i] = y_model[ind]
        return x_out, y_out

    def lnlikelihood(self, x_data: np.ndarray, y_data: np.ndarray):
        """
        Calculates the log-likelihood of the data given the model.
        Note that this is the natural log (ln).
        Args:
            x_data (np.ndarray): x-coordinates of the trough path
            y_data (np.ndarray): y-coordinates of the trough path
        Output:
            log-likelihood value (float)
        """
        x_model, y_model = self.get_nearest_points(x_data, y_data)
        # Variance in meters in both directions
        xvar, yvar = (self.errorbar * self.meters_per_pixel) ** 2
        chi2 = (x_data - x_model) ** 2 / xvar + (y_data - y_model) ** 2 / yvar
        return -0.5 * chi2.sum() - 0.5 * len(x_data) * np.log(xvar * yvar)

    @property
    def angle(self) -> float:
        """
        Slope angle in degrees.
        """
        return self._angle * 180.0 / np.pi

    @angle.setter
    def angle(self, value: float) -> float:
        """Setter for the angle"""
        self._angle = value * np.pi / 180.0
        self._csc = 1.0 / np.sin(self._angle)
        self._cot = np.cos(self._angle) * self._csc

    @property
    def csc_angle(self) -> float:
        """
        Cosecant of the slope angle.
        """
        return self._csc

    @property
    def cot_angle(self) -> float:
        """
        Cotangent of the slope angle.
        """
        return self._cot
