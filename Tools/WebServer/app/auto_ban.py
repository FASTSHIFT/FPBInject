#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Auto-ban engine for FPBInject Web Server.

Detects and bans malicious IPs based on:
1. Known vulnerability scan path fingerprints
2. Request rate limiting for auth-rejected requests

Banned IPs receive tarpit (slow) responses to waste scanner resources.
"""

import ipaddress
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Known vulnerability scan path fingerprints
MALICIOUS_PATH_PATTERNS = [
    # Java middleware
    "/xxl-job-admin",
    "/jmx-console",
    "/invoker/JMXInvokerServlet",
    "/invoker/readonly",
    "/wls-wsat/",
    "/ws_utc/",
    "/console/j_security_check",
    "/j_acegi_security_check",
    "/axis2/services",
    # Spring Boot
    "/actuator/env",
    "/actuator/health",
    "/actuator/gateway",
    "/application-dev.properties",
    "/application-prod.properties",
    "/application-stage.properties",
    "/application-pre.properties",
    "/application-prd.properties",
    "/application-production.properties",
    "/application-staging.properties",
    "/application-stg.properties",
    "/application-preview.properties",
    # Spring Cloud Config
    "/config/application",
    # PHP frameworks
    "/index.php/index/index/testsql",
    "/thinkphp/index.php",
    "/general/login/index.php",
    # Monitoring systems
    "/zabbix/",
    "/zabbix/setup.php",
    "/setup.php",
    "/jsrpc.php",
    "/solr/admin/cores",
    "/remote_agent.php",
    # CMS / admin panels
    "/wp/v2/posts",
    "/xmlrpc.php",
    "/resin-admin/",
    "/manager/html",
    # Gateways / APIs
    "/apisix/batch-requests",
    "/apisix/admin/",
    "/kong/status",
    # Path traversal
    "/../",
    "/..;/",
    "../../../../",
    "/etc/passwd",
    "/win.ini",
    # JNDI injection (Log4Shell CVE-2021-44228)
    "${jndi:",
    # OGNL / SpEL expression injection (Struts2, Spring)
    "${(#",
    "${T(",
    "@java.lang.Runtime@",
    "getRuntime().exec(",
    # Netflix Hystrix SpEL injection
    "/hystrix/",
    # Laravel Ignition RCE (CVE-2021-3129)
    "/_ignition/execute-solution",
    # Apache Druid RCE (CVE-2021-25646)
    "/druid/indexer/v1/sampler",
    # MinIO bootstrap
    "/minio/bootstrap/",
    # CGI-BIN traversal
    "/cgi-bin/",
    # Other known vulnerabilities
    "/CFIDE/administrator",
    "/webtools/control/xmlrpc",
    "/webtools/control/SOAPService",
    "/fileserver/",
    "/uddiexplorer/",
    "/ueditor/",
    "/javax.faces.resource/dynamiccontent",
    "/vpn/../vpns/cfg/smb.conf",
    "/openam/",
    "/debug/exec",
    "/tmui/login.jsp",
    "/zentao/",
    "/CTCWebService/",
    "/manage/log/view",
    "/log/view",
    # JBoss MQ HTTP IL deserialization (CVE-2017-7504)
    "/jbossmq-httpil/HTTPServerILServlet",
    # Confluence OGNL injection (CVE-2022-26134)
    "/pages/createpage-entervariables.action",
    # VMware vCenter / ESXi
    "/ui/vropspluginui/",
    "/eam/vib",
    "/analytics/telemetry/ph/",
    # F5 BIG-IP iControl REST RCE (CVE-2022-1388)
    "/mgmt/tm/util/bash",
    # phpMyAdmin
    "/phpMyAdmin/",
    "/phpmyadmin/",
    "/pma/",
    # Apache Ambari
    "/ambari/api/v1/users/",
    # Fortinet FortiGate VPN (CVE-2018-13379)
    "/remote/logincheck",
    # SaltStack API (CVE-2020-11651)
    "/v1/tools/run",
    # Seeyon OA file upload
    "/develop/systparam/softlogo/",
    # DataEase BI
    "/de2api/datasource/",
    # Exchange Autodiscover SSRF (CVE-2021-34473)
    "/autodiscover/autodiscover.json",
    # Apache Airflow
    "/admin/airflow/",
    # MicroStrategy BI
    "/MicroStrategy/servlet/",
    "/servlet/taskProc",
    # Grafana user creation (CVE-2021-43798)
    "/create_user/",
    # Jira information disclosure
    "/secure/ContactAdministrators",
    # JumpServer session leak
    "/api/v1/terminal/sessions/",
    # Nacos console
    "/api/console/api_server",
    # Roundcube Webmail
    "/composer/send_email",
    # GraphQL introspection
    "/graphql",
    # Azkaban scheduler
    "/azkaban",
    # CASA / NetIQ
    "/casa/nodes/thumbprints",
    # iLO / BMC IPMI
    "/rest/v1/AccountService/",
    # VMware vSAN SpEL injection (CVE-2021-21985)
    "/ui/h5-vsan/rest/proxy/",
    # Struts2 JSON plugin
    "/json",
    # GitLab
    "/users/sign_in",
    "/uploads/user",
    # osinstall
    "/osinstall/v1/device/",
]


@dataclass
class IPRecord:
    """Behavior record for a single IP."""

    first_seen: float = 0.0
    hit_count: int = 0
    reject_count: int = 0
    malicious_score: int = 0
    banned_until: float = 0.0
    ban_count: int = 0
    last_seen: float = 0.0
    recent_timestamps: list = field(default_factory=list)


class AutoBanEngine:
    """Automatic IP ban engine based on behavior analysis."""

    def __init__(
        self,
        rate_window=10,
        rate_limit=20,
        malicious_threshold=3,
        ban_duration=3600,
        ban_escalation=2.0,
        max_ban_duration=86400,
        whitelist=None,
        tarpit_delay=10.0,
    ):
        """Initialize the auto-ban engine.

        Args:
            rate_window: Rate detection window in seconds.
            rate_limit: Max rejected requests within window before ban.
            malicious_threshold: Malicious path hits before ban.
            ban_duration: Base ban duration in seconds.
            ban_escalation: Ban duration multiplier per repeat offense.
            max_ban_duration: Maximum ban duration in seconds.
            whitelist: List of trusted IPs or CIDR ranges.
            tarpit_delay: Seconds to delay response for banned IPs.
        """
        self.rate_window = rate_window
        self.rate_limit = rate_limit
        self.malicious_threshold = malicious_threshold
        self.ban_duration = ban_duration
        self.ban_escalation = ban_escalation
        self.max_ban_duration = max_ban_duration
        self.whitelist = set(whitelist or [])
        self.tarpit_delay = tarpit_delay
        self.records = defaultdict(IPRecord)

    def is_whitelisted(self, ip):
        """Check if IP is in the whitelist (exact or CIDR match)."""
        if ip in self.whitelist:
            return True
        try:
            addr = ipaddress.ip_address(ip)
            for w in self.whitelist:
                if "/" in w:
                    if addr in ipaddress.ip_network(w, strict=False):
                        return True
        except ValueError:
            pass
        return False

    def is_malicious_path(self, path):
        """Check if request path matches known vulnerability scan fingerprints."""
        path_lower = path.lower()
        return any(p.lower() in path_lower for p in MALICIOUS_PATH_PATTERNS)

    def check_and_record(self, ip, path):
        """Pre-auth check: only ban status and malicious path detection.

        This is called BEFORE token verification. It only checks:
        1. Whether the IP is already banned (tarpit)
        2. Whether the path matches known malicious fingerprints

        Rate limiting is NOT done here — it is handled by record_reject()
        which is called only after token verification fails. This prevents
        legitimate authenticated users from being rate-limited by normal
        frontend polling.

        Args:
            ip: Client IP address.
            path: Request path.

        Returns:
            dict with keys:
                action: "allow" or "tarpit"
                reason: Human-readable reason string
                ban_remaining: Seconds remaining in ban (0 if not banned)
        """
        if self.is_whitelisted(ip):
            return {"action": "allow", "reason": "whitelisted", "ban_remaining": 0}

        now = time.time()
        rec = self.records[ip]

        if not rec.first_seen:
            rec.first_seen = now

        rec.last_seen = now
        rec.hit_count += 1

        # Already banned -> tarpit
        if rec.banned_until > now:
            remaining = rec.banned_until - now
            return {"action": "tarpit", "reason": "banned", "ban_remaining": remaining}

        # Malicious path detection (ban immediately on threshold)
        if self.is_malicious_path(path):
            rec.malicious_score += 1
            rec.reject_count += 1
            if rec.malicious_score >= self.malicious_threshold:
                self._ban_ip(
                    ip,
                    rec,
                    f"malicious path threshold ({rec.malicious_score})",
                )
                return {
                    "action": "tarpit",
                    "reason": f"banned: malicious_score={rec.malicious_score}",
                    "ban_remaining": rec.banned_until - now,
                }

        return {"action": "allow", "reason": "passed", "ban_remaining": 0}

    def record_reject(self, ip, path):
        """Record an auth rejection (called after token check fails).

        This feeds the rate limiter without re-running malicious path check.
        """
        if self.is_whitelisted(ip):
            return

        now = time.time()
        rec = self.records[ip]
        rec.reject_count += 1
        rec.recent_timestamps.append(now)
        cutoff = now - self.rate_window
        rec.recent_timestamps = [t for t in rec.recent_timestamps if t > cutoff]

        if len(rec.recent_timestamps) > self.rate_limit:
            self._ban_ip(
                ip,
                rec,
                f"rate limit after reject ({len(rec.recent_timestamps)}/{self.rate_window}s)",
            )

    def _ban_ip(self, ip, rec, reason):
        """Ban an IP with escalating duration."""
        rec.ban_count += 1
        duration = min(
            self.ban_duration * (self.ban_escalation ** (rec.ban_count - 1)),
            self.max_ban_duration,
        )
        rec.banned_until = time.time() + duration
        logger.warning(
            f"AUTO-BAN: {ip} banned for {duration:.0f}s "
            f"(count={rec.ban_count}, reason={reason}, "
            f"total_hits={rec.hit_count}, rejects={rec.reject_count})"
        )

    def get_banned_ips(self):
        """Get list of currently banned IPs."""
        now = time.time()
        result = []
        for ip, rec in self.records.items():
            if rec.banned_until > now:
                result.append(
                    {
                        "ip": ip,
                        "banned_until": rec.banned_until,
                        "remaining": rec.banned_until - now,
                        "ban_count": rec.ban_count,
                        "total_hits": rec.hit_count,
                        "malicious_score": rec.malicious_score,
                    }
                )
        return result

    def get_stats(self):
        """Get engine statistics."""
        now = time.time()
        active_bans = sum(1 for r in self.records.values() if r.banned_until > now)
        return {
            "tracked_ips": len(self.records),
            "active_bans": active_bans,
            "total_bans_issued": sum(r.ban_count for r in self.records.values()),
        }

    def unban_ip(self, ip):
        """Manually unban an IP."""
        if ip in self.records:
            self.records[ip].banned_until = 0
            logger.info(f"MANUAL-UNBAN: {ip}")
