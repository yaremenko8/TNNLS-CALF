"""
This module contains a generic interface for systems (environments) as well as concrete systems as realizations of the former

Remarks: 

- All vectors are treated as of type [n,]
- All buffers are treated as of type [L, n] where each row is a vector
- Buffers are updated from bottom to top

"""

import numpy as np
from numpy.random import randn

import rcognita.base
from rcognita import __utilities as utilities
from abc import ABC, abstractmethod
import rcognita.__utilities as utilities


class System(rcognita.base.RcognitaBase, ABC):
    """
     Interface class of dynamical systems a.k.a. environments.
     Concrete systems should be built upon this class.
     To design a concrete system: inherit this class, override:
         | :func:`~systems.system.compute_dynamics` :
         | right-hand side of system description (required)
         | :func:`~systems.system._compute_disturbance_dynamics` :
         | right-hand side of disturbance model (if necessary)
         | :func:`~systems.system._dynamic_control` :
         | right-hand side of controller dynamical model (if necessary)
         | :func:`~systems.system.out` :
         | system out (if not overridden, output is identical to state)

     Attributes
     ----------
     sys_type : : string
         Type of system by description:

         | ``diff_eqn`` : differential equation :math:`\mathcal D state = f(state, action, disturb)`
         | ``discr_fnc`` : difference equation :math:`state^+ = f(state, action, disturb)`
         | ``discr_prob`` :  by probability distribution :math:`X^+ \sim P_X(state^+| state, action, disturb)`

     where:

         | :math:`state` : state
         | :math:`action` : input
         | :math:`disturb` : disturbance

     The time variable ``time`` is commonly used by ODE solvers, and you shouldn't have it explicitly referenced in the definition, unless your system is non-autonomous.
     For the latter case, however, you already have the input and disturbance at your disposal.

     Parameters of the system are contained in ``pars`` attribute.

     dim_state, dim_input, dim_output, dim_disturb : : integer
         System dimensions
     pars : : list
         List of fixed parameters of the system
     action_bounds : : array of shape ``[dim_input, 2]``
         Box control constraints.
         First element in each row is the lower bound, the second - the upper bound.
         If empty, control is unconstrained (default)
     is_dynamic_controller : : 0 or 1
         If 1, the controller (a.k.a. agent) is considered as a part of the full state vector
     is_disturb : : 0 or 1
         If 0, no disturbance is fed into the system
     pars_disturb : : list
         Parameters of the disturbance model

    Each concrete system must realize ``System`` and define ``name`` attribute.

    """

    def __init__(
        self,
        sys_type: str,
        dim_state: int,
        dim_input: int,
        dim_output: int,
        dim_disturb: int,
        pars: list = None,
        is_dynamic_controller: bool = 0,
        is_disturb: bool = 0,
        pars_disturb: list = None,
    ):

        """
        Parameters
        ----------
        sys_type : : string
            Type of system by description:

            | ``diff_eqn`` : differential equation :math:`\mathcal D state = f(state, action, disturb)`
            | ``discr_fnc`` : difference equation :math:`state^+ = f(state, action, disturb)`
            | ``discr_prob`` :  by probability distribution :math:`X^+ \sim P_X(state^+| state, action, disturb)`

        where:

            | :math:`state` : state
            | :math:`action` : input
            | :math:`disturb` : disturbance

        The time variable ``time`` is commonly used by ODE solvers, and you shouldn't have it explicitly referenced in the definition, unless your system is non-autonomous.
        For the latter case, however, you already have the input and disturbance at your disposal.

        Parameters of the system are contained in ``pars`` attribute.

        dim_state, dim_input, dim_output, dim_disturb : : integer
            System dimensions
        pars : : list
            List of fixed parameters of the system
        action_bounds : : array of shape ``[dim_input, 2]``
            Box control constraints.
            First element in each row is the lower bound, the second - the upper bound.
            If empty, control is unconstrained (default)
        is_dynamic_controller : : 0 or 1
            If 1, the controller (a.k.a. agent) is considered as a part of the full state vector
        is_disturb : : 0 or 1
            If 0, no disturbance is fed into the system
        pars_disturb : : list
            Parameters of the disturbance model
        """

        self.sys_type = sys_type

        self.dim_state = dim_state
        self.dim_input = dim_input
        self.dim_output = dim_output
        self.dim_disturb = dim_disturb
        self.pars = pars
        self.is_dynamic_controller = is_dynamic_controller
        self.is_disturb = is_disturb
        self.pars_disturb = pars_disturb

        # Track system's state
        self.state = np.zeros(dim_state)

        # Current input (a.k.a. action)
        self.action = np.zeros(dim_input)

        if is_dynamic_controller:
            if is_disturb:
                self._dim_full_state = (
                    self.dim_state + self.dim_disturb + self.dim_input
                )
            else:
                self._dim_full_state = self.dim_state
        else:
            if is_disturb:
                self._dim_full_state = self.dim_state + self.dim_disturb
            else:
                self._dim_full_state = self.dim_state

    @abstractmethod
    def compute_dynamics(self, time, state, action, disturb):
        """
        Description of the system internal dynamics.
        Depending on the system type, may be either the right-hand side of the respective differential or difference equation, or a probability distribution.
        As a probability disitribution, ``compute_dynamics`` should return a number in :math:`[0,1]`

        """
        pass

    def _compute_disturbance_dynamics(self, time, disturb):
        """
        Dynamical disturbance model depending on the system type:

        | ``sys_type = "diff_eqn"`` : :math:`\mathcal D disturb = f_q(disturb)`
        | ``sys_type = "discr_fnc"`` : :math:`disturb^+ = f_q(disturb)`
        | ``sys_type = "discr_prob"`` : :math:`disturb^+ \sim P_Q(disturb^+|disturb)`

        """
        pass

    def _dynamic_control(self, time, action, observation):
        """
        Right-hand side of a dynamical controller. When ``is_dynamic_control=0``, the controller is considered static, which is to say that the control actions are
        computed immediately from the system's output.
        In case of a dynamical controller, the system's state vector effectively gets extended.
        Dynamical controllers have some advantages compared to the static ones.

        Depending on the system type, can be:

        | ``sys_type = "diff_eqn"`` : :math:`\mathcal D action = f_u(action, observation)`
        | ``sys_type = "discr_fnc"`` : :math:`action^+ = f_u(action, observation)`
        | ``sys_type = "discr_prob"`` : :math:`action^+ \sim P_U(action^+|action, observation)`

        """
        Daction = utilities.rc.zeros(self.dim_input)

        return Daction

    def out(self, state, time=None, action=None):

        """
        System output.
        This is commonly associated with signals that are measured in the system.
        Normally, output depends only on state ``state`` since no physical processes transmit input to output instantly.

        See also
        --------
        :func:`~systems.system.compute_dynamics`

        """
        # Trivial case: output identical to state
        observation = state
        return observation

    def receive_action(self, action):
        """
        Receive exogeneous control action to be fed into the system.
        This action is commonly computed by your controller (agent) using the system output :func:`~systems.system.out`.

        Parameters
        ----------
        action : : array of shape ``[dim_input, ]``
            Action

        """
        self.action = action

    def compute_closed_loop_rhs(self, time, state_full):
        """
        Right-hand side of the closed-loop system description.
        Combines everything into a single vector that corresponds to the right-hand side of the closed-loop system description for further use by simulators.

        Attributes
        ----------
        state_full : : vector
            Current closed-loop system state

        """

        rhs_full_state = utilities.rc.zeros(
            self._dim_full_state,
            prototype=(state, action),
        )

        state = state_full[0 : self.dim_state]

        if self.is_disturb:
            disturb = state_full[self.dim_state :]
        else:
            disturb = []

        if self.is_dynamic_controller:
            action = state_full[-self.dim_input :]
            observation = self.out(state)
            rhs_full_state[-self.dim_input :] = self._ctrlDyn(time, action, observation)
        else:
            # Fetch the control action stored in the system
            action = self.action

        rhs_full_state[0 : self.dim_state] = self.compute_dynamics(
            time, state, action, disturb
        )

        if self.is_disturb:
            rhs_full_state[self.dim_state :] = self._compute_disturbance_dynamics(
                time, disturb
            )

        # Track system's state
        self.state = state

        return rhs_full_state

    def get_state(self):
        return self.state

    def reset(self):
        pass


