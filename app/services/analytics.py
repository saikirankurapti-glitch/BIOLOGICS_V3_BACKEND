import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import io
import base64

def log_logistic_model(x, top, bottom, ec50, hill_slope):
    """Four-parameter log-logistic model for dose-response curves."""
    return bottom + (top - bottom) / (1 + (x / ec50) ** hill_slope)

def calculate_ic50(concentrations, inhibition_values):
    """
    Fits dose-response data to calculate IC50 (pIC50).
    Input: concentrations (list of floats), inhibition (list 0 to 100)
    """
    try:
        # Initial guesses
        p0 = [max(inhibition_values), min(inhibition_values), np.median(concentrations), 1.0]
        
        # Curve fitting
        popt, _ = curve_fit(log_logistic_model, concentrations, inhibition_values, p0=p0, maxfev=10000)
        
        ic50_value = popt[2]
        pic50 = -np.log10(ic50_value * 1e-9) # Assuming concentrations in nM
        
        return {
            "ic50": round(ic50_value, 2),
            "pic50": round(pic50, 2),
            "params": {
                "top": round(popt[0], 2),
                "bottom": round(popt[1], 2),
                "hill_slope": round(popt[3], 2)
            }
        }
    except Exception as e:
        print(f"Error in IC50 fitting: {e}")
        return None

def generate_dose_response_plot(concentrations, inhibition_values, fit_results):
    """Generates a base64 encoded PNG plot for researchers."""
    plt.figure(figsize=(6, 4))
    plt.scatter(concentrations, inhibition_values, label="Raw Data")
    
    if fit_results:
        x_fit = np.logspace(np.log10(min(concentrations)), np.log10(max(concentrations)), 100)
        y_fit = log_logistic_model(x_fit, **fit_results["params"], ec50=fit_results["ic50"])
        plt.plot(x_fit, y_fit, color='red', label="Fit")
        plt.xscale('log')
    
    plt.xlabel('Concentration (nM)')
    plt.ylabel('% Inhibition')
    plt.title('Dose-Response Curve')
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.legend()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    return image_base64
