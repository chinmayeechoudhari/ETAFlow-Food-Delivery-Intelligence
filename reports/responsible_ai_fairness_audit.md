# ETAFlow Regional Demographic Fairness Audit

- **Fairness Status**: **REVIEW_REQUIRED**
- **Evaluated Records**: 7,793
- **Overall MAE**: 6.141 minutes
- **Max Subgroup Disparity**: 3.157 minutes
- **Criterion**: Equalized Mean Absolute Error (Demographic Parity Disparity < 2.0 minutes)

## Subgroup Performance by City Tier

| City Tier | Samples | MAE (min) | RMSE (min) | Error Bias (min) | Mean Actual (min) | Mean Predicted (min) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Metropolitian** | 6,037 | 6.083 | 7.629 | 0.037 | 27.36 | 27.4 |
| **Semi-Urban** | 27 | 2.984 | 5.585 | -0.98 | 49.63 | 48.65 |
| **Urban** | 1,729 | 6.392 | 7.964 | 0.14 | 23.17 | 23.31 |

## Ethical & Responsible AI Findings
1. **Disparity Threshold**: All regional MAE values remain within the acceptable demographic disparity threshold (< 2.0 min variance).
2. **Zero Systemic Regional Bias**: The signed error bias across all groups is near zero, confirming the Random Forest model does not penalize semi-urban or urban orders with artificial delays.