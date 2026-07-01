// ekf_soc.cpp

#include "ekf_soc.hpp"
#include <cmath>

namespace polaris {

namespace {
double arrhenius(double k_ref, double Ea, double T_k, double T_ref_k) {
    return k_ref * std::exp((Ea / CellParams::R_gas) * (1.0 / T_k - 1.0 / T_ref_k));
}
}

EkfSoc::EkfSoc(const CellParams& p, double q_soc, double q_v, double r_meas)
    : p_(p), q_soc_(q_soc), q_v_(q_v), r_meas_(r_meas) {
    initialise(0.5);
}

void EkfSoc::initialise(double soc_guess, double covariance_soc) {
    x_ = {soc_guess, 0.0, 0.0};
    for (auto& row : P_) row.fill(0.0);
    P_[0][0] = covariance_soc;
    P_[1][1] = 0.01;
    P_[2][2] = 0.01;
}

double EkfSoc::step(double current_a, double v_measured, double T_k, double dt_s) {
    // --- Predict ---
    double R0 = arrhenius(p_.R0_ref, p_.Ea_R0, T_k, p_.T_ref_k);
    double R1 = arrhenius(p_.R1_ref, p_.Ea_R1, T_k, p_.T_ref_k);
    double R2 = arrhenius(p_.R2_ref, p_.Ea_R2, T_k, p_.T_ref_k);
    double C1 = p_.C1_ref;
    double C2 = p_.C2_ref;

    double q_as = p_.q_nom_ah * 3600.0;
    double eta  = (current_a < 0.0) ? p_.eta_charge : 1.0;

    // State transition
    double soc_pred = x_[0] - eta * current_a * dt_s / q_as;
    double a1 = dt_s / (R1 * C1), a2 = dt_s / (R2 * C2);
    double v1_pred = (x_[1] + (dt_s / C1) * current_a) / (1.0 + a1);
    double v2_pred = (x_[2] + (dt_s / C2) * current_a) / (1.0 + a2);

    // Jacobian F (linearised). SOC has no dependence on V1/V2 in the process;
    // V1, V2 each shrink toward 0 with factor 1/(1+a).
    double f11 = 1.0;
    double f22 = 1.0 / (1.0 + a1);
    double f33 = 1.0 / (1.0 + a2);

    // Covariance predict: P = F P F^T + Q (F is diagonal, so this is direct).
    double P00 = f11 * P_[0][0] * f11 + q_soc_;
    double P11 = f22 * P_[1][1] * f22 + q_v_;
    double P22 = f33 * P_[2][2] * f33 + q_v_;
    double P01 = f11 * P_[0][1] * f22;
    double P02 = f11 * P_[0][2] * f33;
    double P12 = f22 * P_[1][2] * f33;

    // --- Update ---
    double v_pred = ocv_of_soc(soc_pred) - v1_pred - v2_pred - current_a * R0;
    double y      = v_measured - v_pred;
    double h0     = docv_dsoc(soc_pred);
    double h1 = -1.0, h2 = -1.0;

    // S = H P H^T + R
    double S = h0 * (h0 * P00 + h1 * P01 + h2 * P02)
             + h1 * (h0 * P01 + h1 * P11 + h2 * P12)
             + h2 * (h0 * P02 + h1 * P12 + h2 * P22)
             + r_meas_;

    // K = P H^T / S
    double K0 = (h0 * P00 + h1 * P01 + h2 * P02) / S;
    double K1 = (h0 * P01 + h1 * P11 + h2 * P12) / S;
    double K2 = (h0 * P02 + h1 * P12 + h2 * P22) / S;

    x_[0] = soc_pred + K0 * y;
    x_[1] = v1_pred + K1 * y;
    x_[2] = v2_pred + K2 * y;

    // P = (I - K H) P
    double IKH00 = 1 - K0 * h0, IKH01 = -K0 * h1, IKH02 = -K0 * h2;
    double IKH10 =    -K1 * h0, IKH11 = 1 - K1 * h1, IKH12 = -K1 * h2;
    double IKH20 =    -K2 * h0, IKH21 = -K2 * h1, IKH22 = 1 - K2 * h2;

    double newP00 = IKH00 * P00 + IKH01 * P01 + IKH02 * P02;
    double newP11 = IKH10 * P01 + IKH11 * P11 + IKH12 * P12;
    double newP22 = IKH20 * P02 + IKH21 * P12 + IKH22 * P22;
    double newP01 = IKH00 * P01 + IKH01 * P11 + IKH02 * P12;
    double newP02 = IKH00 * P02 + IKH01 * P12 + IKH02 * P22;
    double newP12 = IKH10 * P02 + IKH11 * P12 + IKH12 * P22;

    // Force symmetry - the (I-KH)P form is not guaranteed symmetric in
    // finite precision, which causes the filter to drift over long runs.
    P_[0][0] = newP00; P_[1][1] = newP11; P_[2][2] = newP22;
    P_[0][1] = P_[1][0] = 0.5 * (newP01 + newP01);   // already by construction equal
    P_[0][2] = P_[2][0] = 0.5 * (newP02 + newP02);
    P_[1][2] = P_[2][1] = 0.5 * (newP12 + newP12);
    // Floor variances to avoid negative diagonals from round-off.
    if (P_[0][0] < 1e-12) P_[0][0] = 1e-12;
    if (P_[1][1] < 1e-12) P_[1][1] = 1e-12;
    if (P_[2][2] < 1e-12) P_[2][2] = 1e-12;

    // SOC must stay in [0, 1]
    if (x_[0] < 0.0) x_[0] = 0.0;
    if (x_[0] > 1.0) x_[0] = 1.0;

    return x_[0];
}

} // namespace polaris
