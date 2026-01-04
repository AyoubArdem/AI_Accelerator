def check_violation(metadata_log, metadata_policy):
    # Placeholder logic for checking violation
    
    for key, value in metadata_policy.items():
        if key not in metadata_log or metadata_log[key] != value:
            return True
    
    return False