class SysKinematicPoint(System):
    """
    System class: mathematical pendulum

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "kinematic-point"

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )

        for i in range(utilities.rc.shape(action)[0]):
            Dstate[i] = action[i]

        return Dstate

    def out(self, state, time=None, action=None):
        return state


class SysInvertedPendulum(System):
    """
    System class: mathematical pendulum

    """

    # DEBUG ====================================
    # def __init__(self, *args, is_angle_overflow=True, **kwargs):
    # /DEBUG ===================================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "inverted-pendulum"

        if self.is_disturb:
            self.sigma_disturb = self.pars_disturb[0]
            self.mu_disturb = self.pars_disturb[1]
            self.tau_disturb = self.pars_disturb[2]

        self.time_old = 0
        self.integral_alpha = 0

        # DEBUG ====================================
        # self.is_angle_overflow = is_angle_overflow
        # /DEBUG ===================================

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )

        m, g, l = self.pars[0], self.pars[1], self.pars[2]

        Dstate[0] = state[1]
        Dstate[1] = g / l * utilities.rc.sin(state[0]) + action[0] / (m * l**2)

        return Dstate

    def out(self, state, time=None, action=None):

        # DEBUG ====================================
        # observation = utilities.rc.zeros(self.dim_output)
        # observation = state[:3] + measNoise  # <-- Measure only position and orientation
        # observation = state  # <-- Position, force and torque sensors on
        # if self.is_angle_overflow:
        #     delta = np.abs(np.pi - state[0])
        #     if state[0] > 0:
        #         if state[0] > np.pi:
        #             state = [-np.pi + delta, state[1]]
        #     else:
        #         if state[0] < -np.pi:
        #             state = [np.pi - delta, state[1]]
        # /DEBUG ===================================
        delta_time = time - self.time_old if time is not None else 0
        self.integral_alpha += delta_time * state[0]

        return state  # utilities.rc.array([state[0], self.integral_alpha, state[1]])

    def reset(self):
        self.time_old = 0
        self.integral_alpha = 0


class SysInvertedPendulumPD(SysInvertedPendulum):
    def out(self, state, time=None, action=None):

        return utilities.rc.array([state[0], 0, state[1]])

    def reset(self):
        self.time_old = 0
        self.integral_alpha = 0


class Sys3WRobot(System):
    """
    System class: 3-wheel robot with dynamical actuators.

    Description
    -----------
    Three-wheel robot with dynamical pushing force and steering torque (a.k.a. ENDI - extended non-holonomic double integrator) [[1]_]

    .. math::
        \\begin{array}{ll}
                        \dot x_с & = v \cos \\angle \\newline
                        \dot y_с & = v \sin \\angle \\newline
                        \dot \\angle & = \\omega \\newline
                        \dot v & = \\left( \\frac 1 m F + q_1 \\right) \\newline
                        \dot \\omega & = \\left( \\frac 1 I M + q_2 \\right)
        \\end{array}

    **Variables**

    | :math:`x_с` : state-coordinate [m]
    | :math:`y_с` : observation-coordinate [m]
    | :math:`\\angle` : turning angle [rad]
    | :math:`v` : speed [m/s]
    | :math:`\\omega` : revolution speed [rad/s]
    | :math:`F` : pushing force [N]
    | :math:`M` : steering torque [Nm]
    | :math:`m` : robot mass [kg]
    | :math:`I` : robot moment of inertia around vertical axis [kg m\ :sup:`2`]
    | :math:`disturb` : actuator disturbance (see :func:`~RLframe.system.disturbDyn`). Is zero if ``is_disturb = 0``

    :math:`state = [x_c, y_c, \\angle, v, \\omega]`

    :math:`action = [F, M]`

    ``pars`` = :math:`[m, I]`

    References
    ----------
    .. [1] W. Abbasi, F. urRehman, and I. Shah. “Backstepping based nonlinear adaptive control for the extended
        nonholonomic double integrator”. In: Kybernetika 53.4 (2017), pp. 578–594

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "3wrobot"

        if self.is_disturb:
            self.sigma_disturb = self.pars_disturb[0]
            self.mu_disturb = self.pars_disturb[1]
            self.tau_disturb = self.pars_disturb[2]

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )

        m, I = self.pars[0], self.pars[1]

        Dstate[0] = state[3] * utilities.rc.cos(state[2])
        Dstate[1] = state[3] * utilities.rc.sin(state[2])
        Dstate[2] = state[4]

        if self.is_disturb and (disturb != []):
            Dstate[3] = 1 / m * (action[0] + disturb[0])
            Dstate[4] = 1 / I * (action[1] + disturb[1])
        else:
            Dstate[3] = 1 / m * action[0]
            Dstate[4] = 1 / I * action[1]

        return Dstate

    def _compute_disturbance_dynamics(self, time, disturb):

        """
        Description
        -----------

        We use here a 1st-order stochastic linear system of the type

        .. math:: \mathrm d Q_t = - \\frac{1}{\\tau_disturb} \\left( Q_t \\mathrm d t + \\sigma_disturb ( \\mathrm d B_t + \\mu_disturb ) \\right) ,

        where :math:`B` is the standard Brownian motion, :math:`Q` is the stochastic process whose realization is :math:`disturb`, and
        :math:`\\tau_disturb, \\sigma_disturb, \\mu_disturb` are the time constant, standard deviation and mean, resp.

        ``pars_disturb = [sigma_disturb, mu_disturb, tau_disturb]``, with each being an array of shape ``[dim_disturb, ]``

        """

        Ddisturb = utilities.rc.zeros(self.dim_disturb, prototype=disturb)

        for k in range(0, self.dim_disturb):
            Ddisturb[k] = -self.tau_disturb[k] * (
                disturb[k] + self.sigma_disturb[k] * (randn() + self.mu_disturb[k])
            )

        return Ddisturb

    def out(self, state, time=None, action=None):

        # observation = utilities.rc.zeros(self.dim_output)
        # observation = state[:3] + measNoise # <-- Measure only position and orientation
        # observation = state  # <-- Position, force and torque sensors on
        return state


