# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:16
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:

from typing import List

from pydantic import BaseModel


class OrderItem(BaseModel):
    description: str
    quantity: int
    amount: str
    price: int
    offerId: str
    namespace: str


class OrderPromotion(BaseModel):
    type: str
    amount: int
    index: int
    priceString: str
    title: str


class Order(BaseModel):
    orderType: str
    orderId: str
    items: List[OrderItem]
    promotions: List[OrderPromotion]


class CompletedOrder(BaseModel):
    offerId: str
    namespace: str


class PromotionGame(BaseModel):
    title: str
    id: str
    namespace: str
    description: str
    offerType: str
    url: str
