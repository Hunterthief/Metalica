```python
# -*- coding: utf-8 -*-
"""
نظام إدارة المخزون للمعادن
- تتبع المخزون وفقاً لنظام الدفعات (Lots) مع عرض الدفعات في الجدول الرئيسي
- عند النقر على المعدن، عرض/إخفاء الدفعات المختلفة
- دمج الدفعات التي لها نفس السعر
- اختيار الدفعة عند البيع لاحتساب الربح بدقة
"""
import os
import json
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading
from collections import defaultdict

# إعدادات الملفات
DATA_FILE = "data.json"
BACKUP_DIR = "backups"
AUTO_BACKUP_INTERVAL_SECONDS = 30 * 60  # 30 دقيقة
SETTINGS_FILE = "settings.json"

os.makedirs(BACKUP_DIR, exist_ok=True)

# -# الدوال العامة# -
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_data():
    """تحميل البيانات من data.json"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            # التأكد من أن جميع الحقول المطلوبة موجودة
            if "metals" not in d:
                d["metals"] = []
            if "history" not in d:
                d["history"] = []
            if "parties" not in d:
                d["parties"] = {}
            if "expenses" not in d:
                d["expenses"] = []
            # تحديث البيانات القديمة لتشمل الحقول الجديدة
            for m in d["metals"]:
                if "lots" not in m:
                    m["lots"] = [{"quantity": m.get("quantity", 0.0), "price_per_kg": m.get("price_per_kg", 0.0), "source": m.get("source", ""), "date_added": now_iso()}]
                    m["quantity"] = sum(l["quantity"] for l in m["lots"])
                if "profit_total" not in m:
                    m["profit_total"] = 0.0
            for h in d["history"]:
                if "profit_percentage" not in h:
                    h["profit_percentage"] = 0.0
            return d
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل قراءة ملف البيانات: {e}")
            return {"metals": [], "history": [], "parties": {}, "expenses": []}
    else:
        return {"metals": [], "history": [], "parties": {}, "expenses": []}

def save_data(data):
    """حفظ البيانات إلى data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_backup(data):
    """إنشاء نسخة احتياطية جديدة"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(BACKUP_DIR, f"backup_{ts}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # حذف النسخ الاحتياطية الأقدم من 7 أيام
        cutoff_time = datetime.now().timestamp() - 7 * 24 * 3600
        for f in os.listdir(BACKUP_DIR):
            fp = os.path.join(BACKUP_DIR, f)
            if os.path.isfile(fp) and os.path.getctime(fp) < cutoff_time:
                os.remove(fp)
    except Exception as e:
        messagebox.showerror("خطأ", f"فشل إنشاء نسخة احتياطية: {e}")

def backup_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def load_settings():
    """تحميل الإعدادات من settings.json"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    # القيم الافتراضية
    return {"dark_mode": False, "auto_backup": True}

def save_settings(settings):
    """حفظ الإعدادات إلى settings.json"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def metal_total_quantity(metal):
    """حساب الكمية الإجمالية للمعدن من جميع الدفعات"""
    return sum(l["quantity"] for l in metal.get("lots", []))

def calculate_cost_basis_and_sources(metal, qty_to_remove, selected_lot_index=None):
    """
    حساب تكلفة الشراء وتحديث الدفعات بناءً على الكمية المطلوب بيعها.
    يدعم اختيار دفعة معينة أولاً، ثم يستمر باستخدام FIFO إذا لزم الأمر.
    """
    if not metal.get("lots"):
        raise ValueError("لا توجد دفعات متوفرة للمعدن.")

    lots = metal["lots"]
    cost = 0.0
    remaining = qty_to_remove
    sources_used = []

    # 1. محاولة استخدام الدفعة المحددة أولاً (إن وُجدت)
    if selected_lot_index is not None and 0 <= selected_lot_index < len(lots):
        selected_lot = lots[selected_lot_index]
        lot_qty = selected_lot["quantity"]
        lot_price = selected_lot["price_per_kg"]

        if remaining <= lot_qty + 1e-9: # تسامح بسيط لل Floating Point
            # يمكن تغطية الكمية بالكامل من هذه الدفعة
            cost += remaining * lot_price
            sources_used.append((selected_lot.get("source", ""), remaining, lot_price))
            selected_lot["quantity"] -= remaining
            remaining = 0
        else:
            # استخدم كل كمية هذه الدفعة
            cost += lot_qty * lot_price
            sources_used.append((selected_lot.get("source", ""), lot_qty, lot_price))
            remaining -= lot_qty
            selected_lot["quantity"] = 0 # تم استخدامها بالكامل

        # حذف الدفعات التي انتهت كميتها
        metal["lots"] = [l for l in lots if l["quantity"] > 1e-9]

    # 2. الاستمرار باستخدام FIFO (أو أي دفعة متوفرة) للباقي
    lots = metal["lots"] # تحديث القائمة بعد الحذف
    for i in range(len(lots)):
        if remaining <= 1e-9:
            break
        lot = lots[i]
        lot_qty = lot["quantity"]
        lot_price = lot["price_per_kg"]

        if remaining <= lot_qty + 1e-9:
            cost += remaining * lot_price
            sources_used.append((lot.get("source", ""), remaining, lot_price))
            lot["quantity"] -= remaining
            remaining = 0
        else:
            cost += lot_qty * lot_price
            sources_used.append((lot.get("source", ""), lot_qty, lot_price))
            remaining -= lot_qty
            lot["quantity"] = 0 # تم استخدامها بالكامل

    # حذف الدفعات التي انتهت كميتها بعد المعالجة
    metal["lots"] = [l for l in metal["lots"] if l["quantity"] > 1e-9]

    if remaining > 1e-9:
        raise ValueError("الكمية المطلوبة للسحب أكبر من المتوفر.")

    # إذا أصبحت جميع الكميات صفرًا، نقوم بتحديث السعر الرئيسي
    if metal_total_quantity(metal) == 0 and metal["lots"]:
        metal["price_per_kg"] = metal["lots"][0].get("price_per_kg", 0.0)
        metal["sale_price_per_kg"] = metal["price_per_kg"]

    return round(cost, 2), sources_used

def update_party_balance(parties, party_name, amount, transaction_type, is_supplier=False, transaction_details=None):
    """تحديث رصيد العميل/المورد وإضافة تفصيل المعاملة"""
    if party_name not in parties:
        parties[party_name] = {"type": "مورد" if is_supplier else "عميل", "balance": 0.0, "transactions": []}
    
    # إضافة تفصيل المعاملة إلى سجل الطرف
    if transaction_details:
        parties[party_name]["transactions"].append(transaction_details)
    
    # حساب الرصيد الجديد (إذا كان مورداً، فإن المبلغ المدفوع يقلل من الرصيد المطلوب، العكس صحيح للعميل)
    if is_supplier:
        # الرصيد هو المبلغ المطلوب الدفع (الذمم الدائنة)
        parties[party_name]["balance"] += amount
    else:
        # الرصيد هو المبلغ المطلوب تحصيله (الذمم المدينة)
        parties[party_name]["balance"] += amount

# -# نوافذ الحوارات# -
class AddMetalDialog:
    def __init__(self, parent, parties):
        top = self.top = tk.Toplevel(parent)
        top.title("✨ إضافة معدن جديد")
        top.geometry("450x350")
        top.transient(parent)
        top.grab_set()

        # قائمة الموردين
        supplier_names = [name for name, info in parties.items() if info.get("type") == "supplier"]

        ttk.Label(top, text="اسم المعدن:", font=("Cairo", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.e_name = ttk.Entry(top, justify="right")
        self.e_name.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(top, text="الكمية (كجم):", font=("Cairo", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(top, text="سعر الشراء (جنيه/كجم):", font=("Cairo", 10, "bold")).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=5, padx=5)

        # مورد
        ttk.Label(top, text="المصدر (مورد):", font=("Cairo", 10, "bold")).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.cmb_supplier = ttk.Combobox(top, values=supplier_names, state="readonly", justify="right")
        self.cmb_supplier.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Label(top, text="أو أدخل مورد جديد:", font=("Cairo", 10, "bold")).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.e_new_supplier = ttk.Entry(top, justify="right")
        self.e_new_supplier.grid(row=4, column=1, pady=5, padx=5)

        # الدفعات الجزئية
        ttk.Label(top, text="المبلغ المدفوع:", font=("Cairo", 10, "bold")).grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.e_paid = ttk.Entry(top, justify="right")
        self.e_paid.grid(row=5, column=1, pady=5, padx=5)
        self.e_paid.insert(0, "0")

        ttk.Label(top, text="المبلغ المتبقي:", font=("Cairo", 10, "bold")).grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.e_due = ttk.Entry(top, justify="right")
        self.e_due.grid(row=6, column=1, pady=5, padx=5)
        self.e_due.insert(0, "0")

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="✅ حفظ", command=self.on_add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)

        self.result = None

    def on_add(self):
        name = self.e_name.get().strip()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()

        # مورد
        supplier = self.cmb_supplier.get().strip()
        new_supplier = self.e_new_supplier.get().strip()
        if supplier and new_supplier:
            messagebox.showerror("خطأ", "يرجى تحديد مورد من القائمة أو إدخال مورد جديد، وليس كليهما.")
            return
        elif supplier:
            source = supplier
        elif new_supplier:
            source = new_supplier
        else:
            source = "مجهول" # أو اجعله مطلوبًا

        paid = self.e_paid.get().strip() or "0"
        due = self.e_due.get().strip() or "0"

        if not name or not qty or not price:
            messagebox.showerror("خطأ", "يرجى ملء كل الحقول المطلوبة.")
            return
        try:
            float(qty); float(price); float(paid); float(due)
        except:
            messagebox.showerror("خطأ", "قيمة رقمية خاطئة.")
            return

        self.result = (name, qty, float(price), source, float(paid), float(due))
        self.top.destroy()

    def on_cancel(self):
        self.top.destroy()

class AddStockDialog:
    def __init__(self, parent, metals, parties):
        top = self.top = tk.Toplevel(parent)
        top.title("📦 إضافة كمية لمعدن موجود")
        top.geometry("450x350")
        top.transient(parent)
        top.grab_set()

        # قائمة الموردين
        supplier_names = [name for name, info in parties.items() if info.get("type") == "supplier"]

        ttk.Label(top, text="اختر المعدن:", font=("Cairo", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.cmb_metal = ttk.Combobox(top, values=[m["name"] for m in metals], state="readonly", justify="right")
        self.cmb_metal.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(top, text="الكمية (كجم):", font=("Cairo", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(top, text="سعر الشراء (جنيه/كجم):", font=("Cairo", 10, "bold")).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=5, padx=5)

        # مورد
        ttk.Label(top, text="المصدر (مورد):", font=("Cairo", 10, "bold")).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.cmb_supplier = ttk.Combobox(top, values=supplier_names, state="readonly", justify="right")
        self.cmb_supplier.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Label(top, text="أو أدخل مورد جديد:", font=("Cairo", 10, "bold")).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.e_new_supplier = ttk.Entry(top, justify="right")
        self.e_new_supplier.grid(row=4, column=1, pady=5, padx=5)

        # الدفعات الجزئية
        ttk.Label(top, text="المبلغ المدفوع:", font=("Cairo", 10, "bold")).grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.e_paid = ttk.Entry(top, justify="right")
        self.e_paid.grid(row=5, column=1, pady=5, padx=5)
        self.e_paid.insert(0, "0")

        ttk.Label(top, text="المبلغ المتبقي:", font=("Cairo", 10, "bold")).grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.e_due = ttk.Entry(top, justify="right")
        self.e_due.grid(row=6, column=1, pady=5, padx=5)
        self.e_due.insert(0, "0")

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="✅ حفظ", command=self.on_add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)

        self.result = None

    def on_add(self):
        name = self.cmb_metal.get()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()

        # مورد
        supplier = self.cmb_supplier.get().strip()
        new_supplier = self.e_new_supplier.get().strip()
        if supplier and new_supplier:
            messagebox.showerror("خطأ", "يرجى تحديد مورد من القائمة أو إدخال مورد جديد، وليس كليهما.")
            return
        elif supplier:
            source = supplier
        elif new_supplier:
            source = new_supplier
        else:
            source = "مجهول" # أو اجعله مطلوبًا

        paid = self.e_paid.get().strip() or "0"
        due = self.e_due.get().strip() or "0"

        if not name or not qty or not price:
            messagebox.showerror("خطأ", "يرجى ملء كل الحقول المطلوبة.")
            return
        try:
            float(qty); float(price); float(paid); float(due)
        except:
            messagebox.showerror("خطأ", "قيمة رقمية خاطئة.")
            return

        self.result = (name, qty, float(price), source, float(paid), float(due))
        self.top.destroy()

    def on_cancel(self):
        self.top.destroy()

class RemoveStockDialog:
    def __init__(self, parent, metals, parties):
        top = self.top = tk.Toplevel(parent)
        top.title("💰 بيع / سحب كمية")
        top.geometry("500x400")
        top.transient(parent)
        top.grab_set()

        # قائمة العملاء
        customer_names = [name for name, info in parties.items() if info.get("type") == "customer"]

        ttk.Label(top, text="اختر المعدن:", font=("Cairo", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.cmb_metal = ttk.Combobox(top, values=[m["name"] for m in metals], state="readonly", justify="right")
        self.cmb_metal.grid(row=0, column=1, pady=5, padx=5)
        self.cmb_metal.bind("<<ComboboxSelected>>", self.on_metal_selected)

        ttk.Label(top, text="اختر الدفعة:", font=("Cairo", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.cmb_lot = ttk.Combobox(top, state="readonly", justify="right")
        self.cmb_lot.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(top, text="الكمية (كجم):", font=("Cairo", 10, "bold")).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(top, text="سعر البيع (جنيه/كجم):", font=("Cairo", 10, "bold")).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=3, column=1, pady=5, padx=5)

        # عميل
        ttk.Label(top, text="العميل:", font=("Cairo", 10, "bold")).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.cmb_customer = ttk.Combobox(top, values=customer_names, state="readonly", justify="right")
        self.cmb_customer.grid(row=4, column=1, pady=5, padx=5)
        
        ttk.Label(top, text="أو أدخل عميل جديد:", font=("Cairo", 10, "bold")).grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.e_new_customer = ttk.Entry(top, justify="right")
        self.e_new_customer.grid(row=5, column=1, pady=5, padx=5)

        # الدفعات الجزئية
        ttk.Label(top, text="المبلغ المدفوع:", font=("Cairo", 10, "bold")).grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.e_paid = ttk.Entry(top, justify="right")
        self.e_paid.grid(row=6, column=1, pady=5, padx=5)
        self.e_paid.insert(0, "0")

        ttk.Label(top, text="المبلغ المتبقي:", font=("Cairo", 10, "bold")).grid(row=7, column=0, sticky="e", padx=5, pady=5)
        self.e_due = ttk.Entry(top, justify="right")
        self.e_due.grid(row=7, column=1, pady=5, padx=5)
        self.e_due.insert(0, "0")

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="✅ بيع", command=self.on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=top.destroy).pack(side=tk.RIGHT, padx=5)

        self.metals_data = metals
        self.parties_data = parties
        self.result = None

    def on_metal_selected(self, event=None):
        metal_name = self.cmb_metal.get()
        metal = next((m for m in self.metals_data if m["name"] == metal_name), None)
        if metal:
            self.update_lot_options(metal)

    def update_lot_options(self, metal):
        lots = metal.get("lots", [])
        lot_options = []
        for i, lot in enumerate(lots):
            desc = f"{i}: {lot['quantity']:.3f} كجم @ {lot['price_per_kg']:.2f} جنيه"
            lot_options.append(desc)
        self.cmb_lot['values'] = lot_options
        # تحديد الخيار الأول تلقائيًا إذا كان موجودًا
        if lot_options:
            self.cmb_lot.current(0)

    def split_quantity_over_lots(self, metal, total_qty_to_remove, sale_price_per_kg, person, paid_amount, due_amount):
        """
        تقسيم الكمية على الدفعات المختلفة تلقائيًا.
        """
        lots = metal.get("lots", [])
        if not lots:
            raise ValueError("لا توجد دفعات متوفرة للمعدن.")

        remaining_qty = total_qty_to_remove
        transactions = []
        index = 0

        while remaining_qty > 1e-9 and index < len(lots):
            current_lot = lots[index]
            lot_qty_available = current_lot["quantity"]

            if remaining_qty <= lot_qty_available + 1e-9:
                # الكمية المطلوبة تُغطى من هذه الدفعة
                qty_from_this_lot = remaining_qty
                current_lot["quantity"] -= qty_from_this_lot
                # حساب التكلفة والربح لهذه الكمية
                cost_basis = qty_from_this_lot * current_lot["price_per_kg"]
                revenue = qty_from_this_lot * sale_price_per_kg
                profit = revenue - cost_basis
                profit_percentage = (profit / cost_basis * 100) if cost_basis > 0 else 0.0
                
                transactions.append({
                    "name": metal["name"],
                    "qty": qty_from_this_lot,
                    "sale_price": sale_price_per_kg,
                    "person": person,
                    "paid_amount": paid_amount * (qty_from_this_lot / total_qty_to_remove), # توزيع المدفوعات والمطلوبة بشكل متناسب
                    "due_amount": due_amount * (qty_from_this_lot / total_qty_to_remove),
                    "cost_basis": cost_basis,
                    "profit": profit,
                    "profit_percentage": profit_percentage,
                    "lot_index": index
                })
                
                remaining_qty = 0
            else:
                # استخدم كل كمية هذه الدفعة
                qty_from_this_lot = lot_qty_available
                current_lot["quantity"] = 0 # تم استخدامها بالكامل
                # حساب التكلفة والربح لهذه الكمية
                cost_basis = qty_from_this_lot * current_lot["price_per_kg"]
                revenue = qty_from_this_lot * sale_price_per_kg
                profit = revenue - cost_basis
                profit_percentage = (profit / cost_basis * 100) if cost_basis > 0 else 0.0
                
                transactions.append({
                    "name": metal["name"],
                    "qty": qty_from_this_lot,
                    "sale_price": sale_price_per_kg,
                    "person": person,
                    "paid_amount": paid_amount * (qty_from_this_lot / total_qty_to_remove),
                    "due_amount": due_amount * (qty_from_this_lot / total_qty_to_remove),
                    "cost_basis": cost_basis,
                    "profit": profit,
                    "profit_percentage": profit_percentage,
                    "lot_index": index
                })
                
                remaining_qty -= qty_from_this_lot
                index += 1
        
        # حذف الدفعات التي انتهت كميتها
        metal["lots"] = [l for l in lots if l["quantity"] > 1e-9]

        if remaining_qty > 1e-9:
            raise ValueError("الكمية المطلوبة للبيع أكبر من المتوفر.")

        return transactions

    def on_ok(self):
        metal_name = self.cmb_metal.get()
        lot_desc = self.cmb_lot.get()
        qty_str = self.e_qty.get().strip()
        price_str = self.e_price.get().strip()

        # عميل
        customer = self.cmb_customer.get().strip()
        new_customer = self.e_new_customer.get().strip()
        if customer and new_customer:
            messagebox.showerror("خطأ", "يرجى تحديد عميل من القائمة أو إدخال عميل جديد، وليس كليهما.")
            return
        elif customer:
            person = customer
        elif new_customer:
            person = new_customer
        else:
            person = "مجهول" # أو اجعله مطلوبًا

        paid_str = self.e_paid.get().strip() or "0"
        due_str = self.e_due.get().strip() or "0"

        if not metal_name or not lot_desc or not qty_str or not price_str:
            messagebox.showerror("خطأ", "يرجى ملء كل الحقول المطلوبة.")
            return

        try:
            qty = float(qty_str)
            sale_price = float(price_str)
            paid_amount = float(paid_str)
            due_amount = float(due_str)
            if qty <= 0 or sale_price <= 0:
                raise ValueError("الكمية والسعر يجب أن يكونا أكبر من الصفر.")
        except ValueError as e:
            messagebox.showerror("خطأ", f"قيمة غير صحيحة: {e}")
            return

        metal = next((m for m in self.metals_data if m["name"] == metal_name), None)
        if not metal:
            messagebox.showerror("خطأ", "المعدن غير موجود.")
            return

        # استخراج فهرس الدفعة المحددة من الوصف
        selected_lot_index = int(lot_desc.split(':')[0]) if lot_desc else None
        if selected_lot_index is not None and selected_lot_index >= len(metal.get("lots", [])):
            messagebox.showerror("خطأ", "الدفعة المحددة غير موجودة.")
            return

        # التحقق من كمية الدفعة المحددة
        if selected_lot_index is not None:
            selected_lot_qty = metal["lots"][selected_lot_index]["quantity"]
            if qty > selected_lot_qty + 1e-9:
                # الكمية المطلوبة أكبر من الدفعة المحددة
                msg = f"الكمية المطلوبة ({qty:.3f} كجم) تفوق الكمية المتوفرة في الدفعة المحددة ({selected_lot_qty:.3f} كجم).\n"
                msg += "هل تريد تقسيم الكمية تلقائيًا على الدفعات المتاحة؟"
                if messagebox.askyesno("تحذير", msg):
                    try:
                        transactions = self.split_quantity_over_lots(metal, qty, sale_price, person, paid_amount, due_amount)
                        # عرض ملخص التقسيم للمستخدم للتأكيد
                        summary = "سيتم بيع الكمية على النحو التالي:\n"
                        for t in transactions:
                            summary += f"- {t['qty']:.3f} كجم من دفعة (مصدر: {metal['lots'][t['lot_index']]['source'] if t['lot_index'] < len(metal['lots']) else 'N/A'}, سعر شراء: {metal['lots'][t['lot_index']]['price_per_kg'] if t['lot_index'] < len(metal['lots']) else 0.0:.2f} جنيه)\n"
                        summary += f"إجمالي الكمية: {sum(t['qty'] for t in transactions):.3f} كجم\n"
                        summary += f"إجمالي التكلفة: {sum(t['cost_basis'] for t in transactions):.2f} جنيه\n"
                        summary += f"إجمالي الإيراد: {sum(t['qty'] * t['sale_price'] for t in transactions):.2f} جنيه\n"
                        summary += f"إجمالي الربح: {sum(t['profit'] for t in transactions):.2f} جنيه"
                        if messagebox.askyesno("تأكيد التقسيم", summary):
                            self.result = transactions
                            self.top.destroy()
                            return
                        else:
                            return # إلغاء العملية
                    except ValueError as e:
                        messagebox.showerror("خطأ", str(e))
                        return
                else:
                    return # إلغاء العملية

        # إذا لم يتم التقسيم، فاستخدم الدفعة المحددة فقط
        try:
            cost_basis, sources_used = calculate_cost_basis_and_sources(metal, qty, selected_lot_index)
        except ValueError as e:
            messagebox.showerror("خطأ", str(e))
            return

        revenue = qty * sale_price
        profit = revenue - cost_basis
        profit_percentage = (profit / cost_basis * 100) if cost_basis > 0 else 0.0

        self.result = [(metal_name, qty, sale_price, person, paid_amount, due_amount, selected_lot_index, cost_basis, profit, profit_percentage)]
        self.top.destroy()


# -# واجهة المستخدم# -
class MetalInventoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📋 نظام إدارة المخزون للمعادن")
        self.geometry("1000x700")
        self.data = load_data()
        self.settings = load_settings()
        self.create_widgets()
        self.refresh_table()
        self.start_auto_backup()

    def create_widgets(self):
        # إطار الأدوات العلوية
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=5)

        # أزرار الأدوات - مع إضافة رموز ملونة وجذابة
        self.btn_add_metal = ttk.Button(toolbar_frame, text="✨ إضافة معدن", command=self.open_add_metal_menu)
        self.btn_add_stock = ttk.Button(toolbar_frame, text="📦 إضافة كمية", command=self.open_add_stock)
        self.btn_remove_stock = ttk.Button(toolbar_frame, text="💰 بيع / سحب كمية", command=self.open_remove_stock)
        self.btn_remove_metal = ttk.Button(toolbar_frame, text="🗑️ حذف معدن", command=self.remove_metal)
        self.btn_history = ttk.Button(toolbar_frame, text="🕒 السجل", command=self.open_history_window)
        self.btn_export = ttk.Button(toolbar_frame, text="⬇️ تصدير", command=self.export_data)
        self.btn_import = ttk.Button(toolbar_frame, text="⬆️ استيراد", command=self.import_data)
        self.btn_manage_parties = ttk.Button(toolbar_frame, text="👥 إدارة الحسابات", command=self.open_manage_parties)
        self.btn_manage_expenses = ttk.Button(toolbar_frame, text="💸 المصروفات", command=self.open_manage_expenses)
        self.btn_settings = ttk.Button(toolbar_frame, text="⚙️ الإعدادات", command=self.open_settings)

        for w in [self.btn_settings, self.btn_manage_expenses, self.btn_manage_parties, self.btn_export, self.btn_import, self.btn_history, self.btn_remove_metal, self.btn_remove_stock, self.btn_add_stock, self.btn_add_metal]:
            w.pack(side=tk.RIGHT, padx=3)

        # شريط البحث
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(search_frame, text="بحث:").pack(side=tk.RIGHT, padx=(0, 5))
        self.search_var = tk.StringVar()
        entry_search = ttk.Entry(search_frame, textvariable=self.search_var, justify="right")
        entry_search.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(0, 5))
        entry_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        # جدول المعادن
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ("name", "quantity", "price_per_kg", "sale_price_per_kg", "total_value", "profit_total", "lots_count")
        headers_ar = {
            "name": "الاسم",
            "quantity": "الكمية (كجم)",
            "price_per_kg": "سعر الشراء (ج/كجم)",
            "sale_price_per_kg": "سعر البيع (ج/كجم)",
            "total_value": "القيمة الإجمالية (ج)",
            "profit_total": "إجمالي الربح (ج)",
            "lots_count": "عدد الدفعات"
        }
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.tree.heading(c, text=headers_ar.get(c, c))
            self.tree.column(c, anchor="center", width=100)
        self.tree.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # شريط التمرير
        v_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        v_scrollbar.grid(row=0, column=2, sticky="ns")
        self.tree.configure(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=self.tree.xview)
        h_scrollbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.tree.configure(xscrollcommand=h_scrollbar.set)

        # ربط النقر على العنصر
        self.tree.bind("<Button-1>", self.on_item_click)
        self.tree.bind("<Double-1>", self.on_item_double_click)

        # شريط الحالة السفلي
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.total_value_label = ttk.Label(status_frame, text="إجمالي قيمة المخزون (سعر الشراء): 0 جنيه")
        self.total_profit_label = ttk.Label(status_frame, text="إجمالي الربح: 0 جنيه (0.0%)")
        self.last_backup_label = ttk.Label(status_frame, text="آخر نسخة احتياطية: -")
        self.total_profit_label.pack(side=tk.LEFT, padx=8)
        self.total_value_label.pack(side=tk.LEFT, padx=8)
        self.last_backup_label.pack(side=tk.RIGHT, padx=8)

    def on_item_click(self, event):
        """التعامل مع النقر على العنصر في الجدول"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        # تبديل عرض/إخفاء الدفعات
        self.toggle_lots(item_id)

    def on_item_double_click(self, event):
        """النقر المزدوج لفتح نافذة تعديل الأسعار"""
        item_id = self.tree.focus()
        if item_id:
            self.open_edit_prices(item_id)

    def toggle_lots(self, item_id):
        """عرض أو إخفاء دفعات المعدن"""
        children = self.tree.get_children(item_id)
        metal_name = item_id
        metal = next((m for m in self.data["metals"] if m["name"] == metal_name), None)
        if not metal:
            return

        if children:
            # إذا كانت الدفعات معروضة، قم بإخفاؤها
            for child in children:
                self.tree.delete(child)
        else:
            # إذا لم تكن معروضة، قم بعرضها
            lots = metal.get("lots", [])
            for i, lot in enumerate(lots):
                lot_id = f"{item_id}_lot_{i}"
                self.tree.insert(item_id, "end", iid=lot_id, values=("", f"   دفعة {i+1}", lot["quantity"], lot["price_per_kg"], "", "", lot.get("source", "")))

    def refresh_table(self):
        """تحديث عرض الجدول"""
        for i in self.tree.get_children():
            self.tree.delete(i)

        search_term = self.search_var.get().lower()
        filtered_metals = [m for m in self.data["metals"] if search_term in m["name"].lower()]

        for m in filtered_metals:
            total_value = metal_total_quantity(m) * m.get("price_per_kg", 0.0)
            lots_count = len(m.get("lots", []))
            self.tree.insert("", "end", iid=m["name"], values=(
                m["name"],
                f"{metal_total_quantity(m):.3f}",
                f"{m.get('price_per_kg', 0.0):.2f}",
                f"{m.get('sale_price_per_kg', 0.0):.2f}",
                f"{total_value:.2f}",
                f"{m.get('profit_total', 0.0):.2f}",
                lots_count
            ))
            # تحديث التسمية في شريط الحالة
            total_inventory_value = sum(metal_total_quantity(m) * m.get("price_per_kg", 0.0) for m in self.data["metals"])
            total_profit = sum(m.get("profit_total", 0.0) for m in self.data["metals"])
            total_profit_percentage = (total_profit / total_inventory_value * 100) if total_inventory_value > 0 else 0.0
            self.total_value_label.config(text=f"إجمالي قيمة المخزون (سعر الشراء): {total_inventory_value:.2f} جنيه")
            self.total_profit_label.config(text=f"إجمالي الربح: {total_profit:.2f} جنيه ({total_profit_percentage:.2f}%)")

    def start_auto_backup(self):
        """بدء مؤقت النسخ الاحتياطي التلقائي"""
        def backup_loop():
            if self.settings.get("auto_backup", True):
                make_backup(self.data)
                self.after(0, lambda: self.last_backup_label.config(text=f"آخر نسخة احتياطية: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"))
            self.after(AUTO_BACKUP_INTERVAL_SECONDS * 1000, backup_loop)
        self.after(AUTO_BACKUP_INTERVAL_SECONDS * 1000, backup_loop)

    # -# بقية الوظائف (إضافة / بيع / السجل / تصدير / استيراد)# -
    def open_add_metal_menu(self):
        menu = tk.Toplevel(self)
        menu.title("اختيار العملية")
        menu.geometry("300x150")
        menu.transient(self)
        menu.grab_set()
        ttk.Label(menu, text="اختر نوع الإضافة:", font=("Cairo", 12, "bold")).pack(pady=10)
        btn_frame = ttk.Frame(menu)
        btn_frame.pack(pady=10)
        btn_new = ttk.Button(btn_frame, text="✨ معدن جديد", command=lambda:[menu.destroy(), self.open_add_metal_dialog()])
        btn_new.grid(row=0, column=0, padx=5, pady=5)
        btn_existing = ttk.Button(btn_frame, text="📦 إضافة لمعدن موجود",
                                  command=lambda:[menu.destroy(), self.open_add_stock()])

    def open_add_metal_dialog(self):
        dialog = AddMetalDialog(self, self.data.get("parties", {}))
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, source, paid_amount, due_amount = dialog.result
            total_amount = float(qty) * float(price)
            # تحقق من وجود المعدن
            existing_metal = next((m for m in self.data["metals"] if m["name"] == name), None)
            if existing_metal:
                messagebox.showerror("خطأ", f"المعدن '{name}' موجود بالفعل. يرجى استخدام 'إضافة كمية' بدلاً من ذلك.")
                return

            new_metal = {
                "name": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "sale_price_per_kg": float(price), # تعيين سعر البيع مبدئيًا مثل سعر الشراء
                "lots": [{"quantity": float(qty), "price_per_kg": float(price), "source": source, "date_added": now_iso()}],
                "profit_total": 0.0
            }
            self.data["metals"].append(new_metal)

            # إضافة تفصيل المعاملة
            transaction_details = {
                "operation": "إضافة معدن جديد",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": total_amount,
                "paid_amount": paid_amount,
                "due_amount": due_amount
            }

            self.data["history"].append({
                "date": now_iso(),
                "operation": "إضافة معدن جديد",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": total_amount,
                "person": source,
                "paid_amount": paid_amount,
                "due_amount": due_amount,
                "cost_basis": 0, # لا تكلفة للشراء في هذه العملية
                "profit": 0,
                "profit_percentage": 0.0,
                "transaction_type": "purchase" # نوع المعاملة
            })

            # تحديث رصيد المورد وإضافة تفصيل المعاملة
            update_party_balance(self.data["parties"], source, due_amount, "purchase", is_supplier=True, transaction_details=transaction_details)

            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_add_stock(self):
        dialog = AddStockDialog(self, self.data.get("metals", []), self.data.get("parties", {}))
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, buy_price, source, paid_amount, due_amount = dialog.result

            metal = next((m for m in self.data["metals"] if m["name"] == name), None)
            if not metal:
                messagebox.showerror("خطأ", "المعدن غير موجود.")
                return

            qty = float(qty)
            total_amount = qty * buy_price

            # إضافة كمية جديدة كدفعة منفصلة
            new_lot = {
                "quantity": qty,
                "price_per_kg": buy_price,
                "source": source,
                "date_added": now_iso()
            }
            metal["lots"].append(new_lot)
            # تحديث الكمية الإجمالية
            metal["quantity"] = metal_total_quantity(metal)

            # حساب السعر الجديد (متوسط مرجح)
            total_qty = metal["quantity"]
            weighted_price = sum(l["quantity"] * l["price_per_kg"] for l in metal["lots"]) / total_qty if total_qty > 0 else 0.0
            metal["price_per_kg"] = weighted_price
            metal["sale_price_per_kg"] = metal["price_per_kg"] # تحديث سعر البيع حسب السعر الجديد

            # إضافة تفصيل المعاملة
            transaction_details = {
                "operation": "إضافة كمية",
                "metal": name,
                "quantity": qty,
                "price_per_kg": buy_price,
                "total_price": total_amount,
                "paid_amount": paid_amount,
                "due_amount": due_amount
            }

            self.data["history"].append({
                "date": now_iso(),
                "operation": "إضافة كمية",
                "metal": name,
                "quantity": qty,
                "price_per_kg": buy_price,
                "total_price": total_amount,
                "person": source,
                "paid_amount": paid_amount,
                "due_amount": due_amount,
                "transaction_type": "purchase"
            })

            # تحديث رصيد المورد وإضافة تفصيل المعاملة
            update_party_balance(self.data["parties"], source, due_amount, "purchase", is_supplier=True, transaction_details=transaction_details)

            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_remove_stock(self):
        dialog = RemoveStockDialog(self, self.data.get("metals", []), self.data.get("parties", {}))
        self.wait_window(dialog.top)
        if dialog.result:
            # إذا كانت النتيجة قائمة من المعاملات (عند تقسيم الكمية على مصادر متعددة)
            if isinstance(dialog.result, list):
                for transaction in dialog.result:
                    if not transaction:
                        continue
                    self.process_single_transaction(transaction)
            else: # معاملة واحدة (قائمة من القيم)
                if dialog.result and len(dialog.result) > 0:
                    for transaction_data in dialog.result: # التكرار على العناصر داخل القائمة
                        # بناء كائن المعاملة من البيانات
                        trans_obj = {
                            "name": transaction_data[0],
                            "qty": transaction_data[1],
                            "sale_price": transaction_data[2],
                            "person": transaction_data[3],
                            "paid_amount": transaction_data[4],
                            "due_amount": transaction_data[5],
                            "lot_index": transaction_data[6] if len(transaction_data) > 6 else None,
                            "cost_basis": transaction_data[7] if len(transaction_data) > 7 else 0,
                            "profit": transaction_data[8] if len(transaction_data) > 8 else 0,
                            "profit_percentage": transaction_data[9] if len(transaction_data) > 9 else 0
                        }
                        self.process_single_transaction(trans_obj)

            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def process_single_transaction(self, transaction):
        """معالجة معاملة واحدة للبيع"""
        # التحقق من نوع المعاملة وتحويلها إلى كائن قابل للقراءة
        if isinstance(transaction, dict):
            name = transaction["name"]
            qty = transaction["qty"]
            sale_price = transaction["sale_price"]
            person = transaction["person"]
            paid_amount = transaction["paid_amount"]
            due_amount = transaction["due_amount"]
            lot_index = transaction.get("lot_index")
            cost_basis = transaction.get("cost_basis", 0)
            profit = transaction.get("profit", 0)
            profit_percentage = transaction.get("profit_percentage", 0)
        else: # إذا كانت المعاملة عبارة عن قائمة من القيم
            name, qty, sale_price, person, paid_amount, due_amount, lot_index = transaction
            # حساب التكلفة والربح إذا لم يتم حسابها مسبقًا في التقسيم
            metal = next((m for m in self.data["metals"] if m["name"] == name), None)
            if metal and lot_index is not None:
                # نستخدم الدالة الحالية لحساب التكلفة إذا لم تكن موجودة
                if cost_basis == 0:
                    temp_cost, _ = calculate_cost_basis_and_sources(metal, qty, lot_index)
                    cost_basis = temp_cost
                revenue = qty * sale_price
                profit = revenue - cost_basis
                profit_percentage = (profit / cost_basis * 100) if cost_basis > 0 else 0.0
            else:
                # في حالة التقسيم، تكون الحسابات مسبقة
                revenue = qty * sale_price
                profit = revenue - cost_basis
                profit_percentage = (profit / cost_basis * 100) if cost_basis > 0 else 0.0

        metal = next((m for m in self.data["metals"] if m["name"] == name), None)
        if not metal:
            messagebox.showerror("خطأ", "المعدن غير موجود.")
            return

        qty = float(qty)

        # تحديث إجمالي الربح للمعدن
        metal["profit_total"] = metal.get("profit_total", 0.0) + profit

        revenue = qty * sale_price

        # إضافة تفصيل المعاملة
        transaction_details = {
            "operation": "بيع / سحب كمية",
            "metal": name,
            "quantity": qty,
            "price_per_kg": sale_price,
            "total_price": revenue,
            "paid_amount": paid_amount,
            "due_amount": due_amount,
            "cost_basis": cost_basis,
            "profit": profit
        }

        self.data["history"].append({
            "date": now_iso(),
            "operation": "بيع / سحب كمية",
            "metal": name,
            "quantity": qty,
            "price_per_kg": float(sale_price),
            "total_price": revenue,
            "person": person,
            "cost_basis": cost_basis,
            "profit": profit,
            "profit_percentage": profit_percentage,
            "paid_amount": paid_amount,
            "due_amount": due_amount,
            "transaction_type": "sale"
        })

        # تحديث رصيد العميل وإضافة تفصيل المعاملة
        update_party_balance(self.data["parties"], person, due_amount, "sale", is_supplier=False, transaction_details=transaction_details)

    def remove_metal(self):
        """حذف معدن من القائمة"""
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("تحذير", "يرجى تحديد معدن لحذفه.")
            return
        metal_name = selected_item
        if not messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف المعدن '{metal_name}'؟"):
            return

        # حذف المعدن من البيانات فقط
        self.data["metals"] = [m for m in self.data["metals"] if m["name"] != metal_name]
        save_data(self.data)
        make_backup(self.data)
        self.refresh_table()

    def open_history_window(self):
        top = tk.Toplevel(self)
        top.title("🕒 سجل العمليات")
        top.geometry("1200x600")

        # أزرار التصدير
        tool_frame = ttk.Frame(top)
        tool_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(tool_frame, text="📄 تصدير CSV", command=lambda: self.export_history_csv(top)).pack(side=tk.LEFT, padx=4)
        ttk.Button(tool_frame, text="📄 تصدير JSON", command=lambda: self.export_history_json(top)).pack(side=tk.LEFT, padx=4)
        ttk.Button(tool_frame, text="✏️ تعديل سجل", command=lambda: self.edit_history_entry(top)).pack(side=tk.LEFT, padx=4)

        # جدول السجل
        cols = ("date", "operation", "metal", "quantity", "price_per_kg", "total_price", "person", "paid_amount", "due_amount", "cost_basis", "profit", "profit_percentage")
        headers_ar = {
            "date": "التاريخ",
            "operation": "العملية",
            "metal": "المعدن",
            "quantity": "الكمية",
            "price_per_kg": "السعر لكل كجم",
            "total_price": "القيمة الإجمالية",
            "person": "الطرف",
            "paid_amount": "المبلغ المدفوع",
            "due_amount": "المبلغ المتبقي",
            "cost_basis": "تكلفة الشراء",
            "profit": "الربح",
            "profit_percentage": "نسبة الربح (%)"
        }
        tree = ttk.Treeview(top, columns=cols, show="headings", height=20)
        for c in cols:
            tree.heading(c, text=headers_ar.get(c, c))
            tree.column(c, anchor="center", width=100)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # شريط تمرير
        v_scrollbar = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=v_scrollbar.set)

        # ملء الجدول
        for i, h in enumerate(self.data["history"]):
            tree.insert("", "end", iid=i, values=(
                h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"),
                h.get("price_per_kg"), h.get("total_price"), h.get("person"),
                h.get("paid_amount", ""), h.get("due_amount", ""), h.get("cost_basis", ""),
                h.get("profit", ""), h.get("profit_percentage", "")
            ))

    def export_history_csv(self, parent_window):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "التاريخ", "العملية", "المعدن", "الكمية", "السعر لكل كجم",
                    "القيمة الإجمالية", "الطرف", "المبلغ المدفوع", "المبلغ المتبقي",
                    "تكلفة الشراء", "الربح", "نسبة الربح (%)"
                ])
                for h in self.data["history"]:
                    writer.writerow([
                        h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"),
                        h.get("price_per_kg"), h.get("total_price"), h.get("person"),
                        h.get("paid_amount", ""), h.get("due_amount", ""),
                        h.get("cost_basis", ""), h.get("profit", ""), h.get("profit_percentage", "")
                    ])
            messagebox.showinfo("تم", "تم تصدير السجل CSV.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def export_history_json(self, parent_window):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data["history"], f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم تصدير السجل JSON.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def edit_history_entry(self, parent_window):
        selected_item = parent_window.focus_get()
        if hasattr(selected_item, 'focus') and selected_item.focus():
            selected_item_id = selected_item.focus()
        else:
            # إذا لم يتم تحديد عنصر في النافذة الفرعية، نستخدم النافذة الرئيسية
            selected_item_id = self.tree.focus()
            if not selected_item_id or selected_item_id not in [str(i) for i in range(len(self.data["history"]))]:
                 messagebox.showwarning("تحذير", "يرجى تحديد سجل لتعديله من نافذة السجل.")
                 return

        entry_index = int(selected_item_id)
        entry = self.data["history"][entry_index]

        edit_window = tk.Toplevel(parent_window)
        edit_window.title("✏️ تعديل سجل")
        edit_window.geometry("500x500")

        fields = {}
        row = 0
        for label, field in [
            ("التاريخ:", "date"), ("العملية:", "operation"), ("المعدن:", "metal"), ("الكمية:", "quantity"),
            ("السعر لكل كجم:", "price_per_kg"), ("القيمة الإجمالية:", "total_price"), ("الطرف:", "person"),
            ("المبلغ المدفوع:", "paid_amount"), ("المبلغ المتبقي:", "due_amount"), ("تكلفة الشراء:", "cost_basis"),
            ("الربح:", "profit"), ("نسبة الربح (%):", "profit_percentage")
        ]:
            ttk.Label(edit_window, text=label, font=("Cairo", 10, "bold")).grid(row=row, column=1, sticky="e", padx=5, pady=2)
            entry_field = ttk.Entry(edit_window, justify="right")
            entry_field.grid(row=row, column=0, padx=5, pady=2)
            entry_field.insert(0, str(entry.get(field, "")))
            fields[field] = entry_field
            row += 1

        def save_changes():
            try:
                # تحديث البيانات
                for key in fields:
                    if key in ["quantity", "price_per_kg", "total_price", "paid_amount", "due_amount", "cost_basis", "profit", "profit_percentage"]:
                        entry[key] = float(fields[key].get())
                    else:
                        entry[key] = fields[key].get()
                # حفظ التغييرات في الملف
                save_data(self.data)
                make_backup(self.data)
                messagebox.showinfo("تم", "تم تعديل السجل بنجاح.")
                edit_window.destroy()
                if parent_window: parent_window.destroy() # تحديث النافذة الأم
            except ValueError:
                messagebox.showerror("خطأ", "يرجى إدخال قيم صحيحة.")

        btn_frame = ttk.Frame(edit_window)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="💾 حفظ", command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)

    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم تصدير البيانات.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], title="اختر ملف JSON للاستيراد")
        if not path:
            return
        if not messagebox.askyesno("تأكيد", "سيتم استبدال جميع البيانات الحالية. هل ترغب بالمتابعة؟"):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "metals" in d and "history" in d and "parties" in d and "expenses" in d:
                self.data = d
                save_data(self.data)
                make_backup(self.data)
                self.refresh_table()
                messagebox.showinfo("تم", "تم استيراد البيانات.")
            else:
                messagebox.showerror("خطأ", "ملف غير صالح.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستيراد: {e}")

    def open_manage_parties(self):
        top = tk.Toplevel(self)
        top.title("👥 إدارة الحسابات (العملاء والموردين)")
        top.geometry("800x500")

        # جدول الحسابات
        cols = ("name", "type", "balance", "transaction_count")
        headers_ar = {"name": "الاسم", "type": "النوع", "balance": "الرصيد", "transaction_count": "عدد المعاملات"}
        tree = ttk.Treeview(top, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=headers_ar.get(c, c))
            tree.column(c, anchor="center", width=150)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def refresh_party_table():
            for i in tree.get_children():
                tree.delete(i)
            for name, info in self.data["parties"].items():
                tree.insert("", "end", iid=name, values=(name, info.get("type", ""), info.get("balance", 0.0), len(info.get("transactions", []))))

        refresh_party_table()

        # أزرار الإجراءات
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="➕ إضافة حساب", command=lambda: self.add_party_dialog(top, refresh_party_table)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ حذف حساب", command=lambda: self.delete_party(tree, refresh_party_table)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📋 عرض سجل المعاملات", command=lambda: self.view_party_transactions(tree)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📄 تصدير CSV", command=lambda: self.export_parties_csv()).pack(side=tk.LEFT, padx=2)

    def add_party_dialog(self, parent, refresh_func):
        dialog = AddPartyDialog(parent)
        parent.wait_window(dialog.top)
        if dialog.result:
            name, party_type = dialog.result
            if name in self.data["parties"]:
                messagebox.showerror("خطأ", "الحساب موجود بالفعل.")
                return
            self.data["parties"][name] = {"type": party_type, "balance": 0.0, "transactions": []}
            save_data(self.data)
            make_backup(self.data)
            refresh_func()

    def delete_party(self, tree, refresh_func):
        selected = tree.focus()
        if not selected:
            messagebox.showwarning("تحذير", "يرجى تحديد حساب لحذفه.")
            return
        if not messagebox.askyesno("تأكيد", f"هل أنت متأكد من حذف الحساب '{selected}'؟"):
            return
        del self.data["parties"][selected]
        save_data(self.data)
        make_backup(self.data)
        refresh_func()

    def view_party_transactions(self, tree):
        selected = tree.focus()
        if not selected:
            messagebox.showwarning("تحذير", "يرجى تحديد حساب لعرض معاملاته.")
            return
        party_info = self.data["parties"].get(selected, {})
        top = tk.Toplevel(self)
        top.title(f"📋 سجل المعاملات - {selected}")
        top.geometry("1000x400")

        cols = ("date", "operation", "metal", "quantity", "price_per_kg", "total_price", "paid_amount", "due_amount", "cost_basis", "profit")
        headers_ar = {
            "date": "التاريخ", "operation": "العملية", "metal": "المعدن", "quantity": "الكمية",
            "price_per_kg": "السعر/كجم", "total_price": "الإجمالي", "paid_amount": "المدفوع", "due_amount": "المطلوب",
            "cost_basis": "تكلفة الشراء", "profit": "الربح"
        }
        tree_trans = ttk.Treeview(top, columns=cols, show="headings", height=15)
        for c in cols:
            tree_trans.heading(c, text=headers_ar.get(c, c))
            tree_trans.column(c, anchor="center", width=100)
        tree_trans.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for trans in party_info.get("transactions", []):
            tree_trans.insert("", "end", values=(
                trans.get("date"), trans.get("operation"), trans.get("metal"), trans.get("quantity"),
                trans.get("price_per_kg"), trans.get("total_price"), trans.get("paid_amount", ""),
                trans.get("due_amount", ""), trans.get("cost_basis", ""), trans.get("profit", "")
            ))

    def export_parties_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["الاسم", "النوع", "الرصيد", "عدد المعاملات"])
                for name, info in self.data["parties"].items():
                    party_type = "مورد" if info.get("type") == "supplier" else "عميل"
                    writer.writerow([name, party_type, info.get("balance", 0.0), len(info.get("transactions", []))])
            messagebox.showinfo("تم", "تم تصدير الحسابات CSV.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def open_manage_expenses(self):
        # وظيفة بسيطة لإدارة المصروفات_miscellaneous expenses
        top = tk.Toplevel(self)
        top.title("💸 إدارة المصروفات")
        top.geometry("800x500")

        # جدول المصروفات
        cols = ("date", "description", "amount", "paid_amount", "due_amount", "person")
        headers_ar = {"date": "التاريخ", "description": "الوصف", "amount": "المبلغ", "paid_amount": "المدفوع", "due_amount": "المطلوب", "person": "الطرف"}
        tree = ttk.Treeview(top, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=headers_ar.get(c, c))
            tree.column(c, anchor="center", width=120)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def refresh_expense_table():
            for i in tree.get_children():
                tree.delete(i)
            for exp in self.data["expenses"]:
                tree.insert("", "end", values=(
                    exp.get("date"), exp.get("description"), exp.get("amount"),
                    exp.get("paid_amount", 0.0), exp.get("due_amount", 0.0), exp.get("person", "")
                ))

        refresh_expense_table()

        # أزرار الإجراءات
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="➕ إضافة مصروف", command=lambda: self.add_expense_dialog(top, refresh_expense_table)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ حذف مصروف", command=lambda: self.delete_expense(tree, refresh_expense_table)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="📄 تصدير CSV", command=lambda: self.export_expenses_csv()).pack(side=tk.LEFT, padx=2)

    def add_expense_dialog(self, parent, refresh_func):
        # نافذة إضافة مصروف
        top = tk.Toplevel(parent)
        top.title("➕ إضافة مصروف")
        top.geometry("400x250")
        top.transient(parent)
        top.grab_set()

        ttk.Label(top, text="التاريخ (YYYY-MM-DD):", font=("Cairo", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        e_date = ttk.Entry(top, justify="right")
        e_date.grid(row=0, column=1, pady=5, padx=5)
        e_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(top, text="الوصف:", font=("Cairo", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        e_desc = ttk.Entry(top, justify="right")
        e_desc.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(top, text="المبلغ:", font=("Cairo", 10, "bold")).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        e_amount = ttk.Entry(top, justify="right")
        e_amount.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(top, text="الطرف (اختياري):", font=("Cairo", 10, "bold")).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        e_person = ttk.Entry(top, justify="right")
        e_person.grid(row=3, column=1, pady=5, padx=5)

        # الدفعات الجزئية
        ttk.Label(top, text="المبلغ المدفوع:", font=("Cairo", 10, "bold")).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        e_paid = ttk.Entry(top, justify="right")
        e_paid.grid(row=4, column=1, pady=5, padx=5)
        e_paid.insert(0, "0")

        ttk.Label(top, text="المبلغ المتبقي:", font=("Cairo", 10, "bold")).grid(row=5, column=0, sticky="e", padx=5, pady=5)
        e_due = ttk.Entry(top, justify="right")
        e_due.grid(row=5, column=1, pady=5, padx=5)
        e_due.insert(0, "0")

        def on_add():
            date = e_date.get().strip()
            desc = e_desc.get().strip()
            amount_str = e_amount.get().strip()
            person = e_person.get().strip() or "عام"
            paid_str = e_paid.get().strip() or "0"
            due_str = e_due.get().strip() or "0"

            if not date or not desc or not amount_str:
                messagebox.showerror("خطأ", "يرجى ملء الحقول المطلوبة (التاريخ، الوصف، المبلغ).")
                return
            try:
                amount = float(amount_str)
                paid = float(paid_str)
                due = float(due_str)
                if amount <= 0:
                    raise ValueError("المبلغ يجب أن يكون أكبر من الصفر.")
            except ValueError as e:
                messagebox.showerror("خطأ", f"قيمة غير صحيحة: {e}")
                return

            expense = {
                "date": date,
                "description": desc,
                "amount": amount,
                "person": person,
                "paid_amount": paid,
                "due_amount": due
            }
            self.data["expenses"].append(expense)

            # تحديث رصيد الطرف
            update_party_balance(self.data["parties"], person, due, "expense", is_supplier=False) # نعتبر المصروفات كزيادة في الذمة المدينة للطرف

            save_data(self.data)
            make_backup(self.data)
            refresh_func()
            top.destroy()

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="✅ حفظ", command=on_add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=top.destroy).pack(side=tk.RIGHT, padx=5)

    def delete_expense(self, tree, refresh_func):
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "يرجى تحديد مصروف لحذفه.")
            return
        if not messagebox.askyesno("تأكيد", "هل أنت متأكد من حذف المصروف المحدد؟"):
            return
        # حذف من القائمة حسب القيمة، لأن لا يوجد معرف فريد
        values = tree.item(selected[0])['values']
        self.data["expenses"] = [e for e in self.data["expenses"] if not (
            e.get("date") == values[0] and e.get("description") == values[1] and e.get("amount") == values[2]
        )]
        save_data(self.data)
        make_backup(self.data)
        refresh_func()

    def export_expenses_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["التاريخ", "الوصف", "المبلغ", "المدفوع", "المطلوب", "الطرف"])
                for exp in self.data["expenses"]:
                    writer.writerow([
                        exp.get("date"), exp.get("description"), exp.get("amount"),
                        exp.get("paid_amount", 0.0), exp.get("due_amount", 0.0), exp.get("person", "")
                    ])
            messagebox.showinfo("تم", "تم تصدير المصروفات CSV.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def open_settings(self):
        top = tk.Toplevel(self)
        top.title("⚙️ الإعدادات")
        top.geometry("400x200")
        top.transient(self)
        top.grab_set()

        var_auto_backup = tk.BooleanVar(value=self.settings.get("auto_backup", True))
        ttk.Checkbutton(top, text="تمكين النسخ الاحتياطي التلقائي", variable=var_auto_backup).pack(pady=10)

        def save_settings():
            self.settings["auto_backup"] = var_auto_backup.get()
            save_settings(self.settings)
            messagebox.showinfo("تم", "تم حفظ الإعدادات.")
            top.destroy()

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="💾 حفظ", command=save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=top.destroy).pack(side=tk.RIGHT, padx=5)

    def open_edit_prices(self, metal_name):
        metal = next((m for m in self.data["metals"] if m["name"] == metal_name), None)
        if not metal:
            return

        top = tk.Toplevel(self)
        top.title(f"✏️ تعديل أسعار - {metal_name}")
        top.geometry("400x150")
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text="سعر الشراء (ج/كجم):", font=("Cairo", 10, "bold")).grid(row=0, column=1, sticky="e", padx=5, pady=5)
        e_buy = ttk.Entry(top, justify="right")
        e_buy.grid(row=0, column=0, padx=5, pady=5)
        e_buy.insert(0, str(metal.get("price_per_kg", 0.0)))

        ttk.Label(top, text="سعر البيع (ج/كجم):", font=("Cairo", 10, "bold")).grid(row=1, column=1, sticky="e", padx=5, pady=5)
        e_sell = ttk.Entry(top, justify="right")
        e_sell.grid(row=1, column=0, padx=6, pady=4)
        e_sell.insert(0, str(metal.get("sale_price_per_kg", metal.get("price_per_kg", 0.0))))

        def save_prices():
            try:
                metal["price_per_kg"] = float(e_buy.get())
                metal["sale_price_per_kg"] = float(e_sell.get())
                metal["last_updated"] = now_iso()
                save_data(self.data)
                make_backup(self.data)
                self.refresh_table()
                top.destroy()
                if self: self.lift() # رفع النافذة الرئيسية بعد إغلاق النافذة الفرعية
            except Exception as e:
                messagebox.showerror("خطأ", f"قيمة غير صحيحة: {e}")

        button_frame = ttk.Frame(top)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="💾 حفظ", command=save_prices).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="❌ إلغاء", command=top.destroy).pack(side=tk.RIGHT, padx=5)

    def on_exit(self):
        """يسأل المستخدم عن النسخ الاحتياطي قبل الإغلاق"""
        if messagebox.askyesno("خروج", "هل ترغب في إنشاء نسخة احتياطية قبل الإغلاق؟"):
            make_backup(self.data)
            messagebox.showinfo("تم", "تم إنشاء نسخة احتياطية بنجاح.")
        self.destroy()

class AddPartyDialog:
    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        top.title("➕ إضافة حساب")
        top.geometry("400x150")
        top.transient(parent)
        top.grab_set()

        ttk.Label(top, text="اسم الحساب:", font=("Cairo", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.e_name = ttk.Entry(top, justify="right")
        self.e_name.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(top, text="نوع الحساب:", font=("Cairo", 10, "bold")).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.cmb_type = ttk.Combobox(top, values=["عميل", "مورد"], state="readonly", justify="right")
        self.cmb_type.grid(row=1, column=1, pady=5, padx=5)
        self.cmb_type.set("عميل")

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="✅ حفظ", command=self.on_add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="❌ إلغاء", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)

        self.result = None

    def on_add(self):
        name = self.e_name.get().strip()
        party_type = self.cmb_type.get().strip()
        if not name:
            messagebox.showerror("خطأ", "يرجى إدخال اسم الحساب.")
            return
        if party_type not in ["مورد", "عميل"]:
            messagebox.showerror("خطأ", "يرجى اختيار نوع الحساب بشكل صحيح.")
            return
        self.result = (name, party_type)
        self.top.destroy()

    def on_cancel(self):
        self.top.destroy()

if __name__ == "__main__":
    app = MetalInventoryApp()
    app.protocol("WM_DELETE_WINDOW", app.on_exit)
    app.mainloop()
```
