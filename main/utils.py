import httpx

def get_scraped_data(sku):
    url = f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}"

    response = httpx.get(url)
    data = response.json()

    item = data.get("data", {}).get("products")[0]

    name = item.get("name")
    sku = item.get("id")
    price = float(item.get("salePriceU")) / 100 if item.get("salePriceU") else None
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating"))
    num_reviews = int(item.get("feedbacks"))

    return {
        "name": name,
        "sku": sku,
        "price": price,
        "image": image,
        "category": category,
        "brand": brand,
        "seller_name": seller_name,
        "rating": rating,
        "num_reviews": num_reviews,
    }