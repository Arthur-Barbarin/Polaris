// c_api.cpp - flat C ABI for ctypes consumers.
// All handles are opaque pointers; double* output buffers are caller-owned.

#include "cell_model.hpp"
#include "ekf_soc.hpp"
#include <cstring>
#include <new>

extern "C" {

// ---------- Cell handle ----------

void* polaris_cell_new() {
    return new (std::nothrow) polaris::ThéveninCell();
}

void polaris_cell_free(void* h) {
    delete static_cast<polaris::ThéveninCell*>(h);
}

void polaris_cell_reset(void* h, double soc0, double T_k) {
    static_cast<polaris::ThéveninCell*>(h)->reset(soc0, T_k);
}

double polaris_cell_step(void* h, double current_a, double dt_s) {
    return static_cast<polaris::ThéveninCell*>(h)->step(current_a, dt_s);
}

void polaris_cell_set_temperature(void* h, double T_k) {
    static_cast<polaris::ThéveninCell*>(h)->set_temperature(T_k);
}

void polaris_cell_set_fault(void* h, int fault, double severity) {
    using F = polaris::ThéveninCell::Fault;
    F f = F::None;
    switch (fault) {
        case 1: f = F::InternalShort; break;
        case 2: f = F::LithiumPlating; break;
        case 3: f = F::SeiGrowth; break;
        case 4: f = F::ElectrolyteDepletion; break;
        default: f = F::None;
    }
    static_cast<polaris::ThéveninCell*>(h)->set_fault(f, severity);
}

// State export: [soc, v_rc1, v_rc2, T_k, cycles_eq, time_s, q_now_ah, r0_now]
void polaris_cell_state(void* h, double* out8) {
    const auto& s = static_cast<polaris::ThéveninCell*>(h)->state();
    out8[0] = s.soc;
    out8[1] = s.v_rc1;
    out8[2] = s.v_rc2;
    out8[3] = s.T_k;
    out8[4] = s.cycles_eq;
    out8[5] = s.time_s;
    out8[6] = s.q_now_ah;
    out8[7] = s.r0_now;
}

double polaris_cell_terminal_voltage(void* h, double current_a) {
    return static_cast<polaris::ThéveninCell*>(h)->terminal_voltage(current_a);
}

double polaris_ocv_of_soc(double soc) {
    return polaris::ocv_of_soc(soc);
}

// ---------- EKF handle ----------

void* polaris_ekf_new() {
    return new (std::nothrow) polaris::EkfSoc(polaris::CellParams{});
}

void polaris_ekf_free(void* h) {
    delete static_cast<polaris::EkfSoc*>(h);
}

void polaris_ekf_init(void* h, double soc_guess, double cov_soc) {
    static_cast<polaris::EkfSoc*>(h)->initialise(soc_guess, cov_soc);
}

double polaris_ekf_step(void* h, double current_a, double v_meas, double T_k, double dt_s) {
    return static_cast<polaris::EkfSoc*>(h)->step(current_a, v_meas, T_k, dt_s);
}

double polaris_ekf_soc(void* h) {
    return static_cast<polaris::EkfSoc*>(h)->soc();
}

double polaris_ekf_soc_variance(void* h) {
    return static_cast<polaris::EkfSoc*>(h)->soc_variance();
}

} // extern "C"
