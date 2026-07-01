// cell_model.cpp - implementation of the 2nd-order Thevenin Li-ion cell.

#include "cell_model.hpp"
#include <algorithm>
#include <cmath>

namespace polaris {

namespace {
// 11-point OCV-SOC table for a generic NMC cell (V vs SOC in 0..1).
// Calibrated to ~3.7V nominal, 4.2V full, 2.75V empty.
constexpr std::array<double, 11> kOcvTable = {
    2.750, 3.250, 3.450, 3.560, 3.620, 3.700,
    3.770, 3.850, 3.930, 4.040, 4.200
};

double clamp01(double x) { return std::min(1.0, std::max(0.0, x)); }

double arrhenius(double k_ref, double Ea, double T_k, double T_ref_k) {
    // k(T) = k_ref * exp(Ea/R * (1/T - 1/T_ref))
    // Impedance INCREASES at colder T (smaller 1/T_ref - 1/T).
    return k_ref * std::exp((Ea / CellParams::R_gas) * (1.0 / T_k - 1.0 / T_ref_k));
}
} // namespace

double ocv_of_soc(double soc) {
    soc = clamp01(soc);
    double x = soc * (kOcvTable.size() - 1);
    int i = static_cast<int>(std::floor(x));
    int j = std::min(i + 1, static_cast<int>(kOcvTable.size()) - 1);
    double f = x - i;
    return kOcvTable[i] * (1.0 - f) + kOcvTable[j] * f;
}

double docv_dsoc(double soc) {
    // Finite-difference derivative against the table grid.
    const double step = 1.0 / (kOcvTable.size() - 1);
    double up = ocv_of_soc(std::min(1.0, soc + step));
    double dn = ocv_of_soc(std::max(0.0, soc - step));
    return (up - dn) / (2.0 * step);
}

ThéveninCell::ThéveninCell(const CellParams& p) : p_(p) {
    reset(1.0, p_.T_ref_k);
}

void ThéveninCell::reset(double soc0, double T_k) {
    s_.soc = clamp01(soc0);
    s_.v_rc1 = 0.0;
    s_.v_rc2 = 0.0;
    s_.T_k = T_k;
    s_.cycles_eq = 0.0;
    s_.time_s = 0.0;
    refresh_aging();
}

void ThéveninCell::set_temperature(double T_k) { s_.T_k = T_k; }

void ThéveninCell::set_fault(Fault f, double severity) {
    fault_ = f;
    fault_sev_ = std::max(0.0, severity);
}

void ThéveninCell::refresh_aging() {
    const double days = s_.time_s / 86400.0;
    // Faults accelerate cycle aging at characteristic rates:
    //   lithium plating       - irreversible Li loss to plating, ~3x fade
    //   SEI growth            - thicker SEI consumes cyclable Li, ~2.2x fade
    //   internal short        - self-discharge appears as extra capacity loss
    //   electrolyte depletion - active-material starvation, ~2.5x fade
    double fault_k = 1.0;
    double fault_r = 1.0;
    switch (fault_) {
        case Fault::LithiumPlating:        fault_k = 1.0 + 2.0 * fault_sev_; break;
        case Fault::SeiGrowth:             fault_k = 1.0 + 1.2 * fault_sev_; fault_r = 1.0 + 1.5 * fault_sev_; break;
        case Fault::InternalShort:         fault_k = 1.0 + 1.5 * fault_sev_; break;
        case Fault::ElectrolyteDepletion:  fault_k = 1.0 + 1.5 * fault_sev_; fault_r = 1.0 + 1.0 * fault_sev_; break;
        default: break;
    }
    double k_cyc_eff = p_.k_cyc * fault_k;
    double cap_loss = k_cyc_eff * std::sqrt(std::max(0.0, s_.cycles_eq))
                    + p_.k_cal * std::sqrt(std::max(0.0, days));
    s_.q_now_ah = p_.q_nom_ah * std::max(0.0, 1.0 - cap_loss);
    s_.r0_now = p_.R0_ref * (1.0 + p_.k_r_cyc * fault_r * s_.cycles_eq + p_.k_r_cal * days);
}

double ThéveninCell::r0_at(double T_k) const {
    double base = arrhenius(s_.r0_now, p_.Ea_R0, T_k, p_.T_ref_k);
    if (fault_ == Fault::InternalShort) {
        // Internal short LOWERS apparent R0 (parallel resistor path).
        base *= std::max(0.05, 1.0 - 0.6 * fault_sev_);
    }
    return base;
}
double ThéveninCell::r1_at(double T_k) const {
    double base = arrhenius(p_.R1_ref, p_.Ea_R1, T_k, p_.T_ref_k);
    if (fault_ == Fault::SeiGrowth) base *= (1.0 + 0.8 * fault_sev_);
    if (fault_ == Fault::LithiumPlating) base *= (1.0 + 0.5 * fault_sev_);
    return base;
}
double ThéveninCell::r2_at(double T_k) const {
    double base = arrhenius(p_.R2_ref, p_.Ea_R2, T_k, p_.T_ref_k);
    if (fault_ == Fault::ElectrolyteDepletion) base *= (1.0 + 1.5 * fault_sev_);
    return base;
}
double ThéveninCell::c1_at(double /*T_k*/) const { return p_.C1_ref; }
double ThéveninCell::c2_at(double /*T_k*/) const { return p_.C2_ref; }

double ThéveninCell::terminal_voltage(double current_a) const {
    double r0 = r0_at(s_.T_k);
    return ocv_of_soc(s_.soc) - s_.v_rc1 - s_.v_rc2 - current_a * r0;
}

double ThéveninCell::step(double current_a, double dt_s) {
    // SOC update with coulombic efficiency on charge.
    double eta = (current_a < 0.0) ? p_.eta_charge : 1.0;
    double q_as = s_.q_now_ah * 3600.0; // capacity in Coulombs
    s_.soc -= eta * current_a * dt_s / q_as;

    // Track equivalent full cycles by |I| dt / Q.
    s_.cycles_eq += std::abs(current_a) * dt_s / (2.0 * q_as); // /2 to count a full charge+discharge as one cycle
    s_.time_s += dt_s;

    // RC dynamics - backward Euler for unconditional stability.
    double R1 = r1_at(s_.T_k), C1 = c1_at(s_.T_k);
    double R2 = r2_at(s_.T_k), C2 = c2_at(s_.T_k);
    double a1 = dt_s / (R1 * C1);
    double a2 = dt_s / (R2 * C2);
    s_.v_rc1 = (s_.v_rc1 + (dt_s / C1) * current_a) / (1.0 + a1);
    s_.v_rc2 = (s_.v_rc2 + (dt_s / C2) * current_a) / (1.0 + a2);

    s_.soc = std::min(1.0, std::max(0.0, s_.soc));

    // Refresh aging-derived parameters every step (cheap).
    refresh_aging();

    double v_term = terminal_voltage(current_a);

    // Lithium plating manifests as anomalous voltage rebound during low-T charging.
    if (fault_ == Fault::LithiumPlating && current_a < 0.0 && s_.T_k < 288.0) {
        v_term -= 0.04 * fault_sev_;
    }
    return v_term;
}

} // namespace polaris
