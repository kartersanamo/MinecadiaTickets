def seconds_to_format(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if days:
        time_parts.append(f"{days}d")
    if hours:
        time_parts.append(f"{hours}h")
    if minutes:
        time_parts.append(f"{minutes}m")
    time_parts.append(f"{seconds}s")
    return " ".join(time_parts)
