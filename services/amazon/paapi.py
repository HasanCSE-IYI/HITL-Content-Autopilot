import hmac
import hashlib
import json
import datetime
from typing import List, Optional, Dict, Any
import requests
import logging
from core.models import AmazonProduct
from services.amazon.parser import build_affiliate_url

logger = logging.getLogger(__name__)

class AmazonPAAPIClient:
    def __init__(self, access_key: str, secret_key: str, associate_tag: str, country: str = "com"):
        self.access_key = access_key
        self.secret_key = secret_key
        self.associate_tag = associate_tag
        self.country = country
        self.host = f"webservices.amazon.{country}"
        self.region = "us-east-1" if country == "com" else "eu-west-1"
        self.service = "ProductAdvertisingAPI"
        self.endpoint = f"https://{self.host}/paapi5/getitems"

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        k_date = self._sign(("AWS4" + self.secret_key).encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        k_signing = self._sign(k_service, "aws4_request")
        return k_signing

    def get_items(self, asins: List[str]) -> List[AmazonProduct]:
        if not self.access_key or not self.secret_key:
            return []

        payload = {
            "ItemIds": asins,
            "Resources": [
                "Images.Primary.Large",
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ByLineInfo",
                "Offers.Listings.Price",
                "CustomerReviews.Count",
                "CustomerReviews.StarRating"
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": "Associates",
            "Marketplace": f"www.amazon.{self.country}"
        }

        body = json.dumps(payload)
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_uri = "/paapi5/getitems"
        canonical_querystring = ""
        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_request = f"POST\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "content-type": "application/json; charset=utf-8",
            "content-encoding": "amz-1.0",
            "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
            "x-amz-date": amz_date,
            "host": self.host,
            "Authorization": authorization_header
        }

        try:
            resp = requests.post(self.endpoint, data=body, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"PA-API error {resp.status_code}: {resp.text}")
                return []
            
            data = resp.json()
            items = data.get("ItemsResult", {}).get("Items", [])
            products = []
            for item in items:
                asin = item.get("ASIN")
                title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", f"Product {asin}")
                brand = item.get("ItemInfo", {}).get("ByLineInfo", {}).get("Brand", {}).get("DisplayValue")
                features = item.get("ItemInfo", {}).get("Features", {}).get("DisplayValues", [])
                
                # Image
                image_url = item.get("Images", {}).get("Primary", {}).get("Large", {}).get("URL")
                
                # Price
                price = "Check Price on Amazon"
                try:
                    price_str = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
                    if price_str:
                        price = price_str
                except Exception:
                    pass

                # Rating
                rating = None
                try:
                    rating = float(item["CustomerReviews"]["StarRating"]["Value"])
                except Exception:
                    pass

                # Review count
                review_count = None
                try:
                    review_count = int(item["CustomerReviews"]["Count"]["Value"])
                except Exception:
                    pass

                products.append(AmazonProduct(
                    asin=asin,
                    title=title,
                    brand=brand,
                    price=price,
                    rating=rating,
                    review_count=review_count,
                    features=features,
                    main_image=image_url,
                    affiliate_url=build_affiliate_url(asin, self.associate_tag, self.country),
                    pros=features[:3] if features else []
                ))
            return products
        except Exception as e:
            logger.error(f"Failed to fetch from PA-API: {e}")
            return []
