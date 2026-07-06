// flight_core.hpp - reduced-order fixed-wing inner loop (dynamics + autopilot).
//
// This is the C++ port of polaris_ft/vehicle.py (derivatives + RK4 step) and
// polaris_ft/controller.py (cascaded autopilot command law) - the "inner loop"
// that on a real airframe runs deterministically at high rate on the flight
// controller. Math is a byte-for-byte port of the Python so the two backends
// produce identical trajectories (validated by tests/test_native_parity.py).
#pragma once

namespace polaris_ft {

constexpr double G = 9.80665;  // standard gravity [m/s^2]

struct Airframe {
    double Va_cruise, Va_min, Va_max, phi_max, gamma_max;
    double tau_phi, tau_gamma, thrust_accel_max, drag_coef;
};

struct State { double pn, pe, h, Va, psi, gamma, phi; };
struct Control { double phi_c, gamma_c, throttle; };
struct Actuator {
    double roll_authority, pitch_authority, thr_eff;
    double roll_rate_factor, pitch_rate_factor;
};
struct Gains { double k_path, chi_inf, k_chi, k_h, kp_V, ki_V; };

// Wind sampled at the three RK4 sub-times (t, t+dt/2, t+dt) so a time-varying
// gust reproduces the Python trajectory exactly.
struct WindStep { double wn_t, we_t, wn_mid, we_mid, wn_end, we_end; };

struct ControlOut { Control ctrl; int leg_idx; double int_V; };

double wrap_pi(double a);

void derivatives(const State& s, const Control& c, double wn, double we,
                 const Airframe& af, const Actuator& act, double out[7]);

State step_rk4(const State& s, const Control& c, const WindStep& w,
               double dt, const Airframe& af, const Actuator& act);

// Cascaded autopilot command. `legs` is a flattened [n, e, h] per waypoint
// (length 3*n_wps). Returns the control plus the advanced leg index and the
// updated airspeed integrator (the loop's only internal state).
ControlOut control(double pn, double pe, double h, double Va, double chi,
                   double dt, const double* legs, int n_wps, int leg_idx_in,
                   double int_V_in, double Va_cmd, const Gains& g,
                   const Airframe& af);

}  // namespace polaris_ft
