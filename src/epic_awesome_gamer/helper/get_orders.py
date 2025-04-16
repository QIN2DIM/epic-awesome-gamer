# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:16
# Author     : QIN2DIM
# Github     : https://github.com/QIN2DIM
# Description:
from __future__ import annotations

import json
from contextlib import suppress
from json import JSONDecodeError
from typing import List, Dict

import httpx
from loguru import logger

from epic_awesome_gamer.types import Order, OrderItem, PromotionGame

URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
URL_PRODUCT_PAGE = "https://store.epicgames.com/en-US/p/"
URL_PRODUCT_BUNDLES = "https://store.epicgames.com/en-US/bundles/"
URL_ORDER_HISTORY = "https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory"


def get_promotions() -> List[PromotionGame]:
    """
    获取周免游戏数据

    <即将推出> promotion["promotions"]["upcomingPromotionalOffers"]
    <本周免费> promotion["promotions"]["promotionalOffers"]
    :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
    """

    def is_discount_game(prot: dict) -> bool | None:
        with suppress(KeyError, IndexError, TypeError):
            offers = prot["promotions"]["promotionalOffers"][0]["promotionalOffers"]
            for i, offer in enumerate(offers):
                if offer["discountSetting"]["discountPercentage"] == 0:
                    return True

    promotions: List[PromotionGame] = []

    resp = httpx.get(URL_PROMOTIONS, params={"local": "zh-CN"})

    try:
        data = resp.json()
    except JSONDecodeError as err:
        logger.error("Failed to get promotions", err=err)
        return []

    # Get store promotion data and <this week free> games
    for e in data["data"]["Catalog"]["searchStore"]["elements"]:

        # Remove items that are discounted but not free.
        if not is_discount_game(e):
            continue

        # package free games
        try:
            query = e["catalogNs"]["mappings"][0]["pageSlug"]
            e["url"] = f"{URL_PRODUCT_PAGE}{query}"
        except TypeError:
            e["url"] = f"{URL_PRODUCT_BUNDLES}{e['productSlug']}"
        except IndexError:
            e["url"] = f"{URL_PRODUCT_PAGE}{e['productSlug']}"

        promotions.append(PromotionGame(**e))

    return promotions


def get_order_history(
    cookies: Dict[str, str], page: str | None = None, last_create_at: str | None = None
) -> List[OrderItem]:
    """获取最近的订单纪录"""

    def request_history() -> str | None:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203"
        }
        params = {"locale": "zh-CN", "page": page or "0", "latCreateAt": last_create_at or ""}
        resp = httpx.get(URL_ORDER_HISTORY, headers=headers, cookies=cookies, params=params)
        if not resp.is_success:
            raise httpx.RequestError("Failed to get order history, cookie may have expired")
        return resp.text

    completed_orders: List[OrderItem] = []

    try:
        data = json.loads(request_history())
        for _order in data["orders"]:
            order = Order(**_order)
            if order.orderType != "PURCHASE":
                continue
            for item in order.items:
                if not item.namespace or len(item.namespace) != 32:
                    continue
                completed_orders.append(item)
    except (httpx.RequestError, JSONDecodeError, KeyError) as err:
        logger.warning(err)

    return completed_orders
