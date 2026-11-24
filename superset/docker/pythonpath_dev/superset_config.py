# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Minimal Docker configuration restored to Superset defaults.
# Data-preserving note: SECRET_KEY is intentionally kept from the
# existing deployment so encrypted metadata/database passwords remain readable.

import logging
import os
from typing import Optional

from cachelib.file import FileSystemCache

logger = logging.getLogger()


def get_env_variable(var_name: str, default: Optional[str] = None) -> str:
    """Get the environment variable or raise exception."""
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not None:
            return default
        error_msg = "The environment variable {} was missing, abort...".format(var_name)
        raise EnvironmentError(error_msg)


DATABASE_DIALECT = get_env_variable("DATABASE_DIALECT")
DATABASE_USER = get_env_variable("DATABASE_USER")
DATABASE_PASSWORD = get_env_variable("DATABASE_PASSWORD")
DATABASE_HOST = get_env_variable("DATABASE_HOST")
DATABASE_PORT = get_env_variable("DATABASE_PORT")
DATABASE_DB = get_env_variable("DATABASE_DB")

SQLALCHEMY_DATABASE_URI = "%s://%s:%s@%s:%s/%s" % (
    DATABASE_DIALECT,
    DATABASE_USER,
    DATABASE_PASSWORD,
    DATABASE_HOST,
    DATABASE_PORT,
    DATABASE_DB,
)

REDIS_HOST = get_env_variable("REDIS_HOST")
REDIS_PORT = get_env_variable("REDIS_PORT")
REDIS_CELERY_DB = get_env_variable("REDIS_CELERY_DB", "0")
REDIS_RESULTS_DB = get_env_variable("REDIS_RESULTS_DB", "1")

RESULTS_BACKEND = FileSystemCache("/app/superset_home/sqllab")


class CeleryConfig(object):
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    imports = ("superset.sql_lab", "superset.tasks")
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    worker_prefetch_multiplier = 1
    task_acks_late = False

    # Backward-compatible names used by some Superset/Celery versions.
    BROKER_URL = broker_url
    CELERY_IMPORTS = imports
    CELERY_RESULT_BACKEND = result_backend
    CELERYD_PREFETCH_MULTIPLIER = worker_prefetch_multiplier
    CELERY_ACKS_LATE = task_acks_late


CELERY_CONFIG = CeleryConfig

# Keep existing key to preserve encrypted metadata (database passwords, etc.).
SECRET_KEY = get_env_variable("SUPERSET_SECRET_KEY", "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_BASE64_42")
PREVIOUS_SECRET_KEY = os.environ.get("SUPERSET_PREVIOUS_SECRET_KEY")

# Optionally import superset_config_docker.py if present on PYTHONPATH.
# No custom UI/theme/CSS/feature overrides are defined here.
try:
    import superset_config_docker
    from superset_config_docker import *  # noqa

    logger.info(f"Loaded your Docker configuration at [{superset_config_docker.__file__}]")
except ImportError:
    logger.info("Using default Docker config...")

# Superset/Flask-Talisman iframe policy for dashboard embedding.
try:
    from superset.config import TALISMAN_CONFIG as _DEFAULT_TALISMAN_CONFIG
except Exception:
    _DEFAULT_TALISMAN_CONFIG = {}

EMBED_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in get_env_variable("SUPERSET_EMBED_ALLOWED_ORIGINS", "'self'")
    .replace(",", " ")
    .split()
    if origin.strip()
] or ["'self'"]

FRAME_SRC_ORIGINS = [
    origin.strip()
    for origin in get_env_variable("SUPERSET_FRAME_SRC", "'self' blob: data:")
    .replace(",", " ")
    .split()
    if origin.strip()
] or ["'self'", "blob:", "data:"]

TALISMAN_ENABLED = True
TALISMAN_CONFIG = dict(_DEFAULT_TALISMAN_CONFIG)
TALISMAN_CONFIG["content_security_policy"] = dict(
    _DEFAULT_TALISMAN_CONFIG.get("content_security_policy", {})
)
TALISMAN_CONFIG["content_security_policy"]["frame-ancestors"] = EMBED_ALLOWED_ORIGINS
TALISMAN_CONFIG["content_security_policy"]["frame-src"] = FRAME_SRC_ORIGINS
TALISMAN_CONFIG["frame_options"] = None

