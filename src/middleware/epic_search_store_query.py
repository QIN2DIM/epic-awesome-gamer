# -*- coding: utf-8 -*-
# Time       : 2023/11/21 22:02
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description:
import json
from datetime import datetime, timezone
from typing import Dict, Any
from urllib.parse import quote_plus

from pydantic import BaseModel, Field, PositiveInt, NonNegativeInt


def bind_date() -> str:
    """2023-11-21T13:45:31.533Z"""
    dt_utc = datetime.now(tz=timezone.utc)
    formatted_date = f"{dt_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z"
    formatted_effective_date = f"[,{formatted_date}]"

    return formatted_effective_date


class Variables(BaseModel):
    allowCountries: str = "US"
    category: str = "games/edition/base"
    count: PositiveInt = 1
    country: str = "US"
    effectiveDate: str = Field(default_factory=bind_date)
    freeGame: bool = True
    keywords: str = ""
    locale: str = "en-US"
    sortBy: str = "relevancy,viewableDate"
    sortDir: str = "DESC,DESC"
    start: NonNegativeInt = 0
    tag: str = ""
    withPrice: bool = True


class SearchStoreQuery(BaseModel):
    base_url: str = Field(default="https://store.epicgames.com/graphql", frozen=True)
    operation_name: str = Field(default="searchStoreQuery", frozen=True)
    variables: Variables = Variables()
    extensions: Dict[str, Any] = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "7d58e12d9dd8cb14c84a3ff18d360bf9f0caa96bf218f2c5fda68ba88d68a437",
        }
    }

    def query_all_promotions(self, count: int = 1) -> str:
        if isinstance(count, int) and count > 0:
            self.variables.count = count

        encoded_variables = quote_plus(self.variables.model_dump_json())
        encoded_extensions = quote_plus(json.dumps(self.extensions))

        full_url = (
            f"{self.base_url}?"
            f"operationName={self.operation_name}&"
            f"variables={encoded_variables}&"
            f"extensions={encoded_extensions}"
        )

        return full_url
