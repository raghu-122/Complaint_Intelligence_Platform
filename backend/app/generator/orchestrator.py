"""
Synthetic data generator orchestrator.

Fixed seed: 20261022
Reference timestamp: 2026-01-01T00:00:00Z

Modes:
  starter: ~50 customers, 80 orders, 50 complaints, 150 messages
  full:   5000 customers, 8000 orders, 2000 complaints, 6000 messages
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from faker import Faker

from app.generator import ids as ID

REFERENCE_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
REFERENCE_YEAR = "2026"

SCALE_CONFIG = {
    "starter": {
        "customers": 50,
        "products": 30,
        "orders": 80,
        "complaints": 50,
        "messages": 150,
        "teams": 6,
        "agents_per_team": 2,
    },
    "full": {
        "customers": 5000,
        "products": 200,
        "orders": 8000,
        "complaints": 2000,
        "messages": 6000,
        "teams": 6,
        "agents_per_team": 8,
    },
}

CHANNELS = ["email", "phone", "web", "chat", "social_media", "in_store"]
CHANNEL_WEIGHTS = [0.25, 0.20, 0.25, 0.15, 0.10, 0.05]

ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled", "returned"]
ORDER_STATUS_WEIGHTS = [0.05, 0.10, 0.20, 0.55, 0.05, 0.05]

VULNERABILITY_TYPES = ["elderly", "disability", "financial_hardship", "language_barrier", "bereavement"]

PRODUCT_CATEGORIES = [
    ("Electronics", ["Smartphone", "Laptop", "Tablet", "Headphones", "Smart Watch", "Camera", "Speaker"]),
    ("Clothing", ["T-Shirt", "Jeans", "Jacket", "Dress", "Shoes", "Socks", "Hat"]),
    ("Home & Garden", ["Blender", "Coffee Maker", "Vacuum", "Lamp", "Chair", "Rug", "Pillow"]),
    ("Sports", ["Running Shoes", "Yoga Mat", "Dumbbells", "Water Bottle", "Bicycle", "Helmet", "Gloves"]),
    ("Books", ["Novel", "Textbook", "Cookbook", "Biography", "Self-Help Book", "Children's Book", "Dictionary"]),
    ("Toys", ["Action Figure", "Board Game", "Puzzle", "Doll", "LEGO Set", "Remote Car", "Stuffed Animal"]),
    ("Beauty", ["Shampoo", "Moisturizer", "Lipstick", "Perfume", "Face Mask", "Eye Liner", "Nail Polish"]),
    ("Food & Beverage", ["Coffee Beans", "Tea Set", "Chocolate Box", "Protein Powder", "Olive Oil", "Honey", "Nuts"]),
]

COMPLAINT_TEMPLATES = {
    "DELIVERY_DELAY": [
        ("Late delivery concern", "My order {order_id} was supposed to arrive by now but I haven't received it yet. The tracking shows it's been delayed. This is very frustrating as I needed it urgently."),
        ("Where is my package?", "I've been waiting for my delivery for over a week. The estimated date has passed and there's no update on the tracking. Please help."),
        ("Delivery overdue", "My shipment is overdue by several days. I rely on timely deliveries and this delay is unacceptable. I need an update immediately."),
    ],
    "DAMAGED_PRODUCT": [
        ("Product arrived damaged", "The {product_name} I ordered arrived in a completely damaged state. The box was crushed and the item itself is broken. I'm very disappointed."),
        ("Broken item received", "I received my order today and the product was broken. It looks like it was dropped during shipping. I need a replacement."),
        ("Damaged packaging and product", "Both the packaging and the item inside were damaged when I received my order. This is not acceptable quality."),
    ],
    "PRODUCT_SAFETY": [
        ("URGENT: Safety concern with product", "I'm extremely concerned about the safety of the {product_name} I purchased. It is overheating dangerously and I'm worried about fire risk. Please respond IMMEDIATELY."),
        ("Product caused injury", "The product I bought caused me to be hurt. There appears to be a serious safety hazard. I demand this be investigated urgently."),
        ("Dangerous product - potential recall needed", "I believe this product has a serious safety defect. It sparked and smoked during use. This is extremely dangerous and needs immediate attention."),
    ],
    "REFUND": [
        ("Request for refund", "I would like to request a full refund for my order {order_id}. The product does not meet my expectations and I want my money back immediately."),
        ("Refund not processed", "I returned my item two weeks ago but have not received my refund yet. I need this resolved urgently."),
        ("Demanding refund", "I am furious about this purchase. The product is terrible and I demand a full refund right away. This is completely unacceptable."),
    ],
    "PAYMENT": [
        ("Incorrect charge on my account", "I noticed an incorrect charge of extra amount on my account for order {order_id}. I was overcharged and need this corrected."),
        ("Double charged", "I was charged twice for the same order. Please refund the duplicate charge immediately."),
        ("Unauthorized payment", "There is an unauthorized transaction on my account related to your service. I did not approve this charge."),
    ],
    "PRODUCT_QUALITY": [
        ("Poor product quality", "The {product_name} I received is of very poor quality. It stopped working after just two days. This is not what I expected."),
        ("Product not as described", "The product is completely different from what was advertised. The quality is substandard and I feel misled."),
        ("Defective product", "My recently purchased item is faulty. It malfunctions constantly and is not fit for purpose."),
    ],
    "WRONG_ITEM": [
        ("Wrong item sent", "I ordered a {product_name} but received a completely different item. Please send me the correct product."),
        ("Incorrect product delivered", "The wrong product was delivered to me. I need the correct item sent urgently."),
        ("Not what I ordered", "I received the wrong size/color/model. This is not what I selected during checkout."),
    ],
    "MISSING_ORDER": [
        ("Order never arrived", "My order {order_id} shows as delivered but I never received it. The package appears to be lost or stolen."),
        ("Package missing", "I cannot find my package anywhere. The tracking says delivered but nothing arrived."),
        ("Lost shipment", "My order has been missing for weeks. I believe it was lost in transit. I need a replacement or refund."),
    ],
    "ACCOUNT_SERVICE": [
        ("Cannot access my account", "I've been locked out of my account for several days. The password reset emails are not arriving. I need assistance urgently."),
        ("Poor customer service experience", "The customer service representative I spoke to was rude and unhelpful. I expect better treatment as a customer."),
        ("Account issue", "There is a problem with my account that your support team has not been able to resolve despite multiple contacts."),
    ],
    "OTHER": [
        ("General complaint", "I have a concern about my recent experience with your company that I would like to bring to your attention."),
        ("Issue with service", "I have encountered a problem that doesn't fit neatly into any category but I need your help resolving it."),
        ("Customer concern", "I'm reaching out because I'm not satisfied with a recent interaction and would like this addressed."),
    ],
}


class DataGenerator:
    """
    Generates synthetic but realistic and internally consistent data.
    All generation is seeded for reproducibility.
    """

    def __init__(self, seed: int = 20261022, scale: str = "starter"):
        self.seed = seed
        self.scale = scale
        self.config = SCALE_CONFIG[scale]
        self.rng = random.Random(seed)
        self.fake = Faker()
        Faker.seed(seed)

        # Storage for generated data (in-memory dicts before DB insertion)
        self.categories: list[dict] = []
        self.priority_rules: list[dict] = []
        self.teams: list[dict] = []
        self.agents: list[dict] = []
        self.products: list[dict] = []
        self.customers: list[dict] = []
        self.orders: list[dict] = []
        self.order_items: list[dict] = []
        self.complaints: list[dict] = []
        self.messages: list[dict] = []
        self.assignments: list[dict] = []
        self.sla_clocks: list[dict] = []
        self.sla_events: list[dict] = []
        self.status_events: list[dict] = []
        self.resolutions: list[dict] = []
        self.surveys: list[dict] = []
        self.complaint_relationships: list[dict] = []

        # Indexes for fast lookups
        self._customer_map: dict[str, dict] = {}  # customer_id -> customer
        self._order_map: dict[str, dict] = {}  # order_id -> order
        self._complaint_map: dict[str, dict] = {}  # complaint_id -> complaint
        self._agent_workload: dict[str, int] = {}  # agent_id -> open count
        self._customer_complaint_count: dict[str, int] = {}  # customer_id -> count

        # Import engines here to avoid circular imports
        from app.engine.classifier import ComplaintClassifier
        from app.engine.priority import PriorityEngine
        from app.engine.sla import SLAEngine
        from app.engine.assignment import AssignmentEngine

        import yaml
        from app.config import get_settings
        cfg_dir = get_settings().config_dir
        self._classifier = ComplaintClassifier(cfg_dir / "categories.yaml")
        self._priority_engine = PriorityEngine(cfg_dir / "priority_rules.yaml")
        self._sla_engine = SLAEngine(cfg_dir / "sla_config.yaml")
        self._assignment_engine = AssignmentEngine(cfg_dir / "assignment_rules.yaml")

        with open(cfg_dir / "categories.yaml", "r") as f:
            import yaml
            self._cat_config = yaml.safe_load(f)
        with open(cfg_dir / "priority_rules.yaml", "r") as f:
            self._pri_config = yaml.safe_load(f)

    def _ts(self, days_offset: float = 0.0, hours_offset: float = 0.0) -> datetime:
        """Create a UTC timestamp offset from reference."""
        return REFERENCE_TS + timedelta(days=days_offset, hours=hours_offset)

    def _rand_ts(self, start_days: float, end_days: float) -> datetime:
        """Random UTC timestamp within a day range from reference."""
        offset = self.rng.uniform(start_days * 86400, end_days * 86400)
        return REFERENCE_TS + timedelta(seconds=offset)

    def generate_categories(self) -> list[dict]:
        """Seed category records from config."""
        cats = []
        for cat in self._cat_config["categories"]:
            cats.append({
                "code": cat["code"],
                "name": cat["name"],
                "description": cat.get("description", ""),
                "keywords": json.dumps(cat.get("keywords", [])),
                "safety_risk": cat.get("safety_risk", False),
                "is_active": True,
                "config_version": self._cat_config.get("version", "1.0.0"),
            })
        self.categories = cats
        return cats

    def generate_priority_rules(self) -> list[dict]:
        """Seed priority rule records from config."""
        rules = []
        for rule in self._pri_config["rules"]:
            rules.append({
                "rule_id": rule["rule_id"],
                "name": rule["name"],
                "description": rule["description"],
                "priority_code": rule.get("priority"),
                "priority_upgrade": rule.get("priority_upgrade", 0),
                "condition": rule["condition"],
                "precedence": rule["precedence"],
                "is_active": True,
                "config_version": self._pri_config.get("version", "1.0.0"),
                "effective_date": self._pri_config.get("effective_date", "2026-01-01"),
            })
        self.priority_rules = rules
        return rules

    def generate_teams(self) -> list[dict]:
        """Generate team records."""
        import yaml
        from app.config import get_settings
        with open(get_settings().config_dir / "assignment_rules.yaml") as f:
            data = yaml.safe_load(f)
        teams = []
        for i, team_cfg in enumerate(data["teams"], start=1):
            teams.append({
                "team_id": ID.team_id(i),
                "code": team_cfg["code"],
                "name": team_cfg["name"],
                "description": f"Team handling {', '.join(team_cfg['specializations'])}",
                "specializations": json.dumps(team_cfg["specializations"]),
                "handles_priority": json.dumps(team_cfg["handles_priority"]),
                "safety_capable": team_cfg.get("safety_capable", False),
                "is_active": True,
                "created_at": REFERENCE_TS.isoformat(),
            })
        self.teams = teams
        return teams

    def generate_agents(self) -> list[dict]:
        """Generate agent records for each team."""
        agents = []
        agent_num = 1
        for team in self.teams:
            num_agents = self.config["agents_per_team"]
            for _ in range(num_agents):
                first = self.fake.first_name()
                last = self.fake.last_name()
                email = f"{first.lower()}.{last.lower()}.{agent_num}@yottaflex-support.local"
                agents.append({
                    "agent_id": ID.agent_id(agent_num),
                    "team_id_fk_code": team["code"],  # resolved to int FK later
                    "team_code": team["code"],
                    "name": f"{first} {last}",
                    "email": email,
                    "role": "Senior Agent" if agent_num % 5 == 0 else "Agent",
                    "is_active": True,
                    "max_concurrent_cases": 15,
                    "open_complaint_count": 0,
                    "created_at": REFERENCE_TS.isoformat(),
                })
                self._agent_workload[ID.agent_id(agent_num)] = 0
                agent_num += 1
        self.agents = agents
        return agents

    def generate_products(self) -> list[dict]:
        """Generate product records."""
        products = []
        num = self.config["products"]
        for i in range(1, num + 1):
            cat_name, names = self.rng.choice(PRODUCT_CATEGORIES)
            name = self.rng.choice(names)
            brand = self.fake.company().split()[0]
            full_name = f"{brand} {name}"
            unit_price = Decimal(str(round(self.rng.uniform(5.99, 599.99), 2)))
            products.append({
                "product_id": ID.product_id(i),
                "name": full_name,
                "description": f"High quality {name.lower()} from {brand}.",
                "category": cat_name,
                "subcategory": name,
                "brand": brand,
                "sku": ID.sku(i, cat_name),
                "unit_price": str(unit_price),
                "currency": "USD",
                "stock_quantity": self.rng.randint(0, 500),
                "is_active": True,
                "is_safety_flagged": False,
                "created_at": REFERENCE_TS.isoformat(),
                "updated_at": REFERENCE_TS.isoformat(),
            })
        self.products = products
        return products

    def generate_customers(self) -> list[dict]:
        """Generate customer records."""
        customers = []
        num = self.config["customers"]
        vuln_count = max(1, int(num * 0.05))  # 5% vulnerability flag
        vuln_indices = set(self.rng.sample(range(num), min(vuln_count, num)))

        for i in range(1, num + 1):
            cid = ID.customer_id(i)
            is_vuln = (i - 1) in vuln_indices
            customers.append({
                "customer_id": cid,
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "email": self.fake.unique.email(),
                "phone": self.fake.phone_number()[:30],
                "address_line1": self.fake.street_address(),
                "address_line2": self.fake.secondary_address() if self.rng.random() < 0.3 else None,
                "city": self.fake.city(),
                "state": self.fake.state_abbr(),
                "postal_code": self.fake.zipcode(),
                "country": "US",
                # FICTIONAL TEST ATTRIBUTE ONLY — not real vulnerability data
                "vulnerability_flag": is_vuln,
                "vulnerability_type": self.rng.choice(VULNERABILITY_TYPES) if is_vuln else None,
                "is_active": True,
                "account_tier": self.rng.choice(["standard", "standard", "standard", "premium", "vip"]),
                "loyalty_points": self.rng.randint(0, 5000),
                "is_synthetic": True,
                "created_at": self._rand_ts(-365, -30).isoformat(),
                "updated_at": REFERENCE_TS.isoformat(),
            })
            self._customer_map[cid] = customers[-1]
            self._customer_complaint_count[cid] = 0
        self.customers = customers
        return customers

    def generate_orders(self) -> list[dict]:
        """Generate order records with normalized OrderItem line items and valid customer/product references."""
        orders = []
        order_items = []
        num = self.config["orders"]
        cust_ids = [c["customer_id"] for c in self.customers]
        prod_ids = [p["product_id"] for p in self.products]
        prod_by_id = {p["product_id"]: p for p in self.products}

        for i in range(1, num + 1):
            oid = ID.order_id(i)
            cid = self.rng.choice(cust_ids)
            order_date = self._rand_ts(-180, -1)
            status = self.rng.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS)[0]
            shipped_at = None
            delivered_at = None
            if status in ("shipped", "delivered", "returned"):
                shipped_at = (order_date + timedelta(days=self.rng.randint(1, 3))).isoformat()
            if status in ("delivered", "returned"):
                delivered_at = (order_date + timedelta(days=self.rng.randint(4, 10))).isoformat()

            # Multi-product order item generation (1 to 3 items per order)
            num_items = self.rng.choices([1, 2, 3], weights=[0.70, 0.20, 0.10])[0]
            chosen_pids = self.rng.sample(prod_ids, min(num_items, len(prod_ids)))

            cur_order_items = []
            order_total = Decimal("0.00")
            order_discount = Decimal("0.00")
            order_qty = 0

            for seq, pid in enumerate(chosen_pids, start=1):
                product = prod_by_id[pid]
                uprice = Decimal(product["unit_price"])
                qty = self.rng.randint(1, 4)
                item_discount = Decimal("0.00")
                if self.rng.random() < 0.15:
                    item_discount = (uprice * qty * Decimal("0.10")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                line_total = (uprice * qty - item_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                order_total += line_total
                order_discount += item_discount
                order_qty += qty

                item_id = ID.order_item_id(i, seq)
                item_dict = {
                    "order_item_id": item_id,
                    "order_id_fk_code": oid,
                    "product_id_fk_code": pid,
                    "quantity": qty,
                    "unit_price": str(uprice),
                    "discount_amount": str(item_discount),
                    "line_total": str(line_total),
                    "created_at": order_date.isoformat(),
                }
                cur_order_items.append(item_dict)
                order_items.append(item_dict)

            primary_item = cur_order_items[0]

            orders.append({
                "order_id": oid,
                "customer_id_fk_code": cid,
                "product_id_fk_code": primary_item["product_id_fk_code"],
                "quantity": order_qty,
                "unit_price": primary_item["unit_price"],
                "discount_amount": str(order_discount),
                "total_amount": str(order_total),
                "currency": "USD",
                "status": status,
                "shipping_address": self.fake.address().replace("\n", ", "),
                "tracking_number": f"TRK{self.rng.randint(100000000, 999999999)}" if status != "pending" else None,
                "ordered_at": order_date.isoformat(),
                "shipped_at": shipped_at,
                "delivered_at": delivered_at,
                "created_at": order_date.isoformat(),
                "updated_at": order_date.isoformat(),
            })
            self._order_map[oid] = orders[-1]

        self.orders = orders
        self.order_items = order_items
        return orders

    def _get_category_by_code(self, code: str) -> dict:
        return next((c for c in self.categories if c["code"] == code), self.categories[-1])

    def generate_complaints(self) -> list[dict]:
        """
        Generate complaints with full classification, priority, assignment, SLA, messages.
        Generation follows documented order for referential integrity.
        """
        complaints = []
        num = self.config["complaints"]
        target_messages = self.config["messages"]

        cust_ids = [c["customer_id"] for c in self.customers]
        cat_codes = [c["code"] for c in self.categories]
        agent_list = [
            {
                "agent_id": a["agent_id"],
                "team_code": a["team_code"],
                "open_complaint_count": 0,
                "is_active": True,
            }
            for a in self.agents
        ]

        # Fast lookup maps for referential integrity
        customer_orders_map: dict[str, list[dict]] = {}
        for o in self.orders:
            customer_orders_map.setdefault(o["customer_id_fk_code"], []).append(o)

        order_items_map: dict[str, list[dict]] = {}
        for it in self.order_items:
            order_items_map.setdefault(it["order_id_fk_code"], []).append(it)

        # Pre-allocate variable messages per complaint summing to exactly target_messages
        msg_weights = [0.12, 0.28, 0.35, 0.15, 0.07, 0.03]  # distribution across 1 to 6
        allocated_msgs = [self.rng.choices([1, 2, 3, 4, 5, 6], weights=msg_weights)[0] for _ in range(num)]
        diff = target_messages - sum(allocated_msgs)
        if diff > 0:
            for k in range(diff):
                allocated_msgs[k % num] += 1
        elif diff < 0:
            k = 0
            while diff < 0:
                slot = k % num
                if allocated_msgs[slot] > 1:
                    allocated_msgs[slot] -= 1
                    diff += 1
                k += 1

        # Domain variation flags
        indices = list(range(num))
        self.rng.shuffle(indices)
        chunk = max(1, num // 20)
        safety_indices = set(indices[:chunk])
        missing_order_indices = set(indices[chunk:chunk*2])
        refund_indices = set(indices[chunk*2:chunk*3])
        reopen_indices = set(indices[chunk*3:chunk*4])

        # Recurrence: allocate repeat complaints (~70 for full, ~5 for starter)
        num_repeats = max(5, int(num * 0.035))
        repeat_indices = set(self.rng.sample(range(num // 4, num), min(num_repeats, num - num // 4)))

        repeat_pairs = {}  # complaint_idx -> prior_complaint_id

        for idx in range(num):
            i = idx + 1
            cid = ID.complaint_id(i)

            # Pick customer: if this is a repeat complaint, select a customer who already filed one
            if idx in repeat_indices and complaints:
                prior_complaint_customers = [c["customer_id_fk_code"] for c in complaints]
                customer_id = self.rng.choice(prior_complaint_customers)
            else:
                customer_id = self.rng.choice(cust_ids)

            customer = self._customer_map[customer_id]
            prior_count = self._customer_complaint_count.get(customer_id, 0)

            # Pick order: STRICT CONSISTENCY — orders come ONLY from this customer's orders
            order_id_ref = None
            order_ref = None
            cust_orders = customer_orders_map.get(customer_id, [])
            if idx not in missing_order_indices and cust_orders and self.rng.random() < 0.85:
                order_ref = self.rng.choice(cust_orders)
                order_id_ref = order_ref["order_id"]

            # Determine category
            if idx in safety_indices:
                cat_code = "PRODUCT_SAFETY"
            elif idx in missing_order_indices:
                cat_code = "MISSING_ORDER"
            elif idx in refund_indices:
                cat_code = "REFUND"
            else:
                cat_code = self.rng.choice(cat_codes)

            category = self._get_category_by_code(cat_code)

            # Pick product consistent with order or category
            prod_id_ref = None
            product_name = ""
            if order_ref:
                items_in_order = order_items_map.get(order_id_ref, [])
                if items_in_order:
                    prod_id_ref = self.rng.choice(items_in_order)["product_id_fk_code"]
                else:
                    prod_id_ref = order_ref.get("product_id_fk_code")
            else:
                # For complaints without an order, link if category is product-related
                if cat_code in ("PRODUCT_SAFETY", "PRODUCT_QUALITY", "DAMAGED_PRODUCT", "WRONG_ITEM"):
                    prod_id_ref = self.rng.choice(self.products)["product_id"]
                else:
                    prod_id_ref = None

            if prod_id_ref:
                prod = next((p for p in self.products if p["product_id"] == prod_id_ref), None)
                if prod:
                    product_name = prod["name"]

            # Build complaint text
            templates = COMPLAINT_TEMPLATES.get(cat_code, COMPLAINT_TEMPLATES["OTHER"])
            subject_tmpl, body_tmpl = self.rng.choice(templates)
            subject = subject_tmpl.format(order_id=order_id_ref or "N/A", product_name=product_name or "product")
            body = body_tmpl.format(order_id=order_id_ref or "N/A", product_name=product_name or "product")

            channel = self.rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]

            # Classify
            clf_result = self._classifier.classify(body, subject)

            # Detect sentiment
            sentiment, sentiment_score = self._priority_engine.detect_sentiment(body)

            # Calculate priority
            order_total = Decimal(order_ref["total_amount"]) if order_ref else None
            priority_decision = self._priority_engine.calculate_priority(
                category_code=cat_code,
                is_safety_category=category.get("safety_risk", False),
                sentiment=sentiment,
                order_total=order_total,
                customer_vulnerability_flag=customer.get("vulnerability_flag", False),
                prior_complaint_count=prior_count,
            )

            # Assign
            assignment_decision = self._assignment_engine.assign(
                category_code=cat_code,
                is_safety=category.get("safety_risk", False),
                priority=priority_decision.priority,
                agents=agent_list,
            )

            # Timestamps
            complaint_ts = self._rand_ts(0, 270)  # Jan-Sep 2026
            sla_policy = self._sla_engine.get_policy(priority_decision.priority)
            sla_deadline = complaint_ts + timedelta(hours=sla_policy.resolution_hours)

            # Determine status based on domain variation
            if idx in reopen_indices:
                status = "reopened"
            elif self.rng.random() < 0.25:
                status = "open"
            elif self.rng.random() < 0.20:
                status = "in_progress"
            elif self.rng.random() < 0.15:
                status = "escalated"
            elif self.rng.random() < 0.35:
                status = "resolved"
            else:
                status = "closed"

            # Determine if SLA is breached
            # Simulate: some complaints took longer than SLA
            elapsed_hours = (complaint_ts + timedelta(hours=self.rng.uniform(0, sla_policy.resolution_hours * 1.5)) - complaint_ts).total_seconds() / 3600
            is_breached = elapsed_hours > sla_policy.resolution_hours
            resolved_at = None
            closed_at = None
            if status in ("resolved", "closed", "reopened"):
                resolved_hours = self.rng.uniform(sla_policy.resolution_hours * 0.5,
                                                   sla_policy.resolution_hours * 2.0)
                resolved_at = (complaint_ts + timedelta(hours=resolved_hours)).isoformat()
            if status in ("closed",):
                close_offset = self.rng.uniform(1, 48)
                closed_at = (complaint_ts + timedelta(hours=(float(resolved_hours) + close_offset))).isoformat() if resolved_at else None

            is_safety = category.get("safety_risk", False)
            is_refund = idx in refund_indices

            complaint = {
                "complaint_id": cid,
                "complaint_num": i,
                "customer_id_fk_code": customer_id,
                "order_id_fk_code": order_id_ref,
                "product_id_fk_code": prod_id_ref,
                "category_id_fk_code": cat_code,
                "subject": subject,
                "description": body,
                "channel": channel,
                "status": status,
                "priority": priority_decision.priority,
                "category_code": cat_code,
                "classification_confidence": clf_result.confidence,
                "classification_evidence": clf_result.evidence,
                "classification_rule_id": clf_result.rule_id,
                "classification_rule_version": clf_result.rule_version,
                "priority_rule_applied": priority_decision.rule_applied,
                "priority_explanation": priority_decision.explanation,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "is_safety_incident": is_safety,
                "is_refund_pending": is_refund and status not in ("resolved", "closed"),
                "is_reopened": status == "reopened",
                "reopen_count": 1 if status == "reopened" else 0,
                "is_escalated": status == "escalated",
                "is_anomaly": False,
                "created_at": complaint_ts.isoformat(),
                "updated_at": complaint_ts.isoformat(),
                "resolved_at": resolved_at,
                "closed_at": closed_at,
                # Assignment info (used for building assignment records)
                "_team_code": assignment_decision.team_code,
                "_agent_id": assignment_decision.agent_id,
                "_assignment_rule": assignment_decision.rule_applied,
            }
            complaints.append(complaint)
            self._complaint_map[cid] = complaint
            self._customer_complaint_count[customer_id] = prior_count + 1

            # Update agent workload
            if assignment_decision.agent_id:
                self._agent_workload[assignment_decision.agent_id] = \
                    self._agent_workload.get(assignment_decision.agent_id, 0) + 1
                # Update agent in agent_list for subsequent assignments
                for a in agent_list:
                    if a["agent_id"] == assignment_decision.agent_id:
                        a["open_complaint_count"] = self._agent_workload[assignment_decision.agent_id]

            # Store repeat complaint relationship with strictly prior complaint from same customer
            if idx in repeat_indices and len(complaints) >= 2:
                prior = next((c for c in reversed(complaints[:-1])
                              if c["customer_id_fk_code"] == customer_id), None)
                if prior:
                    repeat_pairs[i] = prior["complaint_id"]

        self.complaints = complaints

        # Build complaint relationships
        for comp_num, prior_cid in repeat_pairs.items():
            comp = next(c for c in complaints if c["complaint_num"] == comp_num)
            self.complaint_relationships.append({
                "primary_complaint_id_fk_code": prior_cid,
                "related_complaint_id_fk_code": comp["complaint_id"],
                "relationship_type": "repeat",
                "notes": "Repeat complaint from same customer on similar issue",
                "created_at": comp["created_at"],
            })

        # Generate status events, messages, SLA, assignments, resolutions, surveys
        self._generate_auxiliary(complaints, allocated_msgs)

        return complaints

    def _generate_auxiliary(self, complaints: list[dict], allocated_msgs: list[int]) -> None:
        """Generate all auxiliary records for complaints."""
        msg_counter: dict[int, int] = {}  # complaint_num -> message seq
        total_msgs = 0

        for comp_idx, comp in enumerate(complaints):
            comp_num = comp["complaint_num"]
            complaint_id_str = comp["complaint_id"]
            complaint_ts = datetime.fromisoformat(comp["created_at"])

            # --- Status events ---
            self.status_events.append({
                "complaint_id_fk_code": complaint_id_str,
                "from_status": None,
                "to_status": "open",
                "changed_by": "system",
                "reason": "Complaint created",
                "occurred_at": complaint_ts.isoformat(),
            })
            if comp["status"] != "open":
                in_prog_ts = complaint_ts + timedelta(hours=self.rng.uniform(0.5, 4))
                self.status_events.append({
                    "complaint_id_fk_code": complaint_id_str,
                    "from_status": "open",
                    "to_status": "in_progress",
                    "changed_by": comp.get("_agent_id", "system"),
                    "reason": "Agent picked up complaint",
                    "occurred_at": in_prog_ts.isoformat(),
                })
            if comp["status"] in ("resolved", "closed", "reopened"):
                res_ts = datetime.fromisoformat(comp["resolved_at"]) if comp["resolved_at"] else complaint_ts + timedelta(hours=24)
                self.status_events.append({
                    "complaint_id_fk_code": complaint_id_str,
                    "from_status": "in_progress",
                    "to_status": "resolved",
                    "changed_by": comp.get("_agent_id", "system"),
                    "reason": "Issue resolved by agent",
                    "occurred_at": res_ts.isoformat(),
                })
            if comp["status"] in ("closed",):
                close_ts = datetime.fromisoformat(comp["closed_at"]) if comp["closed_at"] else res_ts + timedelta(hours=24)
                self.status_events.append({
                    "complaint_id_fk_code": complaint_id_str,
                    "from_status": "resolved",
                    "to_status": "closed",
                    "changed_by": "system",
                    "reason": "Auto-closed after resolution confirmation",
                    "occurred_at": close_ts.isoformat(),
                })
            if comp["status"] == "reopened":
                reopen_ts = datetime.fromisoformat(comp["resolved_at"]) + timedelta(hours=self.rng.uniform(2, 48)) if comp["resolved_at"] else complaint_ts + timedelta(hours=36)
                self.status_events.append({
                    "complaint_id_fk_code": complaint_id_str,
                    "from_status": "resolved",
                    "to_status": "reopened",
                    "changed_by": comp["customer_id_fk_code"],
                    "reason": "Customer indicated issue not resolved",
                    "occurred_at": reopen_ts.isoformat(),
                })
            if comp["status"] == "escalated":
                esc_ts = complaint_ts + timedelta(hours=self.rng.uniform(1, 8))
                self.status_events.append({
                    "complaint_id_fk_code": complaint_id_str,
                    "from_status": "in_progress",
                    "to_status": "escalated",
                    "changed_by": "system",
                    "reason": "SLA threshold exceeded",
                    "occurred_at": esc_ts.isoformat(),
                })

            # --- Assignment ---
            asn_id = ID.assignment_id(comp_num, 1)
            self.assignments.append({
                "assignment_id": asn_id,
                "complaint_id_fk_code": complaint_id_str,
                "team_id_fk_code": comp.get("_team_code"),
                "agent_id_fk_code": comp.get("_agent_id"),
                "assignment_type": "initial",
                "assigned_by": "system",
                "reason": "Initial auto-assignment by engine",
                "rule_applied": comp.get("_assignment_rule", ""),
                "is_current": True,
                "assigned_at": complaint_ts.isoformat(),
            })

            # --- SLA clock ---
            priority = comp["priority"]
            sla_policy = self._sla_engine.get_policy(priority)
            original_deadline = (complaint_ts + timedelta(hours=sla_policy.resolution_hours))
            escalation_threshold = (complaint_ts + timedelta(hours=sla_policy.escalation_hours))
            first_response_deadline = (complaint_ts + timedelta(hours=sla_policy.first_response_hours))

            # Realistic pause simulation: escalated complaints or small fraction of in-progress/closed
            has_pause = (comp["status"] == "escalated") or (self.rng.random() < 0.08 and comp["status"] in ("in_progress", "resolved", "closed"))
            paused_hours = round(self.rng.uniform(1.0, 5.0), 2) if has_pause else 0.0
            current_deadline = original_deadline + timedelta(hours=paused_hours)

            res_dt = datetime.fromisoformat(comp["resolved_at"]) if comp.get("resolved_at") else None
            is_breached = bool(res_dt and res_dt > current_deadline)

            if comp["status"] in ("closed", "resolved"):
                sla_status = "completed"
            elif is_breached:
                sla_status = "breached"
            else:
                sla_status = "running"

            sla_id_str = ID.sla_id(comp_num)

            self.sla_clocks.append({
                "sla_id": sla_id_str,
                "complaint_id_fk_code": complaint_id_str,
                "priority": priority,
                "resolution_hours": sla_policy.resolution_hours,
                "first_response_hours": sla_policy.first_response_hours,
                "escalation_hours": sla_policy.escalation_hours,
                "start_time": complaint_ts.isoformat(),
                "original_deadline": original_deadline.isoformat(),
                "current_deadline": current_deadline.isoformat(),
                "first_response_deadline": first_response_deadline.isoformat(),
                "escalation_threshold_time": escalation_threshold.isoformat(),
                "accumulated_paused_hours": paused_hours,
                "status": sla_status,
                "is_breached": is_breached,
                "breached_at": current_deadline.isoformat() if is_breached else None,
                "is_escalated": comp["is_escalated"],
                "config_version": "1.0.0",
                "created_at": complaint_ts.isoformat(),
            })

            # SLA events (Complete lifecycle: created, paused, resumed, escalated, breached, completed)
            self.sla_events.append({
                "sla_id_fk_code": sla_id_str,
                "event_type": "created",
                "reason": f"SLA clock started for {priority} complaint",
                "hours_paused": None,
                "occurred_at": complaint_ts.isoformat(),
                "is_anomaly": False,
            })

            if paused_hours > 0:
                pause_time = complaint_ts + timedelta(hours=min(1.0, sla_policy.first_response_hours * 0.5))
                resume_time = pause_time + timedelta(hours=paused_hours)
                self.sla_events.append({
                    "sla_id_fk_code": sla_id_str,
                    "event_type": "paused",
                    "reason": "Clock paused awaiting customer documentation",
                    "hours_paused": paused_hours,
                    "occurred_at": pause_time.isoformat(),
                    "is_anomaly": False,
                })
                self.sla_events.append({
                    "sla_id_fk_code": sla_id_str,
                    "event_type": "resumed",
                    "reason": "Customer responded with requested documentation",
                    "hours_paused": None,
                    "occurred_at": resume_time.isoformat(),
                    "is_anomaly": False,
                })

            if comp["is_escalated"]:
                esc_time = complaint_ts + timedelta(hours=min(sla_policy.escalation_hours * 0.8, 8.0))
                self.sla_events.append({
                    "sla_id_fk_code": sla_id_str,
                    "event_type": "escalated",
                    "reason": "Escalated to specialized tier due to threshold breach",
                    "hours_paused": None,
                    "occurred_at": esc_time.isoformat(),
                    "is_anomaly": False,
                })

            if is_breached:
                self.sla_events.append({
                    "sla_id_fk_code": sla_id_str,
                    "event_type": "breached",
                    "reason": "Resolution time exceeded SLA deadline",
                    "hours_paused": None,
                    "occurred_at": current_deadline.isoformat(),
                    "is_anomaly": False,
                })

            if sla_status == "completed" and res_dt:
                self.sla_events.append({
                    "sla_id_fk_code": sla_id_str,
                    "event_type": "completed",
                    "reason": "SLA clock completed upon resolution",
                    "hours_paused": None,
                    "occurred_at": res_dt.isoformat(),
                    "is_anomaly": False,
                })

            # --- Messages ---
            num_msgs = allocated_msgs[comp_idx]

            for seq in range(1, num_msgs + 1):
                msg_ts = complaint_ts + timedelta(hours=self.rng.uniform(seq * 0.5, seq * 4))
                is_agent = seq % 2 == 0
                sender_type = "agent" if is_agent else "customer"
                sender_id = comp.get("_agent_id") if is_agent else comp["customer_id_fk_code"]
                if is_agent:
                    body = self.rng.choice([
                        "Thank you for contacting us. We are looking into your issue and will get back to you shortly.",
                        "We have received your complaint and our team is investigating. We apologize for the inconvenience.",
                        "We have reviewed your case and are working on a resolution. Please allow us 24-48 hours.",
                        "Our team has escalated this issue and a senior agent will follow up with you soon.",
                        "We have processed your request. Please let us know if you need anything else.",
                    ])
                    is_visible = self.rng.random() < 0.8
                else:
                    body = self.rng.choice([
                        "I am still waiting for a resolution. Please update me on the status.",
                        "Thank you for the update. I hope this gets resolved soon.",
                        "This is taking too long. I need this resolved today.",
                        "I appreciate your help. Looking forward to hearing back.",
                        "Please expedite my case. It has been several days now.",
                    ])
                    is_visible = True

                msg_id = ID.message_id(comp_num, seq)
                self.messages.append({
                    "message_id": msg_id,
                    "complaint_id_fk_code": complaint_id_str,
                    "message_type": "customer_message" if not is_agent else "resolution_update" if seq == num_msgs else "customer_message",
                    "sender_type": sender_type,
                    "sender_id": sender_id,
                    "sender_name": None,
                    "body": body,
                    "is_customer_visible": is_visible,
                    "channel": comp["channel"],
                    "delivery_status": "delivered",
                    "sequence_number": seq,
                    "sent_at": msg_ts.isoformat(),
                    "created_at": msg_ts.isoformat(),
                    "is_anomaly": False,
                })
                total_msgs += 1

            # --- Resolution (for resolved/closed/reopened complaints) ---
            if comp["status"] in ("resolved", "closed", "reopened") and comp.get("resolved_at"):
                res_ts = datetime.fromisoformat(comp["resolved_at"])
                res_type = "refund_issued" if comp["is_refund_pending"] else \
                    self.rng.choice(["resolved_no_action", "replacement_sent", "apology_credit", "investigation_closed"])
                refund_amt = None
                if res_type == "refund_issued" and comp.get("order_id_fk_code"):
                    order = self._order_map.get(comp["order_id_fk_code"])
                    if order:
                        refund_amt = str(Decimal(order["total_amount"]).quantize(Decimal("0.01")))

                res_id = ID.resolution_id(comp_num)
                self.resolutions.append({
                    "resolution_id": res_id,
                    "complaint_id_fk_code": comp["complaint_id"],
                    "resolution_type": res_type,
                    "description": f"Complaint resolved via {res_type.replace('_', ' ')}. Customer notified.",
                    "refund_amount": refund_amt,
                    "refund_currency": "USD" if refund_amt else None,
                    "refund_approved": True if refund_amt else None,
                    "refund_processed_at": (res_ts + timedelta(hours=24)).isoformat() if refund_amt else None,
                    "resolved_by_agent_id": comp.get("_agent_id"),
                    "resolved_by_team_id": comp.get("_team_code"),
                    "is_superseded": comp["status"] == "reopened",
                    "resolved_at": res_ts.isoformat(),
                    "created_at": res_ts.isoformat(),
                })

                # Survey (for closed complaints only, 60% response rate)
                if comp["status"] == "closed" and self.rng.random() < 0.60:
                    close_ts = datetime.fromisoformat(comp["closed_at"]) if comp.get("closed_at") else res_ts + timedelta(hours=24)
                    survey_ts = close_ts + timedelta(hours=self.rng.uniform(1, 48))
                    rating = self.rng.choices([1, 2, 3, 4, 5], weights=[0.05, 0.10, 0.20, 0.35, 0.30])[0]
                    srv_id = ID.survey_id(comp_num)
                    self.surveys.append({
                        "survey_id": srv_id,
                        "complaint_id_fk_code": comp["complaint_id"],
                        "rating": rating,
                        "feedback": self.rng.choice([
                            "Overall satisfied with the resolution.",
                            "Could have been faster but the outcome was good.",
                            "Very helpful support team.",
                            "The issue took too long to resolve.",
                            None,
                        ]),
                        "submitted_by": comp["customer_id_fk_code"],
                        "submitted_before_closure": False,
                        "is_anomaly": False,
                        "submitted_at": survey_ts.isoformat(),
                        "created_at": survey_ts.isoformat(),
                    })

    def generate_all(self) -> dict:
        """Run full generation pipeline in correct dependency order."""
        self.generate_categories()
        self.generate_priority_rules()
        self.generate_teams()
        self.generate_agents()
        self.generate_products()
        self.generate_customers()
        self.generate_orders()
        self.generate_complaints()

        return {
            "categories": self.categories,
            "priority_rules": self.priority_rules,
            "teams": self.teams,
            "agents": self.agents,
            "products": self.products,
            "customers": self.customers,
            "orders": self.orders,
            "order_items": self.order_items,
            "complaints": self.complaints,
            "status_events": self.status_events,
            "assignments": self.assignments,
            "sla_clocks": self.sla_clocks,
            "sla_events": self.sla_events,
            "messages": self.messages,
            "resolutions": self.resolutions,
            "surveys": self.surveys,
            "complaint_relationships": self.complaint_relationships,
        }
