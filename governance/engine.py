IGNORED_POLICY_KEYS = {"version", "target", "role_permissions"}


def check_violation(metadata_log, metadata_policy):
    """
    Compare policy rules with log metadata.

    A violation is reported only when a policy key exists in the log metadata
    and its value does not match. Control keys such as "target" are ignored.
    """
    if not isinstance(metadata_log, dict) or not isinstance(metadata_policy, dict):
        return False

    for key, expected_value in metadata_policy.items():
        if key in IGNORED_POLICY_KEYS:
            continue

        if key not in metadata_log:
            # Skip non-present keys to avoid false positives for broad templates.
            continue

        actual_value = metadata_log.get(key)

        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
            if check_violation(actual_value, expected_value):
                return True
            continue

        if actual_value != expected_value:
            return True

    return False
