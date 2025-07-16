# -*- coding: utf-8 -*-
# Time       : 2023/8/14 23:16
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:

from typing import List

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    description: str
    offerId: str
    namespace: str


class Order(BaseModel):
    orderType: str
    orderId: str
    items: List[OrderItem] = Field(default_factory=list)


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
