import re
from typing import List, Tuple

BANNED_PHRASES = [
    r"you should (buy|sell|invest|purchase|enter|trade)",
    r"you must (buy|sell|invest|purchase|enter|trade)",
    r"you need to (buy|sell|invest|purchase|enter|trade)",
    r"buy (this|the) stock",
    r"sell (this|the) stock",
    r"don't miss (this|the) opportunity",
    r"best stock to (buy|invest)",
    r"sure.?shot (winner|stock)",
    r"guaranteed (return|profit|income)",
    r"double your money",
    r"maximum profit",
    r"secret (strategy|formula|tip|technique)",
    r"(stock|trading) (tip|signal|call)",
    r"target (price|of) ₹?\s*\d+",
    r"(will|going to) (reach|hit|touch) ₹?\d+",
    r"price (target|prediction)",
    r"this is not financial advice",  # negative framing - implies you ARE giving advice
]

REQUIRED_DISCLAIMER_PATTERNS = [
    r"educational (purpose|only)",
    r"not (a |an |)SEBI[\s-]?(registered|regist)",
    r"(do your own|your own) research",
]

BANNED_STOCK_ACTIONS = [
    "buy", "sell", "purchase", "enter", "exit",
]

PERSONAL_OPINION_MARKERS = [
    r"I would",
    r"in my (view|opinion|perspective)",
    r"personally",
    r"I (consider|think|believe|feel)",
    r"my (approach|strategy|plan)",
]

FOLLOW_UP_REQUIRED = re.compile(
    r"(I would (buy|sell|hold|consider|invest|enter|exit))",
    re.IGNORECASE,
)

FOLLOW_UP_DISCLAIMERS = re.compile(
    r"(do your own research|your own (investigation|due diligence)|consult (a |your |an |)advisor|not (a |)recommendation)",
    re.IGNORECASE,
)


def check_banned_phrases(script: str) -> List[str]:
    violations = []
    for pattern in BANNED_PHRASES:
        matches = re.findall(pattern, script, re.IGNORECASE)
        for match in matches:
            full_match = match[0] if isinstance(match, tuple) else match
            violations.append(f"Banned phrase found: \"{full_match}\" (pattern: {pattern})")
    return violations


def check_required_disclaimers(script: str) -> List[str]:
    missing = []
    for pattern in REQUIRED_DISCLAIMER_PATTERNS:
        if not re.search(pattern, script, re.IGNORECASE):
            missing.append(f"Missing required disclaimer pattern: {pattern}")
    return missing


def check_personal_opinion_follow_up(script: str) -> List[str]:
    violations = []
    opinion_statements = FOLLOW_UP_REQUIRED.findall(script)
    has_disclaimer = FOLLOW_UP_DISCLAIMERS.search(script)
    for statement in opinion_statements:
        full_statement = statement[0] if isinstance(statement, tuple) else statement
        if not has_disclaimer:
            violations.append(
                f"Personal opinion \"{full_statement}\" found without follow-up disclaimer "
                f"(\"do your own research\")"
            )
    return violations


def check_price_targets(script: str) -> List[str]:
    violations = []
    price_target_pattern = re.compile(
        r"(will|going to|could|would) (reach|hit|touch|cross) ₹?\s*\d+",
        re.IGNORECASE,
    )
    matches = price_target_pattern.findall(script)
    if matches:
        violations.append(
            "Forward-looking price target found. Use \"historically reached\" instead."
        )
    return violations


def validate_script(script: str) -> Tuple[bool, List[str]]:
    all_violations = []
    all_violations.extend(check_banned_phrases(script))
    all_violations.extend(check_required_disclaimers(script))
    all_violations.extend(check_personal_opinion_follow_up(script))
    all_violations.extend(check_price_targets(script))

    is_clean = len(all_violations) == 0
    return is_clean, all_violations


def redact_banned_phrases(script: str) -> str:
    for pattern in BANNED_PHRASES:
        script = re.sub(
            pattern,
            lambda m: f"**[REDACTED: {m.group(0)}]**",
            script,
            flags=re.IGNORECASE,
        )
    return script


def generate_compliance_report(script: str) -> str:
    is_clean, violations = validate_script(script)
    if is_clean:
        return "✅ COMPLIANCE PASSED — No violations found.\n"

    report = ["❌ COMPLIANCE FAILED — Violations found:\n"]
    for v in violations:
        report.append(f"  • {v}")
    report.append("")

    redacted = redact_banned_phrases(script)
    if redacted != script:
        report.append("Redacted Script:")
        report.append(redacted)

    return "\n".join(report)
