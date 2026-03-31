import json
from pathlib import Path
from typing import Callable


def normalize_fund_code(code: str) -> str:
    return str(code or "").strip()


def _normalize_optional_name(name) -> str:
    return str(name or "").strip()


def _normalize_holding(raw_holding: dict | None) -> dict | None:
    if not isinstance(raw_holding, dict):
        return None

    units_raw = raw_holding.get("units")
    cost_raw = raw_holding.get("cost_amount")
    if units_raw is None and cost_raw is None:
        return None

    try:
        units = float(units_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("持有份额必须是数字") from exc

    try:
        cost_amount = float(cost_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("持仓成本必须是数字") from exc

    if units <= 0:
        raise ValueError("持有份额必须大于 0")
    if cost_amount < 0:
        raise ValueError("持仓成本不能为负数")

    return {"units": units, "cost_amount": cost_amount}


def normalize_fund_items(existing_funds: list[dict], *, ignore_invalid_holding: bool = False) -> list[dict]:
    normalized: list[dict] = []
    for item in existing_funds or []:
        if isinstance(item, dict):
            code = normalize_fund_code(item.get("code"))
            name = _normalize_optional_name(item.get("name"))
            try:
                holding = _normalize_holding(item.get("holding"))
            except ValueError:
                if not ignore_invalid_holding:
                    raise
                holding = None
        else:
            code = normalize_fund_code(item)
            name = ""
            holding = None

        if not code:
            continue

        normalized_item = {"code": code}
        if name:
            normalized_item["name"] = name
        if holding:
            normalized_item["holding"] = holding
        normalized.append(normalized_item)
    return normalized


def _serialize_funds_payload(funds: list[dict]) -> dict:
    payload_items: list[dict] = []
    for item in normalize_fund_items(funds):
        payload_item = {"code": str(item["code"])}
        name = _normalize_optional_name(item.get("name"))
        if name:
            payload_item["name"] = name
        holding = _normalize_holding(item.get("holding"))
        if holding:
            payload_item["holding"] = holding
        payload_items.append(payload_item)
    return {"funds": payload_items}


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


def add_fund_and_save(existing_funds: list[dict], code: str, config_path: Path) -> list[dict]:
    normalized_code = normalize_fund_code(code)
    if not normalized_code:
        raise ValueError("基金代码不能为空")

    current = normalize_fund_items(existing_funds)
    existing_codes = {str(item.get("code") or "").strip() for item in current}
    if normalized_code in existing_codes:
        raise ValueError("基金已在列表中")

    updated = [*current, {"code": normalized_code}]
    payload = _serialize_funds_payload(updated)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return updated


def update_fund_holding_and_save(
    existing_funds: list[dict], code: str, units: float, cost_amount: float, config_path: Path
) -> list[dict]:
    normalized_code = normalize_fund_code(code)
    if not normalized_code:
        raise ValueError("基金代码不能为空")

    holding = _normalize_holding({"units": units, "cost_amount": cost_amount})
    current = normalize_fund_items(existing_funds)

    updated: list[dict] = []
    found = False
    for item in current:
        item_code = normalize_fund_code(item.get("code"))
        if item_code == normalized_code:
            updated_item = dict(item)
            updated_item["holding"] = holding
            updated.append(updated_item)
            found = True
        else:
            updated.append(dict(item))

    if not found:
        raise ValueError("基金不在列表中")

    payload = _serialize_funds_payload(updated)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return updated


def calculate_holding_metrics(
    *, units: float | None, cost_amount: float | None, current_nav: float | None, previous_nav: float | None
) -> dict:
    try:
        normalized_units = float(units)
        normalized_cost = float(cost_amount)
    except (TypeError, ValueError):
        return {
            "market_value": None,
            "total_profit": None,
            "total_profit_pct": None,
            "daily_profit": None,
            "daily_profit_pct": None,
        }

    if normalized_units <= 0 or normalized_cost < 0:
        return {
            "market_value": None,
            "total_profit": None,
            "total_profit_pct": None,
            "daily_profit": None,
            "daily_profit_pct": None,
        }

    market_value = None
    total_profit = None
    total_profit_pct = None
    daily_profit = None
    daily_profit_pct = None

    try:
        normalized_current_nav = float(current_nav)
    except (TypeError, ValueError):
        normalized_current_nav = None

    try:
        normalized_previous_nav = float(previous_nav)
    except (TypeError, ValueError):
        normalized_previous_nav = None

    if normalized_current_nav is not None:
        market_value = normalized_units * normalized_current_nav
        total_profit = market_value - normalized_cost
        if normalized_cost > 0:
            total_profit_pct = total_profit / normalized_cost * 100

    if normalized_current_nav is not None and normalized_previous_nav is not None and normalized_previous_nav != 0:
        daily_profit = normalized_units * (normalized_current_nav - normalized_previous_nav)
        daily_profit_pct = (normalized_current_nav - normalized_previous_nav) / normalized_previous_nav * 100

    return {
        "market_value": market_value,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_profit": daily_profit,
        "daily_profit_pct": daily_profit_pct,
    }


def remove_fund_and_save(existing_funds: list[dict], code: str, config_path: Path) -> list[dict]:
    normalized_code = normalize_fund_code(code)
    if not normalized_code:
        raise ValueError("基金代码不能为空")

    current = normalize_fund_items(existing_funds)
    updated = [item for item in current if str(item.get("code") or "").strip() != normalized_code]
    if len(updated) == len(current):
        raise ValueError("基金不在列表中")

    payload = _serialize_funds_payload(updated)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return updated
