import json
from typing import List, Dict, Any, Optional
from core.models import AmazonProduct

def generate_product_schema(product: AmazonProduct) -> Dict[str, Any]:
    schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": product.title,
        "image": [product.main_image] if product.main_image else [],
        "description": " ".join(product.features[:3]) if product.features else product.title,
        "offers": {
            "@type": "Offer",
            "url": product.affiliate_url,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": "Amazon"
            }
        }
    }
    if product.brand:
        schema["brand"] = {
            "@type": "Brand",
            "name": product.brand
        }
    if product.rating and product.review_count:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(product.rating),
            "reviewCount": str(product.review_count)
        }
    return schema

def generate_item_list_schema(products: List[AmazonProduct], title: str) -> Dict[str, Any]:
    items = []
    for idx, prod in enumerate(products):
        prod_schema = generate_product_schema(prod)
        items.append({
            "@type": "ListItem",
            "position": idx + 1,
            "item": prod_schema
        })
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": title,
        "itemListElement": items
    }

def generate_faq_schema(faqs: List[Dict[str, str]]) -> Dict[str, Any]:
    faq_elements = []
    for item in faqs:
        question = item.get("q") or item.get("question")
        answer = item.get("a") or item.get("answer")
        if question and answer:
            faq_elements.append({
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer
                }
            })
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_elements
    }

def combine_schemas_to_html(schemas: List[Dict[str, Any]]) -> str:
    script_tags = []
    for s in schemas:
        if s:
            json_text = json.dumps(s, indent=2)
            script_tags.append(f'<script type="application/ld+json">\n{json_text}\n</script>')
    return "\n\n".join(script_tags)
