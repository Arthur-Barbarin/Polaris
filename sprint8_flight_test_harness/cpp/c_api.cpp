// c_api.cpp - flat C ABI for ctypes consumers.
// Stateless: all state travels through caller-owned double buffers.
#include "flight_core.hpp"

using namespace polaris_ft;

static Airframe unpack_af(const double* a) {
    // [Va_cruise,Va_min,Va_max,phi_max,gamma_max,tau_phi,tau_gamma,
    //  thrust_accel_max,drag_coef]
    return Airframe{ a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8] };
}

extern "C" {

double ft_wrap_pi(double a) { return wrap_pi(a); }

// state7 = [pn,pe,h,Va,psi,gamma,phi]
// ctrl3  = [phi_c,gamma_c,throttle]
// wind6  = [wn_t,we_t, wn_mid,we_mid, wn_end,we_end]
// af9    = [Va_cruise,Va_min,Va_max,phi_max,gamma_max,tau_phi,tau_gamma,thrust_accel_max,drag_coef]
// act5   = [roll_authority,pitch_authority,thr_eff,roll_rate_factor,pitch_rate_factor]
// out7   = next state (same order as state7)
void ft_step(const double* state7, const double* ctrl3, const double* wind6,
             double dt, const double* af9, const double* act5, double* out7) {
    State s{ state7[0], state7[1], state7[2], state7[3],
             state7[4], state7[5], state7[6] };
    Control c{ ctrl3[0], ctrl3[1], ctrl3[2] };
    WindStep w{ wind6[0], wind6[1], wind6[2], wind6[3], wind6[4], wind6[5] };
    Actuator act{ act5[0], act5[1], act5[2], act5[3], act5[4] };
    State n = step_rk4(s, c, w, dt, unpack_af(af9), act);
    out7[0] = n.pn; out7[1] = n.pe; out7[2] = n.h; out7[3] = n.Va;
    out7[4] = n.psi; out7[5] = n.gamma; out7[6] = n.phi;
}

// legs   = flattened [n,e,h] per waypoint, length 3*n_wps
// gains6 = [k_path,chi_inf,k_chi,k_h,kp_V,ki_V]
// out5   = [phi_c,gamma_c,throttle, leg_idx, int_V]
void ft_control(double pn, double pe, double h, double Va, double chi, double dt,
                const double* legs, int n_wps, int leg_idx_in, double int_V_in,
                double Va_cmd, const double* gains6, const double* af10,
                double* out5) {
    Gains g{ gains6[0], gains6[1], gains6[2], gains6[3], gains6[4], gains6[5] };
    ControlOut r = control(pn, pe, h, Va, chi, dt, legs, n_wps, leg_idx_in,
                           int_V_in, Va_cmd, g, unpack_af(af10));
    out5[0] = r.ctrl.phi_c;
    out5[1] = r.ctrl.gamma_c;
    out5[2] = r.ctrl.throttle;
    out5[3] = static_cast<double>(r.leg_idx);
    out5[4] = r.int_V;
}

}  // extern "C"