class Sys3WRobotNI(System):
    """
    System class: 3-wheel robot with static actuators (the NI - non-holonomic integrator).


    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "3wrobotNI"

        if self.is_disturb:
            self.sigma_disturb = self.pars_disturb[0]
            self.mu_disturb = self.pars_disturb[1]
            self.tau_disturb = self.pars_disturb[2]

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(self.dim_state, prototype=(state, action))

        if self.is_disturb and (disturb != []):
            Dstate[0] = action[0] * utilities.rc.cos(state[2]) + disturb[0]
            Dstate[1] = action[0] * utilities.rc.sin(state[2]) + disturb[0]
            Dstate[2] = action[1] + disturb[1]
        else:
            Dstate[0] = action[0] * utilities.rc.cos(state[2])
            Dstate[1] = action[0] * utilities.rc.sin(state[2])
            Dstate[2] = action[1]

        return Dstate

    def _compute_disturbance_dynamics(self, time, disturb):

        """ """
        Ddisturb = utilities.rc.zeros(self.dim_disturb)

        for k in range(0, self.dim_disturb):
            Ddisturb[k] = -self.tau_disturb[k] * (
                disturb[k] + self.sigma_disturb[k] * (randn() + self.mu_disturb[k])
            )

        return Ddisturb

    def out(self, state, time=None, action=None):

        return state


class System2Tank(System):
    """
    Two-tank system with nonlinearity.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "2tank"

    def compute_dynamics(self, time, state, action, disturb=None):

        tau1, tau2, K1, K2, K3 = self.pars

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )
        Dstate[0] = 1 / (tau1) * (-state[0] + K1 * action[0])
        Dstate[1] = 1 / (tau2) * (-state[1] + K2 * state[0] + K3 * state[1] ** 2)

        return Dstate

    def _compute_disturbance_dynamics(self, time, disturb):

        Ddisturb = utilities.rc.zeros(self.dim_disturb)

        return utilities.rc.array(Ddisturb)

    def out(self, observation, time=None, action=None):
        state = observation

        return state


