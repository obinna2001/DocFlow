# def _fit_binary_calibrator(
#     raw_probs: np.ndarray, y_true: np.ndarray
# ) -> LogisticRegression | None:
#     """Fit a lightweight Platt-style calibrator; fallback to None if only one class exists.

#     Raw probabilities are often over/under-confident. Calibrated probabilities ensure that
#     the predicted probabilities better reflect the true likelihood of the positive class,
#     which can improve decision-making based on these probabilities."""
#     # If only one class is present in y_true, calibration is not possible
#     if np.unique(y_true).size < 2:
#         return None

#     # Fit logistic regression on the raw probabilities to calibrate them to true labels
#     calibrator = LogisticRegression(max_iter=1000, solver="lbfgs")
#     calibrator.fit(raw_probs.reshape(-1, 1), y_true)
#     return calibrator


# def train_classification_model(
#     X_train: pl.DataFrame | np.ndarray, y_train: np.ndarray
# ) -> dict[str, Any]:
#     """Train multi-label LightGBM classifier with Platt-style probability calibration.

#     Supports either a feature matrix (np.ndarray) or a feature DataFrame.
#     When a DataFrame contains `credit_count`, inverse-sqrt sample weighting is applied.
#     """
#     global FORMAL_CALIBRATOR, INFORMAL_CALIBRATOR

#     base_estimator = LGBMClassifier(
#         n_estimators=200,
#         learning_rate=0.05,
#         num_leaves=31,
#         random_state=RANDOM_SEED,
#         class_weight="balanced",
#         n_jobs=-1,
#     )
#     # Used to extend any single-output classifier to multi-label classification by fitting one
#     # binary classifier per label. One binary LightGBM per target label (formal, informal)
#     model = MultiOutputClassifier(base_estimator)

#     if isinstance(X_train, pl.DataFrame):
#         train_df = X_train
#         X_train_mat = train_df.to_numpy().astype(float)
#         has_credit_count = "credit_count" in train_df.columns
#     else:
#         train_df = None
#         X_train_mat = np.asarray(X_train, dtype=float)
#         has_credit_count = False

#     # Downweight long statements so high-volume accounts don't dominate the fit.
#     # Fall back to uniform weights when credit_count is unavailable (e.g., precomputed matrix input).
#     if has_credit_count:
#         assert train_df is not None
#         train_counts = train_df["credit_count"].to_numpy().astype(float)
#         sample_weight = 1.0 / np.sqrt(np.clip(train_counts, a_min=1.0, a_max=None))
#         sample_weight = sample_weight / sample_weight.mean()
#     else:
#         sample_weight = np.ones(X_train_mat.shape[0], dtype=float)

#     # Split train into fit + calibration subsets for probability calibration
#     X_fit, X_cal, y_fit, y_cal, w_fit, _ = train_test_split(
#         X_train_mat,
#         y_train,
#         sample_weight,
#         test_size=TEST_SIZE,
#         random_state=RANDOM_SEED,
#     )

#     model.fit(X_fit, y_fit, sample_weight=w_fit)

#     # Fit one calibrator per label using held-out calibration subset
#     with warnings.catch_warnings():
#         warnings.filterwarnings(
#             "ignore",
#             message="X does not have valid feature names, but LGBMClassifier was fitted with feature names",
#             category=UserWarning,
#         )
#         cal_formal_raw = model.estimators_[0].predict_proba(X_cal)[:, 1]
#         cal_informal_raw = model.estimators_[1].predict_proba(X_cal)[:, 1]
#     FORMAL_CALIBRATOR = _fit_binary_calibrator(cal_formal_raw, y_cal[:, 0])
#     INFORMAL_CALIBRATOR = _fit_binary_calibrator(cal_informal_raw, y_cal[:, 1])

#     return {"model": model}
