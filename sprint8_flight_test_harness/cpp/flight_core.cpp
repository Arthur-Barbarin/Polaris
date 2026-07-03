// flight_core.cpp - implementation. Direct port of vehicle.py + controller.py.
#include "flight_core.hpp"
#include <cmath>

namespace polaris_ft {

static inline double clip(double x, double lo, double hi) {
    return x < lo ? lo : (x > hi ? hi : x);
}

double wrap_pi(double a) {
    // Match numpy: (a + pi) % (2pi) - pi, with Python's non-negative modulo.
    const double twopi = 2.0 * M_PI;
    double m = std::fmod(a + M_PI, twopi);
    if (m < 0) m += twopi;      // Python % always returns sign of divisor
    return m - M_PI;
}

void derivatives(const State& s, const Control& c, double wn, double we,
                 const Airframe& af, const Actuator& act, double out[7]) {
    double phi_c = clip(c.phi_c, -af.phi_max, af.phi_max) * act.roll_eff;
    double gamma_c = clip(c.gamma_c, -af.gamma_max, af.gamma_max) * act.pitch_eff;
    double phi_dot = (phi_c - s.phi) / af.tau_phi;
    double gamma_dot = (gamma_c - s.gamma) / af.tau_gamma;

    double thr = clip(c.throttle, 0.0, 1.0) * act.thr_eff;
    double accel_cmd = (2.0 * thr - 1.0);
    accel_cmd *= (accel_cmd >= 0 ? af.accel_max : af.decel_max);
    double Va_dot = accel_cmd - (s.Va - af.Va_cruise) / af.tau_Va;

    double Va = s.Va < 1.0 ? 1.0 : s.Va;   // guard for psi_dot only
    double psi_dot = (G / Va) * std::tan(s.phi);

    double cg = std::cos(s.gamma);
    double va_n = s.Va * std::cos(s.psi) * cg;
    double va_e = s.Va * std::sin(s.psi) * cg;
    double va_d = s.Va * std::sin(s.gamma);

    out[0] = va_n + wn;   // pn_dot (ground frame)
    out[1] = va_e + we;   // pe_dot
    out[2] = va_d;        // h_dot
    out[3] = Va_dot;
    out[4] = psi_dot;
    out[5] = gamma_dot;
    out[6] = phi_dot;
}

static State add(const State& s, const double d[7], double k) {
    return State{ s.pn + k * d[0], s.pe + k * d[1], s.h + k * d[2],
                  s.Va + k * d[3], s.psi + k * d[4], s.gamma + k * d[5],
                  s.phi + k * d[6] };
}

State step_rk4(const State& s, const Control& c, const WindStep& w,
               double dt, const Airframe& af, const Actuator& act) {
    // Classic RK4: each k is evaluated from the ORIGINAL state s (not the
    // previous intermediate), matching vehicle.py exactly.
    double k1[7], k2[7], k3[7], k4[7];
    derivatives(s, c, w.wn_t, w.we_t, af, act, k1);
    State s2 = add(s, k1, dt / 2);
    derivatives(s2, c, w.wn_mid, w.we_mid, af, act, k2);
    State s3 = add(s, k2, dt / 2);
    derivatives(s3, c, w.wn_mid, w.we_mid, af, act, k3);
    State s4 = add(s, k3, dt);
    derivatives(s4, c, w.wn_end, w.we_end, af, act, k4);

    double incr[7];
    for (int i = 0; i < 7; ++i)
        incr[i] = (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) / 6.0;
    State nxt = add(s, incr, dt);

    nxt.Va = clip(nxt.Va, af.Va_min * 0.6, af.Va_max * 1.2);
    nxt.psi = wrap_pi(nxt.psi);
    nxt.phi = clip(nxt.phi, -af.phi_max, af.phi_max);
    nxt.gamma = clip(nxt.gamma, -af.gamma_max, af.gamma_max);
    return nxt;
}

// --- Guidance geometry (port of mission.py) ---
static double cross_track(double pn, double pe,
                          double fn, double fe, double tn, double te) {
    double pnv = tn - fn, pev = te - fe;
    double norm = std::sqrt(pnv * pnv + pev * pev);
    if (norm < 1e-6) return 0.0;
    double un = pnv / norm, ue = pev / norm;
    double normal_n = -ue, normal_e = un;   // left-normal
    double rn = pn - fn, re = pe - fe;
    return rn * normal_n + re * normal_e;
}

static double along_track(double pn, double pe,
                          double fn, double fe, double tn, double te) {
    double pnv = tn - fn, pev = te - fe;
    double norm2 = pnv * pnv + pev * pev;
    if (norm2 < 1e-6) return 1.0;
    double rn = pn - fn, re = pe - fe;
    return (rn * pnv + re * pev) / norm2;
}

ControlOut control(double pn, double pe, double h, double Va, double chi,
                   double dt, const double* legs, int n_wps, int leg_idx_in,
                   double int_V_in, double Va_cmd, const Gains& g,
                   const Airframe& af) {
    int n_legs = n_wps - 1;
    int leg = leg_idx_in;
    // _advance_leg
    while (leg < n_legs - 1) {
        double fn = legs[3 * leg], fe = legs[3 * leg + 1];
        double tn = legs[3 * (leg + 1)], te = legs[3 * (leg + 1) + 1];
        if (along_track(pn, pe, fn, fe, tn, te) >= 1.0) leg++;
        else break;
    }
    double fn = legs[3 * leg], fe = legs[3 * leg + 1];
    double tn = legs[3 * (leg + 1)], te = legs[3 * (leg + 1) + 1];
    double th = legs[3 * (leg + 1) + 2];   // to-waypoint altitude

    double e_xt = cross_track(pn, pe, fn, fe, tn, te);
    double chi_path = std::atan2(te - fe, tn - fn);
    double chi_c = chi_path - g.chi_inf * (2.0 / M_PI) * std::atan(g.k_path * e_xt);
    double course_err = wrap_pi(chi_c - chi);
    double phi_c = clip(g.k_chi * course_err, -af.phi_max, af.phi_max);

    double gamma_c = clip(g.k_h * (th - h), -af.gamma_max, af.gamma_max);

    double err_V = Va_cmd - Va;
    double int_V = int_V_in + err_V * dt;
    int_V = clip(int_V, -20.0, 20.0);
    double throttle = 0.5 + g.kp_V * err_V + g.ki_V * int_V;
    throttle = clip(throttle, 0.0, 1.0);

    return ControlOut{ Control{ phi_c, gamma_c, throttle }, leg, int_V };
}

}  // namespace polaris_ft