class GridWorld(System):
    """
    A simple 2-dimensional grid world with five actions: left, right, up, down and do nothing.
    The action encoding rule is as follows: right, left, up, down, do nothing -> 0, 1, 2, 3, 4.

    """

    def __init__(self, dims, terminal_state):
        self.dims = dims
        self.terminal_state = terminal_state

    def compute_dynamics(self, current_state, action):
        if tuple(self.terminal_state) == tuple(current_state):
            return current_state
        if action == 0:
            if current_state[1] < self.dims[1] - 1:
                return (current_state[0], current_state[1] + 1)
        elif action == 2:
            if current_state[0] > 0:
                return (current_state[0] - 1, current_state[1])
        elif action == 1:
            if current_state[1] > 0:
                return (current_state[0], current_state[1] - 1)
        elif action == 3:
            if current_state[0] < self.dims[0] - 1:
                return (current_state[0] + 1, current_state[1])
        return current_state


class CartPole(System):
    """
    Cart pole system without friction. link:
    https://coneural.org/florian/papers/05_cart_pole.pdf

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "2wrobot"

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )

        m_c, m_p, g, l = self.pars
        theta = state[0]
        x = state[1]
        theta_dot = state[2]
        x_dot = state[3]

        Dstate[0] = theta_dot

        Dstate[1] = x_dot

        Dstate[2] = (
            (
                g * utilities.rc.sin(theta)
                - utilities.rc.cos(theta)
                * (action[0] + m_p * l * theta_dot**2 * utilities.rc.sin(theta))
                / (m_c + m_p)
            )
            / l
            / (4 / 3 - m_p * (utilities.rc.cos(theta) ** 2) / (m_c + m_p))
        )
        Dstate[3] = (
            action[0]
            + m_p
            * l
            * (
                theta_dot**2 * utilities.rc.sin(theta)
                - Dstate[0] * utilities.rc.cos(theta)
            )
        ) / (m_c + m_p)

        return Dstate

    def _compute_disturbance_dynamics(self, time, disturb):

        Ddisturb = utilities.rc.zeros(self.dim_disturb)

        return utilities.rc.array(Ddisturb)

    def out(self, state, time=None, action=None):
        theta = state[0]
        x = state[1]
        theta_dot = state[2]
        x_dot = state[3]

        theta_observed = theta - utilities.rc.floor(theta / (2 * np.pi)) * 2 * np.pi
        if theta_observed > np.pi:
            theta_observed = theta_observed - 2 * np.pi

        return utilities.rc.array([theta_observed, x, theta_dot, x_dot])


class LunarLander(System):
    """
    Lunar lander system. link:
    https://web.aeromech.usyd.edu.au/AMME3500/Course_documents/material/tutorials/Assignment%204%20Lunar%20Lander%20Solution.pdf

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "lander"
        self.a = 1
        self.r = 1
        self.sigma = 1
        self.state_cache = []
        self.is_landed = False

    def compute_dynamics(self, time, state, action, disturb=None):

        Dstate = utilities.rc.zeros(
            self.dim_state,
            prototype=(state, action),
        )

        m, J, g = self.pars

        F_g = m * g * utilities.rc.array([0, 1], prototype=Dstate)

        theta = state[2]
        x_dot = state[3]
        y_dot = state[4]
        theta_dot = state[5]

        left_support, right_support = self.compute_supports_geometry(state[:2], theta)
        # l_reaction = self.compute_reaction(state[:2], left_support)
        # r_reaction = self.compute_reaction(state[:2], right_support)

        F_l = action[0]
        F_t = action[1]

        # M_l = utilities.rc.cross(
        #     utilities.rc.concatenate(
        #         (left_support - state[:2], utilities.rc.array([0]))
        #     ),
        #     utilities.rc.concatenate((F_g, utilities.rc.array([0]))),
        # )[2] * utilities.rc.if_else(left_support[1] < 0, 1, 0)
        # M_r = utilities.rc.cross(
        #     utilities.rc.concatenate(
        #         (right_support - state[:2], utilities.rc.array([0]))
        #     ),
        #     utilities.rc.concatenate((F_g, utilities.rc.array([0]))),
        # )[2] * utilities.rc.if_else(right_support[1] < 0, 1, 0)

        Dstate[0] = x_dot

        Dstate[1] = y_dot

        Dstate[2] = theta_dot

        Dstate[3] = (
            1 / m * (F_l * utilities.rc.cos(theta) - F_t * utilities.rc.sin(theta))
        )

        Dstate[4] = (
            1 / m * (F_l * utilities.rc.sin(theta) + F_t * utilities.rc.cos(theta)) - g
        )

        # Dstate[5] = (4 * F_l + M_l + M_r) / J
        Dstate[5] = (4 * F_l) / J

        # Check if any of the two lander's supports touched the ground. If yes, freeze the state.
        self.is_landed = utilities.rc.if_else(
            left_support[1] <= 0, 1, 0
        ) * utilities.rc.if_else(right_support[1] <= 0, 1, 0)

        Dstate = Dstate * (1 - self.is_landed)

        return Dstate

    def _compute_disturbance_dynamics(self, time, disturb):

        Ddisturb = utilities.rc.zeros(self.dim_disturb)

        return utilities.rc.array(Ddisturb)

    def compute_supports_geometry(self, xi, theta):
        A = utilities.rc.zeros((2, 2), prototype=xi)
        xi_2 = utilities.rc.zeros(2, prototype=xi)
        xi_3 = utilities.rc.zeros(2, prototype=xi)

        A[0, 0] = utilities.rc.cos(theta)
        A[0, 1] = -utilities.rc.sin(theta)
        A[1, 0] = utilities.rc.sin(theta)
        A[1, 1] = utilities.rc.cos(theta)

        xi_2[0] = xi[0] - self.a
        xi_2[1] = xi[1] - self.r
        xi_3[0] = xi[0] + self.a
        xi_3[1] = xi[1] - self.r

        xi_2_d = xi_2 - xi
        xi_3_d = xi_3 - xi

        xi_2_d_rot = A @ xi_2_d
        xi_3_d_rot = A @ xi_3_d
        xi_2_new = xi + xi_2_d_rot
        xi_3_new = xi + xi_3_d_rot
        return xi_2_new, xi_3_new

    def compute_reaction(self, r, r_support):
        m, J, g = self.pars
        lvl = r_support[1]
        e = (r - r_support) / utilities.rc.sqrt(utilities.rc.norm_2(r - r_support))
        reaction = utilities.rc.if_else(
            lvl <= 0,
            e
            * utilities.rc.dot(e, m * g * utilities.rc.array([0, 1]))
            * lvl
            * self.sigma,
            utilities.rc.array([0.0, 0.0]),
        )
        return -reaction

    def out(self, state, time=None, action=None):
        # If landed, we artificially output the target as an indicator of episode end
        # state = utilities

        # (
        #     observation
        #     if not self.is_landed
        #     else utilities.rc.array([0, self.a, 0, 0, 0, 0])
        # )

        # return state * (1 - self.is_landed) + self.is_landed * utilities.rc.array(
        #     [0, self.a, 0, 0, 0, 0]
        # )
        # return utilities.rc.if_else(
        #     self.is_landed > 0, utilities.rc.array([0, self.a, 0, 0, 0, 0]), state
        # )
        # return state
        left_support, right_support = self.compute_supports_geometry(
            state[:2], state[2]
        )
        self.is_landed = utilities.rc.if_else(
            left_support[1] <= 0, 1, 0
        ) * utilities.rc.if_else(right_support[1] <= 0, 1, 0)
        return state * (1 - self.is_landed) + self.is_landed * utilities.rc.array(
            [0, self.a, 0, 0, 0, 0]
        )