# Required for Superset authentication/session cookies inside a cross-site iframe.
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
ENABLE_PROXY_FIX = True


# Allow dashboards to be embedded by origins listed in SUPERSET_EMBED_ALLOWED_ORIGINS.
# Browser iframe enforcement uses CSP frame-ancestors and X-Frame-Options.
def _allow_configured_iframe_embedding(response):
    # X-Frame-Options SAMEORIGIN blocks cross-origin iframe embedding.
    response.headers.pop("X-Frame-Options", None)

    csp = response.headers.get("Content-Security-Policy", "")
    frame_ancestors = "frame-ancestors " + " ".join(EMBED_ALLOWED_ORIGINS)
    if csp:
        directives = [d.strip() for d in csp.split(";") if d.strip()]
        replaced = False
        for idx, directive in enumerate(directives):
            if directive.lower().startswith("frame-ancestors"):
                directives[idx] = frame_ancestors
                replaced = True
                break
        if not replaced:
            directives.append(frame_ancestors)
        response.headers["Content-Security-Policy"] = "; ".join(directives)
    else:
        response.headers["Content-Security-Policy"] = frame_ancestors

    return response

# Custom loading text frontend asset cache-buster and runtime text fallback.
# Forces browsers/CDN to fetch patched frontend assets and also replaces old cached
# loading labels in the DOM with Waiting Load Data.
FRONTEND_ASSET_VERSION = "civic-dual-v3-20261124-1"
FRONTEND_ASSETS_TO_BUST = [
    "/static/assets/spa.75f58c053056fc51f1b6.entry.js",
    "/static/assets/embedded.ca778c9454042915ed9e.entry.js",
    "/static/assets/7e6e5031a28b6756a45f.chunk.js",
    "/static/assets/9059.b2f889ad23bd80f99e2a.entry.js",
]
LOADING_TEXT_REPLACER = '\n<script id="waiting-load-data-text-replacer">\n(function () {\n  function replaceWaitingText(root) {\n    try {\n      var walker = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT);\n      var nodes = [];\n      while (walker.nextNode()) nodes.push(walker.currentNode);\n      nodes.forEach(function (node) {\n        var text = node.nodeValue || \'\';\n        if (/Waiting on\\s+.+/i.test(text) || /Waiting on database\\.\\.\\./i.test(text)) {\n          node.nodeValue = \'Waiting Load Data\';\n        }\n      });\n    } catch (e) {}\n  }\n  function start() {\n    replaceWaitingText(document.body);\n    var observer = new MutationObserver(function (mutations) {\n      mutations.forEach(function (mutation) {\n        if (mutation.type === \'characterData\') {\n          replaceWaitingText(mutation.target.parentNode || document.body);\n        }\n        mutation.addedNodes && mutation.addedNodes.forEach(function (node) {\n          replaceWaitingText(node.nodeType === 1 ? node : document.body);\n        });\n      });\n    });\n    observer.observe(document.body, { childList: true, subtree: true, characterData: true });\n    setInterval(function () { replaceWaitingText(document.body); }, 500);\n  }\n  if (document.readyState === \'loading\') document.addEventListener(\'DOMContentLoaded\', start);\n  else start();\n})();\n</script>\n'


def FLASK_APP_MUTATOR(app):
    app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True, ENABLE_PROXY_FIX=True)
    @app.after_request
    def add_frontend_asset_cachebuster_and_loading_text_replacer(response):
        response = _allow_configured_iframe_embedding(response)
        if not (response.content_type or "").startswith("text/html"):
            return response
        if response.direct_passthrough:
            return response
        body = response.get_data(as_text=True)
        changed = False
        for asset in FRONTEND_ASSETS_TO_BUST:
            versioned = f"{asset}?v={FRONTEND_ASSET_VERSION}"
            if asset in body and versioned not in body:
                body = body.replace(asset, versioned)
                changed = True
        if "waiting-load-data-text-replacer" not in body and "</body>" in body:
            body = body.replace("</body>", f"{LOADING_TEXT_REPLACER}</body>")
            changed = True
        if changed:
            response.set_data(body)
            response.headers["Content-Length"] = str(len(body.encode("utf-8")))
        return response

