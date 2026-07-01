// ekf_soc.hpp - Extended Kalman Filter for SOC, V_RC1, V_RC2 estimation.
//
// State x_k = [SOC, V_RC1, V_RC2]^T
// Process model linearised about current state. Measurement is terminal voltage
//   z_k = OCV(SOC) - V_RC1 - V_RC2 - I*R0
// so H = [dOCV/dSOC, -1, -1].
//
// Q and R are tuned for a 1 Hz sample rate.

#pragma once
#include "cell_model.hpp"
#include <array>

namespace polaris {

class EkfSoc {
public:
    // Process / measurement noise (variance, not std).
    EkfSoc(const CellParams& p,
           double q_soc = 1e-7,
           double q_v   = 1e-5,
           double r_meas = 5e-4);

    // Seed the filter with a (possibly noisy) initial SOC guess and large covariance.
    void initialise(double soc_guess, double covariance_soc = 0.05);

    // One filter step: feed in applied current (A, discharge positive),
    // measured terminal voltage (V), pack temperature (K), and dt (s).
    // Returns posterior SOC estimate.
    double step(double current_a, double v_measured, double T_k, double dt_s);

    double soc() const { return x_[0]; }
    double v_rc1() const { return x_[1]; }
    double v_rc2() const { return x_[2]; }
    double soc_variance() const { return P_[0][0]; }

private:
    CellParams p_;
    std::array<double, 3> x_{};
    std::array<std::array<double, 3>, 3> P_{};
    double q_soc_, q_v_, r_meas_;
};

} // namespace polaris
