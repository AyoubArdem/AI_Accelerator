import numpy as np
import scipy
from scipy.stats import ks_2samp, wasserstein_distance, chi2_contingency , entropy

def calculate_kl_divergence(p, q, num_bins=10):
    """Calculate KL Divergence between two distributions."""
    min_val = min(np.min(p), np.min(q))
    max_val = max(np.max(p), np.max(q))
    bins = np.linspace(min_val, max_val, num_bins)

    p_hist, _ = np.histogram(p, bins=bins, density=True)
    q_hist, _ = np.histogram(q, bins=bins, density=True)

    p_hist += 1e-10
    q_hist += 1e-10

    kl_div = scipy.stats.entropy(p_hist, q_hist)
    return kl_div

def calculate_wasserstein_distance(p, q):
    """Calculate Wasserstein Distance between two distributions."""
    return wasserstein_distance(p, q)

def calculate_ks_statistic(p, q):
    """Calculate Kolmogorov-Smirnov statistic between two distributions."""
    ks_stat, _ = ks_2samp(p, q)
    return ks_stat

def calculate_chi_square(p, q, num_bins=10):
    """Calculate Chi-Square statistic between two distributions."""
    min_val = min(np.min(p), np.min(q))
    max_val = max(np.max(p), np.max(q))
    bins = np.linspace(min_val, max_val, num_bins)

    p_hist, _ = np.histogram(p, bins=bins)
    q_hist, _ = np.histogram(q, bins=bins)

    chi2_stat, p_value, _, _ = chi2_contingency([p_hist, q_hist])
    return chi2_stat

    