# Indonesian Rupiah (IDR) and Locale Configuration
CURRENCIES = ['IDR', 'USD', 'EUR', 'GBP', 'INR', 'MXN', 'JPY', 'CNY']
D3_FORMAT = {
    'decimal': ',',
    'thousands': '.',
    'grouping': [3],
    'currency': ['Rp ', '']
}

# ==============================================================================
# Custom Executive Branding & Modern UI Tokens (Configurable via Environment)
# ==============================================================================
APP_NAME = get_env_variable("SUPERSET_APP_NAME", "Executive Analytics")
APP_ICON = get_env_variable(
    "SUPERSET_APP_ICON", "/static/assets/images/favicon.png"
)
APP_ICON_WIDTH = int(get_env_variable("SUPERSET_APP_ICON_WIDTH", "135"))
LOGO_TARGET_PATH = get_env_variable("SUPERSET_LOGO_TARGET_PATH", "/superset/welcome/")
LOGO_TOOLTIP = get_env_variable(
    "SUPERSET_LOGO_TOOLTIP", f"{APP_NAME} - Executive Analytics"
)
LOGO_RIGHT_TEXT = get_env_variable("SUPERSET_LOGO_RIGHT_TEXT", APP_NAME)
FAVICON_URL = get_env_variable(
    "SUPERSET_FAVICON_URL", "/static/assets/images/favicon.png"
)
_FAVICON_TYPE = (
    "image/svg+xml"
    if FAVICON_URL.lower().endswith(".svg")
    else "image/x-icon"
    if FAVICON_URL.lower().endswith(".ico")
    else "image/webp"
    if FAVICON_URL.lower().endswith(".webp")
    else "image/png"
)

FAVICONS = [
    {
        "href": FAVICON_URL,
        "type": _FAVICON_TYPE,
    }
]

# Global Default Categorical Palette for all drag-and-drop charts
EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "executive_modern",
        "description": "Skema Warna Eksekutif Modern Civic Dual-Mode",
        "label": "Executive Modern",
        "isDefault": True,
        "colors": [
            "#0f2a4a",  # Deep Slate Navy
            "#10b981",  # Emerald Green
            "#f59e0b",  # Amber Gold
            "#2563eb",  # Royal Blue
            "#6366f1",  # Indigo
            "#06b6d4",  # Cyan
            "#8b5cf6",  # Violet
            "#ec4899",  # Rose
            "#64748b",  # Slate Muted
            "#d97706",  # Ochre Gold
        ],
    }
]

THEME_FONT_URL_ALLOWED_DOMAINS = ["fonts.googleapis.com", "fonts.gstatic.com"]

# Modern Interactive Feature Flags
FEATURE_FLAGS = {
    "DRILL_TO_DETAIL": True,
    "DRILL_BY": True,
    "DASHBOARD_VIRTUALIZATION": False,
    "EMBEDDABLE_CHARTS": True,
    "EMBEDDED_SUPERSET": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_RBAC": True,
    "TAGGING_SYSTEM": True,
    "AVOID_COLORS_COLLISION": True,
    "ALERT_REPORTS": True,
    "ALERT_REPORT_TABS": True,
    "ALERT_REPORT_WEBHOOK": True,
    "ALERTS_ATTACH_REPORTS": True,
}

# Automated Alerts & Reports Settings
ALERT_REPORTS_DEFAULT_WORKING_TIMEOUT = 3600
ALERT_REPORTS_DEFAULT_RETENTION = 14
ALERT_REPORTS_NOTIFICATION_METHODS = ["Email", "Webhook"]


# ==============================================================================
# Multi-Tier Redis Caching Configuration
# ==============================================================================
REDIS_CACHE_KEY_PREFIX = "superset_cache_"

# 1. Dashboard & Chart Query Cache (Redis DB 2, TTL 24 Jam)
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_query_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 2,
    "CACHE_REDIS_URL": f"redis://{REDIS_HOST}:{REDIS_PORT}/2",
}

