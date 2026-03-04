import json
from pathlib import Path
from typing import Callable


def normalize_fund_code(code: str) -> str:
    return str(code or "").strip()


def preview_fund_candidate(code: str, fetch_estimate: Callable[[str], dict]) -> dict:
    normalized = normalize_fund_code(code)
    if not normalized:
        raise ValueError("基金代码不能为空")

    try:
        result = fetch_estimate(normalized)
    except Exception as exc:
        raise ValueError(f"基金查询失败: {exc}") from exc
    name = str(result.get("name") or normalized).strip() or normalized
    return {
        "code": normalized,
        "name": name,
        "pct": result.get("pct"),
        "ts": result.get("ts") or "",
    }


def _normalize_fund_items(existing_funds: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in existing_funds or []:
        if isinstance(item, dict):
            code = normalize_fund_code(item.get("code"))
        else:
            code = normalize_fund_code(item)
        if code:
            normalized.append({"code": code})
    return normalized


def add_fund_and_save(existing_funds: list[dict], code: str, config_path: Path) -> list[dict]:
    normalized_code = normalize_fund_code(code)
    if not normalized_code:
        raise ValueError("基金代码不能为空")

    current = _normalize_fund_items(existing_funds)
    existing_codes = {str(item.get("code") or "").strip() for item in current}
    if normalized_code in existing_codes:
        raise ValueError("基金已在列表中")

    updated = [*current, {"code": normalized_code}]
    payload = {"funds": [{"code": str(item["code"])} for item in updated]}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return updated


def remove_fund_and_save(existing_funds: list[dict], code: str, config_path: Path) -> list[dict]:
    normalized_code = normalize_fund_code(code)
    if not normalized_code:
        raise ValueError("基金代码不能为空")

    current = _normalize_fund_items(existing_funds)
    updated = [item for item in current if str(item.get("code") or "").strip() != normalized_code]
    if len(updated) == len(current):
        raise ValueError("基金不在列表中")

    payload = {"funds": [{"code": str(item["code"])} for item in updated]}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return updated
