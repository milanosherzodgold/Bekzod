import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS (Telegram/GitHub Pages uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mongo ENV
MONGO_URL = os.getenv("MONGO_URL") or "mongodb://localhost:27017/"
DB_NAME = os.getenv("DB_NAME", "sklad_db")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

products = db["products"]
sales = db["sales"]


def oid(x: str) -> ObjectId:
    return ObjectId(x)


@app.get("/")
def home():
    return {"message": "Sklad backend ishlayapti"}


# ======================
# PRODUCTS
# ======================
@app.get("/products")
def get_products():
    data = []
    for p in products.find({"isActive": {"$ne": False}}):
        p["_id"] = str(p["_id"])
        data.append(p)
    return data


@app.post("/products")
def add_product(product: dict):
    # default qiymatlar
    product.setdefault("stockQty", 0)
    product.setdefault("averageCost", 0)
    product.setdefault("sellPrice", 0)
    product.setdefault("isActive", True)

    products.insert_one(product)
    return {"status": "product added"}


@app.put("/products/{product_id}")
def update_product(product_id: str, payload: dict):
    products.update_one({"_id": oid(product_id)}, {"$set": payload})
    return {"status": "product updated"}


@app.delete("/products/{product_id}")
def delete_product(product_id: str):
    # soft delete
    products.update_one({"_id": oid(product_id)}, {"$set": {"isActive": False}})
    return {"status": "product deleted"}


# ======================
# STOCK IN (KIRIM)
# ======================
@app.post("/stock-in")
def stock_in(payload: dict):
    """
    payload:
    {
      "items":[{"productId":"...","qty":10,"buyPrice":5000}],
      "note":"..."
    }
    """
    items = payload.get("items", [])
    now = datetime.utcnow()

    for it in items:
        pid = it["productId"]
        qty = float(it["qty"])
        buy_price = float(it["buyPrice"])

        p = products.find_one({"_id": oid(pid)})
        if not p:
            continue

        old_qty = float(p.get("stockQty", 0))
        old_cost = float(p.get("averageCost", 0))

        new_qty = old_qty + qty
        if new_qty > 0:
            new_cost = ((old_qty * old_cost) + (qty * buy_price)) / new_qty
        else:
            new_cost = old_cost

        products.update_one(
            {"_id": oid(pid)},
            {"$set": {"stockQty": new_qty, "averageCost": new_cost}}
        )

    return {"status": "stock-in confirmed", "at": now.isoformat()}


# ======================
# SALES (SOTUV)
# ======================
@app.post("/sales")
def create_sale(payload: dict):
    """
    payload:
    {
      "items":[{"productId":"...","qty":2,"sellPrice":8000}],
      "paymentType":"cash"
    }
    """
    items_in = payload.get("items", [])
    payment = payload.get("paymentType", "cash")
    now = datetime.utcnow()

    sale_items = []
    total_rev = 0.0
    total_cost = 0.0

    # qoldiq tekshir + hisobla
    for it in items_in:
        pid = it["productId"]
        qty = float(it["qty"])
        sell_price = float(it.get("sellPrice", 0))

        p = products.find_one({"_id": oid(pid)})
        if not p:
            return {"error": "product not found", "productId": pid}

        stock = float(p.get("stockQty", 0))
        avg_cost = float(p.get("averageCost", 0))

        if qty > stock:
            return {"error": "not enough stock", "name": p.get("name"), "stock": stock}

        line_rev = sell_price * qty
        line_cost = avg_cost * qty

        sale_items.append({
            "productId": pid,
            "name": p.get("name"),
            "qty": qty,
            "sellPrice": sell_price,
            "costAtSale": avg_cost,
            "lineRevenue": line_rev,
            "lineCost": line_cost,
            "lineProfit": line_rev - line_cost
        })

        total_rev += line_rev
        total_cost += line_cost

    # qoldiqni kamaytir
    for it in sale_items:
        pid = it["productId"]
        qty = float(it["qty"])
        products.update_one({"_id": oid(pid)}, {"$inc": {"stockQty": -qty}})

    doc = {
        "date": now,
        "paymentType": payment,
        "items": sale_items,
        "totalRevenue": total_rev,
        "totalCost": total_cost,
        "totalProfit": total_rev - total_cost
    }
    res = sales.insert_one(doc)

    return {"status": "sale created", "saleId": str(res.inserted_id), "totals": doc}


# ======================
# REPORTS
# ======================
@app.get("/reports/monthly")
def report_monthly(year: int, month: int):
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    pipeline = [
        {"$match": {"date": {"$gte": start, "$lt": end}}},
        {"$group": {
            "_id": None,
            "revenue": {"$sum": "$totalRevenue"},
            "cost": {"$sum": "$totalCost"},
            "profit": {"$sum": "$totalProfit"},
            "count": {"$sum": 1}
        }}
    ]

    agg = list(sales.aggregate(pipeline))
    if not agg:
        return {"year": year, "month": month, "revenue": 0, "cost": 0, "profit": 0, "salesCount": 0}

    a = agg[0]
    return {
        "year": year,
        "month": month,
        "revenue": a["revenue"],
        "cost": a["cost"],
        "profit": a["profit"],
        "salesCount": a["count"]
    }