# 2. Raw Table & Chart Data Cache (Redis DB 3, TTL 2 Jam)
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 7200,
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 3,
    "CACHE_REDIS_URL": f"redis://{REDIS_HOST}:{REDIS_PORT}/3",
}

# 3. Filter State & Form Data Cache (Redis DB 4, TTL 7 Hari)
FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400 * 7,
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_URL": f"redis://{REDIS_HOST}:{REDIS_PORT}/4",
}

EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400 * 7,
    "CACHE_KEY_PREFIX": "superset_form_",
    "CACHE_REDIS_URL": f"redis://{REDIS_HOST}:{REDIS_PORT}/4",
}

# 4. Distributed Rate Limiter Storage via Redis DB 0
RATELIMIT_STORAGE_URI = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Izinkan render elemen HTML/Iframe pada komponen Markdown Dashboard
HTML_SANITIZATION = False
HTML_SANITIZATION_SCHEMA_EXTENSIONS = {
    "attributes": {
        "*": ["style", "className", "class", "id"],
        "iframe": [
            "src",
            "width",
            "height",
            "frameborder",
            "allow",
            "allowfullscreen",
            "style",
            "loading",
        ],
        "video": ["src", "controls", "autoplay", "muted", "loop", "width", "height", "style"],
        "source": ["src", "type"],
    },
    "tagNames": [
        "iframe",
        "video",
        "source",
    ],
}


# Modern Civic Dual-Mode v3 & ECharts Global Presets (2026-11-24)
_ECHARTS_COMMON_ANIMATION = {
    "animation": True,
    "animationDuration": 550,
    "animationEasing": "cubicOut",
    "animationDurationUpdate": 350,
    "animationEasingUpdate": "cubicInOut",
}


def _build_echarts_by_chart_type(is_dark: bool) -> dict:
    border_surface = "#101b2e" if is_dark else "#ffffff"
    split_line = "rgba(148, 163, 184, 0.14)" if is_dark else "rgba(15, 23, 42, 0.08)"
    axis_label = "#cbd5e1" if is_dark else "#334155"
    shadow_color = "rgba(2, 6, 23, 0.45)" if is_dark else "rgba(15, 42, 74, 0.18)"

    cartesian_axes = {
        "grid": {"top": 40, "right": 20, "bottom": 36, "left": 20, "containLabel": True},
        "xAxis": {
            "axisLabel": {"color": axis_label, "fontSize": 11},
            "axisLine": {"lineStyle": {"color": split_line}},
        },
        "yAxis": {
            "axisLabel": {"color": axis_label, "fontSize": 11},
            "splitLine": {"lineStyle": {"color": split_line, "type": "dashed"}},
        },
    }

    return {
        "echarts_timeseries_bar": {
            **cartesian_axes,
            "series": {
                "barMaxWidth": 42,
                "emphasis": {
                    "focus": "series",
                    "itemStyle": {"shadowBlur": 12, "shadowColor": shadow_color},
                },
            },
        },
        "echarts_timeseries_line": {
            **cartesian_axes,
            "series": {
                "smooth": 0.25,
                "showSymbol": True,
                "symbolSize": 6,
                "lineStyle": {"width": 2.75},
                "areaStyle": {"opacity": 0.14 if is_dark else 0.10},
                "emphasis": {"focus": "series", "scale": True},
            },
        },
        "echarts_timeseries_smooth": {
            **cartesian_axes,
            "series": {
                "smooth": 0.35,
                "symbolSize": 6,
                "lineStyle": {"width": 2.75},
                "areaStyle": {"opacity": 0.16 if is_dark else 0.11},
                "emphasis": {"focus": "series"},
            },
        },
        "echarts_area": {
            **cartesian_axes,
            "series": {
                "smooth": 0.25,
                "lineStyle": {"width": 2.5},
                "areaStyle": {"opacity": 0.24 if is_dark else 0.18},
                "emphasis": {"focus": "series"},
            },
        },
        "mixed_timeseries": {
            **cartesian_axes,
            "series": {
                "emphasis": {"focus": "series"},
            },
        },
        "pie": {
            "series": {
                "itemStyle": {
                    "borderRadius": 6,
                    "borderColor": border_surface,
                    "borderWidth": 2,
                },
                "emphasis": {
                    "scale": True,
                    "scaleSize": 6,
                    "itemStyle": {"shadowBlur": 14, "shadowColor": shadow_color},
                },
            },
        },
        "treemap_v2": {
            "series": {
                "itemStyle": {
                    "borderRadius": 6,
                    "gapWidth": 2,
                    "borderColor": border_surface,
                },
            },
        },
    }


