// cell_model.hpp - 2nd-order Thevenin equivalent circuit Li-ion cell model
//
// State vector x = [SOC, V_RC1, V_RC2]
//   dSOC/dt   = -eta * I / Q_now
//   dV_RC1/dt = -V_RC1 / (R1*C1) + I / C1
//   dV_RC2/dt = -V_RC2 / (R2*C2) + I / C2
// Terminal voltage:
//   V_term = OCV(SOC) - V_RC1 - V_RC2 - I*R0
//
// Sign convention: I > 0 on discharge (current leaving the +ve terminal).
//
// Parameters scale with temperature via Arrhenius and with aging.

#pragma once
#include <array>
#include <cstddef>

namespace polaris {

struct CellParams {
    // Nominal capacity at beginning-of-life (Ah)
    double q_nom_ah = 3.20;
    // Coulombic efficiency on charge (discharge assumed 1.0)
    double eta_charge = 0.995;
    // Reference temperature for parameter calibration (K)
    double T_ref_k = 298.15;
    // Arrhenius activation energies (J/mol) for each impedance element
    double Ea_R0 = 20000.0;
    double Ea_R1 = 35000.0;
    double Ea_R2 = 40000.0;
    // Impedance parameters at T_ref (Ohm, Ohm, F, Ohm, F)
    double R0_ref = 0.022;
    double R1_ref = 0.015;
    double C1_ref = 1800.0;
    double R2_ref = 0.030;
    double C2_ref = 18000.0;
    // Aging coefficients
    //   capacity loss: q_now = q_nom * (1 - k_cyc * sqrt(cycles) - k_cal * sqrt(time_s/86400))
    double k_cyc = 0.0030;     // per sqrt(cycle) - calibrated for accelerated test cycling
                               // (0.0030 is the value data/cycle_records.json was generated with;
                               //  see integration_campaign_2026-09 finding F1-1)
    double k_cal = 0.00015;    // per sqrt(day)
    //   internal resistance growth: R0(now) = R0_ref * (1 + k_r_cyc * cycles + k_r_cal * days)
    double k_r_cyc = 0.0008;   // value data/cycle_records.json was generated with (F1-1)
    double k_r_cal = 0.00010;
    // Voltage limits (V)
    double v_max = 4.20;
    double v_min = 2.75;
    // Universal gas constant J/(mol*K)
    static constexpr double R_gas = 8.314462618;
};

// Open-circuit voltage as a function of SOC, evaluated from a smoothed lookup.
double ocv_of_soc(double soc);
// dOCV/dSOC for the EKF Jacobian.
double docv_dsoc(double soc);

struct CellState {
    double soc;          // 0..1
    double v_rc1;        // V
    double v_rc2;        // V
    double T_k;          // K (cell temperature)
    double cycles_eq;    // equivalent full cycles
    double time_s;       // age in seconds
    double q_now_ah;     // present capacity (computed)
    double r0_now;       // present R0 (computed)
};

class ThéveninCell {
public:
    explicit ThéveninCell(const CellParams& p = CellParams{});

    void reset(double soc0, double T_k = 298.15);

    // Step the model forward by dt seconds at applied current I (A, discharge positive).
    // Updates state in place; returns terminal voltage (V).
    double step(double current_a, double dt_s);

    // Inject a sensed temperature (e.g. from a thermal model or test chamber).
    void set_temperature(double T_k);

    // Anomaly injection hooks - used to seed pathological behaviour for the triage layer.
    enum class Fault { None, InternalShort, LithiumPlating, SeiGrowth, ElectrolyteDepletion };
    void set_fault(Fault f, double severity = 1.0);

    // Accessors
    const CellState& state() const { return s_; }
    const CellParams& params() const { return p_; }

    // Present terminal voltage at zero current (i.e. OCV through impedance relaxation).
    double terminal_voltage(double current_a) const;

    // Recompute capacity and R0 from age/cycle counters.
    void refresh_aging();

private:
    CellParams p_;
    CellState s_{};
    Fault fault_ = Fault::None;
    double fault_sev_ = 0.0;

    double r0_at(double T_k) const;
    double r1_at(double T_k) const;
    double r2_at(double T_k) const;
    double c1_at(double T_k) const;
    double c2_at(double T_k) const;
};

} // namespace polaris
