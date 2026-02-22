import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def skill_install_handler(event: dict, agent=None) -> None:
    if event.get("extension_point") != "skill_install":
        return

    skill_name = event.get("skill_name", "")
    skill_path = event.get("skill_path", "")
    if not skill_name or not skill_path:
        return

    try:
        from skill_scanner.core.analyzers import StaticAnalyzer, BehavioralAnalyzer
        from skill_scanner import SkillScanner
    except ImportError:
        logger.warning(
            "cisco-ai-skill-scanner not installed; skipping scan for '%s'", skill_name
        )
        return

    try:
        scanner = SkillScanner(analyzers=[StaticAnalyzer(), BehavioralAnalyzer()])
        result = scanner.scan_skill(skill_path)

        from python.helpers.guard_utils import save_scan_status

        save_scan_status(skill_name, {
            "skill_name": skill_name,
            "status": result.get("status", "needs_review"),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "scanner": "cisco-skill-scanner",
            "scanner_version": getattr(scanner, "version", "unknown"),
            "findings": result.get("findings", []),
            "max_severity": result.get("max_severity", "UNKNOWN"),
        })
        logger.info("Scanned skill '%s': status=%s", skill_name, result.get("status"))

    except Exception:
        logger.exception("Cisco scanner failed for skill '%s'", skill_name)