THEME_DEFAULT = {
    "algorithm": "default",
    "token": {
        "brandAppName": APP_NAME,
        "brandLogoAlt": APP_NAME,
        "brandLogoUrl": APP_ICON,
        "brandLogoMargin": "10px 0",
        "brandLogoHref": "/superset/welcome/",
        "brandLogoHeight": "32px",
        "colorPrimary": "#1d4ed8",
        "colorLink": "#1d4ed8",
        "colorSuccess": "#047857",
        "colorWarning": "#b45309",
        "colorError": "#b91c1c",
        "colorInfo": "#0369a1",
        "colorBgBase": "#f3f6fa",
        "colorBgLayout": "#f3f6fa",
        "colorBgContainer": "#ffffff",
        "colorBgElevated": "#ffffff",
        "colorText": "#0f172a",
        "colorTextSecondary": "#334155",
        "colorTextTertiary": "#475569",
        "colorBorder": "#dbe3ee",
        "colorBorderSecondary": "#e2e8f0",
        "borderRadius": 10,
        "fontFamily": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "fontUrls": [
            "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
        ],
        "echartsOptionsOverrides": {
            **_ECHARTS_COMMON_ANIMATION,
            "tooltip": {
                "backgroundColor": "rgba(15, 23, 42, 0.95)",
                "borderColor": "rgba(193, 206, 222, 0.28)",
                "borderWidth": 1,
                "borderRadius": 8,
                "padding": [10, 14],
                "textStyle": {
                    "color": "#f8fafc",
                    "fontSize": 12,
                    "fontFamily": "'Plus Jakarta Sans', sans-serif",
                },
                "extraCssText": "box-shadow: 0 10px 26px rgba(15, 42, 74, 0.25);",
            },
        },
        "echartsOptionsOverridesByChartType": _build_echarts_by_chart_type(is_dark=False),
    },
}

THEME_DARK = {
    "algorithm": "dark",
    "token": {
        "brandAppName": APP_NAME,
        "brandLogoAlt": APP_NAME,
        "brandLogoUrl": APP_ICON,
        "brandLogoMargin": "10px 0",
        "brandLogoHref": "/superset/welcome/",
        "brandLogoHeight": "32px",
        "colorPrimary": "#60a5fa",
        "colorLink": "#93c5fd",
        "colorSuccess": "#34d399",
        "colorWarning": "#fbbf24",
        "colorError": "#f87171",
        "colorInfo": "#38bdf8",
        "colorBgBase": "#08101d",
        "colorBgLayout": "#08101d",
        "colorBgContainer": "#101b2e",
        "colorBgElevated": "#16243b",
        "colorText": "#f1f5f9",
        "colorTextSecondary": "#cbd5e1",
        "colorTextTertiary": "#94a3b8",
        "colorBorder": "#203149",
        "colorBorderSecondary": "#314661",
        "borderRadius": 10,
        "fontFamily": "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "fontUrls": [
            "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
        ],
        "echartsOptionsOverrides": {
            **_ECHARTS_COMMON_ANIMATION,
            "tooltip": {
                "backgroundColor": "rgba(8, 16, 29, 0.96)",
                "borderColor": "rgba(148, 163, 184, 0.30)",
                "borderWidth": 1,
                "borderRadius": 8,
                "padding": [10, 14],
                "textStyle": {
                    "color": "#f1f5f9",
                    "fontSize": 12,
                    "fontFamily": "'Plus Jakarta Sans', sans-serif",
                },
                "extraCssText": "box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);",
            },
        },
        "echartsOptionsOverridesByChartType": _build_echarts_by_chart_type(is_dark=True),
    },
}
