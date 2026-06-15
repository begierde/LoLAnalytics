FLEX_QUEUE_ID = 440
DEFAULT_PLATFORM_ROUTE = "jp1"
DEFAULT_REGIONAL_ROUTE = "asia"
DEFAULT_TIMEZONE = "UTC+08:00"
DEFAULT_RETENTION_DAYS = 365
DEFAULT_MONITOR_INTERVAL_MINUTES = 15
DEFAULT_SERVER = "JP"
DEFAULT_RANK_SCOPE = "challenger"
DEFAULT_LANGUAGE = "zh"

SERVERS = {
    "JP": {"label": "Japan", "platform": "jp1", "regional": "asia"},
    "KR": {"label": "Korea", "platform": "kr", "regional": "asia"},
    "NA": {"label": "North America", "platform": "na1", "regional": "americas"},
    "EUW": {"label": "Europe West", "platform": "euw1", "regional": "europe"},
    "EUNE": {"label": "Europe Nordic & East", "platform": "eun1", "regional": "europe"},
    "BR": {"label": "Brazil", "platform": "br1", "regional": "americas"},
    "LAN": {"label": "Latin America North", "platform": "la1", "regional": "americas"},
    "LAS": {"label": "Latin America South", "platform": "la2", "regional": "americas"},
    "OCE": {"label": "Oceania", "platform": "oc1", "regional": "sea"},
    "TR": {"label": "Turkey", "platform": "tr1", "regional": "europe"},
    "RU": {"label": "Russia", "platform": "ru", "regional": "europe"},
}

RANK_SCOPES = {
    "challenger": ["CHALLENGER"],
    "challenger_grandmaster": ["CHALLENGER", "GRANDMASTER"],
    "challenger_grandmaster_master": ["CHALLENGER", "GRANDMASTER", "MASTER"],
}

TIER_PRIORITY = {"CHALLENGER": 0, "GRANDMASTER": 1, "MASTER": 2}

TIMEZONES = [
    {"value": "UTC-12:00", "country": "United States"},
    {"value": "UTC-11:00", "country": "American Samoa"},
    {"value": "UTC-10:00", "country": "United States"},
    {"value": "UTC-09:30", "country": "French Polynesia"},
    {"value": "UTC-09:00", "country": "United States"},
    {"value": "UTC-08:00", "country": "United States"},
    {"value": "UTC-07:00", "country": "United States"},
    {"value": "UTC-06:00", "country": "Mexico"},
    {"value": "UTC-05:00", "country": "Colombia"},
    {"value": "UTC-04:00", "country": "Chile"},
    {"value": "UTC-03:30", "country": "Canada"},
    {"value": "UTC-03:00", "country": "Brazil"},
    {"value": "UTC-02:00", "country": "Brazil"},
    {"value": "UTC-01:00", "country": "Portugal"},
    {"value": "UTC", "country": "United Kingdom"},
    {"value": "UTC+01:00", "country": "Germany"},
    {"value": "UTC+02:00", "country": "South Africa"},
    {"value": "UTC+03:00", "country": "Saudi Arabia"},
    {"value": "UTC+03:30", "country": "Iran"},
    {"value": "UTC+04:00", "country": "United Arab Emirates"},
    {"value": "UTC+04:30", "country": "Afghanistan"},
    {"value": "UTC+05:00", "country": "Pakistan"},
    {"value": "UTC+05:30", "country": "India"},
    {"value": "UTC+05:45", "country": "Nepal"},
    {"value": "UTC+06:00", "country": "Bangladesh"},
    {"value": "UTC+06:30", "country": "Myanmar"},
    {"value": "UTC+07:00", "country": "Thailand"},
    {"value": "UTC+08:00", "country": "China"},
    {"value": "UTC+08:45", "country": "Australia"},
    {"value": "UTC+09:00", "country": "Japan"},
    {"value": "UTC+09:30", "country": "Australia"},
    {"value": "UTC+10:00", "country": "Australia"},
    {"value": "UTC+10:30", "country": "Australia"},
    {"value": "UTC+11:00", "country": "Solomon Islands"},
    {"value": "UTC+12:00", "country": "New Zealand"},
    {"value": "UTC+12:45", "country": "New Zealand"},
    {"value": "UTC+13:00", "country": "Samoa"},
    {"value": "UTC+14:00", "country": "Kiribati"},
]


def server_routes(server: str) -> dict[str, str]:
    key = server.upper()
    if key not in SERVERS:
        raise ValueError(f"Unsupported server: {server}")
    return SERVERS[key]


def rank_scope_tiers(rank_scope: str) -> list[str]:
    if rank_scope not in RANK_SCOPES:
        raise ValueError(f"Unsupported rank scope: {rank_scope}")
    return RANK_SCOPES[rank_scope]
